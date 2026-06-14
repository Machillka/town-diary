"""Combined runtime checkpoint persistence, restore, and replay."""

from collections.abc import Mapping
from dataclasses import dataclass
import json
from pathlib import Path

from town_diary.core.config import ConfigBundle
from town_diary.core.contracts import TimeBlock, Weather
from town_diary.core.errors import SnapshotValidationError
from town_diary.core.run_context import RunContext, config_digest
from town_diary.core.schema import SCHEMA_VERSION, SUPPORTED_SCHEMA_VERSIONS
from town_diary.events import WorldLog
from town_diary.simulation.runtime import (
    RuntimeEndReason,
    RuntimeStatus,
    WorldRuntime,
    WorldTickRecord,
)
from town_diary.simulation.world_state import WorldState, WorldStateCheckpoint


@dataclass(frozen=True, slots=True)
class RuntimeCheckpoint:
    """All structured state required to continue or replay a world runtime."""

    run_context: Mapping[str, object]
    world_state: WorldStateCheckpoint
    records: tuple[WorldTickRecord, ...]
    saved_status: RuntimeStatus
    end_reason: RuntimeEndReason | None
    world_events: tuple[object, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "run_context": dict(self.run_context),
            "world_state": self.world_state.to_dict(),
            "records": [record.to_dict() for record in self.records],
            "saved_status": self.saved_status.value,
            "end_reason": self.end_reason.value if self.end_reason else None,
            "world_events": list(self.world_events),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: object) -> "RuntimeCheckpoint":
        if not isinstance(value, Mapping):
            raise SnapshotValidationError("runtime checkpoint must be a mapping")
        required = {
            "run_context",
            "world_state",
            "records",
            "saved_status",
            "end_reason",
            "world_events",
            "schema_version",
        }
        missing = sorted(required.difference(value))
        if missing:
            raise SnapshotValidationError(
                f"runtime checkpoint missing fields: {', '.join(missing)}"
            )
        if value["schema_version"] not in SUPPORTED_SCHEMA_VERSIONS:
            raise SnapshotValidationError(
                f"unsupported runtime checkpoint schema_version: {value['schema_version']}"
            )
        if not isinstance(value["run_context"], Mapping):
            raise SnapshotValidationError("runtime checkpoint run_context must be a mapping")
        if not isinstance(value["records"], list):
            raise SnapshotValidationError("runtime checkpoint records must be a list")
        if not isinstance(value["world_events"], list):
            raise SnapshotValidationError("runtime checkpoint world_events must be a list")
        try:
            saved_status = RuntimeStatus(value["saved_status"])
            end_reason = (
                RuntimeEndReason(value["end_reason"])
                if value["end_reason"] is not None
                else None
            )
        except (TypeError, ValueError) as error:
            raise SnapshotValidationError(
                "runtime checkpoint lifecycle state is invalid"
            ) from error
        if saved_status is RuntimeStatus.ENDED and end_reason is None:
            raise SnapshotValidationError("ended runtime checkpoint needs an end reason")
        if saved_status is not RuntimeStatus.ENDED and end_reason is not None:
            raise SnapshotValidationError("active runtime checkpoint cannot have an end reason")
        return cls(
            run_context=dict(value["run_context"]),
            world_state=_world_state_checkpoint(value["world_state"]),
            records=tuple(_tick_record(record) for record in value["records"]),
            saved_status=saved_status,
            end_reason=end_reason,
            world_events=tuple(value["world_events"]),
            schema_version=str(value["schema_version"]),
        )


def create_runtime_checkpoint(runtime: WorldRuntime) -> RuntimeCheckpoint:
    """Capture runtime state after any committed tick."""
    return RuntimeCheckpoint(
        run_context=runtime.context.to_manifest(),
        world_state=runtime.world_state.checkpoint(),
        records=runtime.records,
        saved_status=runtime.status,
        end_reason=runtime.end_reason,
        world_events=tuple(runtime.world_log.to_dicts()),
    )


def restore_world_runtime(
    *,
    checkpoint: RuntimeCheckpoint | object,
    config: ConfigBundle,
) -> WorldRuntime:
    """Restore a checkpoint without consulting any textual output."""
    parsed = (
        checkpoint
        if isinstance(checkpoint, RuntimeCheckpoint)
        else RuntimeCheckpoint.from_dict(checkpoint)
    )
    context = RunContext.from_manifest(parsed.run_context)
    _validate_config_digest(context, config)
    world_state = WorldState.from_checkpoint(
        checkpoint=parsed.world_state,
        config=config,
        random=context.random,
    )
    restored_status = (
        RuntimeStatus.ENDED
        if parsed.saved_status is RuntimeStatus.ENDED
        else RuntimeStatus.PAUSED
    )
    return WorldRuntime(
        config=config,
        context=context,
        world_state=world_state,
        status=restored_status,
        end_reason=parsed.end_reason,
        records=parsed.records,
        world_log=WorldLog.from_dicts(list(parsed.world_events)),
    )


def replay_world_runtime(
    *,
    checkpoint: RuntimeCheckpoint | object,
    config: ConfigBundle,
) -> WorldRuntime:
    """Re-run to the checkpoint tick using its original seed and config identity."""
    parsed = (
        checkpoint
        if isinstance(checkpoint, RuntimeCheckpoint)
        else RuntimeCheckpoint.from_dict(checkpoint)
    )
    context = RunContext.from_manifest(parsed.run_context)
    _validate_config_digest(context, config)
    replay = WorldRuntime.create(config=config, seed=context.seed)
    if parsed.world_state.tick:
        replay.run_ticks(parsed.world_state.tick)
    return replay


def save_runtime_checkpoint(
    path: str | Path,
    checkpoint: RuntimeCheckpoint,
) -> None:
    """Write a checkpoint once; existing files are never overwritten."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("x", encoding="utf-8") as file:
            json.dump(
                checkpoint.to_dict(),
                file,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
    except FileExistsError as error:
        raise SnapshotValidationError(f"checkpoint already exists: {target}") from error


def load_runtime_checkpoint(path: str | Path) -> RuntimeCheckpoint:
    target = Path(path)
    try:
        with target.open(encoding="utf-8") as file:
            return RuntimeCheckpoint.from_dict(json.load(file))
    except FileNotFoundError as error:
        raise SnapshotValidationError(f"checkpoint does not exist: {target}") from error
    except json.JSONDecodeError as error:
        raise SnapshotValidationError(f"checkpoint is not valid JSON: {target}") from error


def _validate_config_digest(context: RunContext, config: ConfigBundle) -> None:
    if context.config_digest != config_digest(config):
        raise SnapshotValidationError(
            "runtime checkpoint config digest does not match active configuration"
        )


def _world_state_checkpoint(value: object) -> WorldStateCheckpoint:
    return WorldStateCheckpoint.from_dict(value)


def _tick_record(value: object) -> WorldTickRecord:
    if not isinstance(value, Mapping):
        raise SnapshotValidationError("runtime checkpoint tick record must be a mapping")
    required = {
        "tick",
        "day",
        "time_block",
        "previous_weather",
        "weather",
        "weather_changed",
        "schema_version",
    }
    missing = sorted(required.difference(value))
    if missing:
        raise SnapshotValidationError(
            f"runtime checkpoint tick record missing fields: {', '.join(missing)}"
        )
    if value["schema_version"] not in SUPPORTED_SCHEMA_VERSIONS:
        raise SnapshotValidationError(
            f"unsupported tick record schema_version: {value['schema_version']}"
        )
    tick = value["tick"]
    day = value["day"]
    weather_changed = value["weather_changed"]
    if not isinstance(tick, int) or tick < 1:
        raise SnapshotValidationError("runtime checkpoint tick must be positive")
    if not isinstance(day, int) or day < 1:
        raise SnapshotValidationError("runtime checkpoint day must be positive")
    if not isinstance(weather_changed, bool):
        raise SnapshotValidationError("runtime checkpoint weather_changed must be boolean")
    try:
        return WorldTickRecord(
            tick=tick,
            day=day,
            time_block=TimeBlock(value["time_block"]),
            previous_weather=Weather(value["previous_weather"]),
            weather=Weather(value["weather"]),
            weather_changed=weather_changed,
            schema_version=str(value["schema_version"]),
        )
    except (TypeError, ValueError) as error:
        raise SnapshotValidationError(
            "runtime checkpoint tick record has invalid enum values"
        ) from error
