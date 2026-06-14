"""Independent objective-world runtime lifecycle."""

from dataclasses import dataclass
from enum import StrEnum

from town_diary.core.config import ConfigBundle
from town_diary.core.contracts import TimeBlock, Weather, WorldSnapshot
from town_diary.core.errors import TownDiaryError
from town_diary.core.run_context import RunContext
from town_diary.core.schema import SCHEMA_VERSION
from town_diary.events import EventFactory, WorldLog
from town_diary.simulation.clock import TIME_BLOCKS
from town_diary.simulation.world_state import WorldState


class RuntimeLifecycleError(TownDiaryError):
    """Raised when a lifecycle operation is invalid for the current state."""


class RuntimeStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    ENDED = "ended"


class RuntimeEndReason(StrEnum):
    COMPLETED = "completed"
    STOPPED = "stopped"


@dataclass(frozen=True, slots=True)
class WorldTickRecord:
    """Objective environment result for one committed runtime tick."""

    tick: int
    day: int
    time_block: TimeBlock
    previous_weather: Weather
    weather: Weather
    weather_changed: bool
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "tick": self.tick,
            "day": self.day,
            "time_block": self.time_block.value,
            "previous_weather": self.previous_weather.value,
            "weather": self.weather.value,
            "weather_changed": self.weather_changed,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True, slots=True)
class WorldRunSummary:
    """Read-only summary of a world runtime."""

    run_id: str
    status: RuntimeStatus
    end_reason: RuntimeEndReason | None
    ticks_completed: int
    days_completed: int
    current_day: int
    current_time_block: TimeBlock
    current_weather: Weather
    weather_changes: int
    world_events: int
    schema_version: str = SCHEMA_VERSION


class WorldRuntime:
    """Lifecycle owner for an environment that runs without Agent or Writing."""

    def __init__(
        self,
        *,
        config: ConfigBundle,
        context: RunContext,
        world_state: WorldState,
        status: RuntimeStatus = RuntimeStatus.CREATED,
        end_reason: RuntimeEndReason | None = None,
        records: tuple[WorldTickRecord, ...] = (),
        world_log: WorldLog | None = None,
    ) -> None:
        self._config = config
        self._context = context
        self._world_state = world_state
        self._status = RuntimeStatus(status)
        self._end_reason = end_reason
        self._records = list(records)
        self._world_log = world_log or WorldLog()
        self._events = EventFactory(
            run_id=str(context.run_id),
            ids=context.ids,
            world_log=self._world_log,
        )
        self._validate_runtime_state()

    @classmethod
    def create(cls, *, config: ConfigBundle, seed: int) -> "WorldRuntime":
        context = RunContext.create(seed=seed, config=config)
        return cls(
            config=config,
            context=context,
            world_state=WorldState.from_config(config=config, random=context.random),
        )

    @property
    def config(self) -> ConfigBundle:
        return self._config

    @property
    def context(self) -> RunContext:
        return self._context

    @property
    def world_state(self) -> WorldState:
        """Environment-owned mutable state; never pass this to an Agent."""
        return self._world_state

    @property
    def status(self) -> RuntimeStatus:
        return self._status

    @property
    def end_reason(self) -> RuntimeEndReason | None:
        return self._end_reason

    @property
    def records(self) -> tuple[WorldTickRecord, ...]:
        return tuple(self._records)

    @property
    def world_log(self) -> WorldLog:
        return self._world_log

    def start(self) -> None:
        if self._status is not RuntimeStatus.CREATED:
            raise RuntimeLifecycleError("only a created runtime can start")
        self._status = RuntimeStatus.RUNNING

    def pause(self) -> None:
        if self._status is not RuntimeStatus.RUNNING:
            raise RuntimeLifecycleError("only a running runtime can pause")
        self._status = RuntimeStatus.PAUSED

    def resume(self) -> None:
        if self._status is not RuntimeStatus.PAUSED:
            raise RuntimeLifecycleError("only a paused runtime can resume")
        self._status = RuntimeStatus.RUNNING

    def end(self, reason: RuntimeEndReason = RuntimeEndReason.STOPPED) -> None:
        if self._status not in {RuntimeStatus.RUNNING, RuntimeStatus.PAUSED}:
            raise RuntimeLifecycleError("only an active runtime can end")
        self._status = RuntimeStatus.ENDED
        self._end_reason = RuntimeEndReason(reason)

    def step(self) -> WorldTickRecord:
        if self._status is not RuntimeStatus.RUNNING:
            raise RuntimeLifecycleError("runtime must be running to advance")

        day = self._world_state.clock.day
        time_block = self._world_state.clock.time_block
        previous_weather = self._world_state.weather.current
        change = self._world_state.weather.advance(day=day, time_block=time_block)
        if change is not None and change.previous != change.current:
            self._events.weather_event(
                change=change,
                location_id=self._config.locations[0].id,
            )
        self._world_state.increment_tick()
        record = WorldTickRecord(
            tick=self._world_state.tick,
            day=day,
            time_block=time_block,
            previous_weather=previous_weather,
            weather=self._world_state.weather.current,
            weather_changed=change is not None and change.previous != change.current,
        )
        self._records.append(record)
        self._world_state.clock.advance()
        self._world_state.validate_invariants()
        return record

    def run_ticks(self, ticks: int, *, end_when_complete: bool = False) -> WorldRunSummary:
        if not isinstance(ticks, int) or ticks < 1:
            raise ValueError("ticks must be a positive integer")
        if self._status is RuntimeStatus.CREATED:
            self.start()
        if self._status is not RuntimeStatus.RUNNING:
            raise RuntimeLifecycleError("runtime must be running to run ticks")
        for _ in range(ticks):
            self.step()
        if end_when_complete:
            self.end(RuntimeEndReason.COMPLETED)
        return self.summary()

    def run_days(self, days: int) -> WorldRunSummary:
        if not isinstance(days, int) or days < 1:
            raise ValueError("days must be a positive integer")
        return self.run_ticks(days * len(TIME_BLOCKS), end_when_complete=True)

    def record_committed_tick(self, record: WorldTickRecord) -> None:
        """Attach a tick committed by another Environment driver."""
        if self._status is not RuntimeStatus.RUNNING:
            raise RuntimeLifecycleError("runtime must be running to record a tick")
        if record.tick != self._world_state.tick or record.tick != len(self._records) + 1:
            raise RuntimeLifecycleError("committed tick record does not match runtime state")
        self._records.append(record)

    def snapshot(self) -> WorldSnapshot:
        return self._world_state.snapshot()

    def summary(self) -> WorldRunSummary:
        return WorldRunSummary(
            run_id=str(self._context.run_id),
            status=self._status,
            end_reason=self._end_reason,
            ticks_completed=self._world_state.tick,
            days_completed=self._world_state.tick // len(TIME_BLOCKS),
            current_day=self._world_state.clock.day,
            current_time_block=self._world_state.clock.time_block,
            current_weather=self._world_state.weather.current,
            weather_changes=sum(record.weather_changed for record in self._records),
            world_events=len(self._world_log.events),
        )

    def _validate_runtime_state(self) -> None:
        if self._status is RuntimeStatus.ENDED and self._end_reason is None:
            raise RuntimeLifecycleError("ended runtime must have an end reason")
        if self._status is not RuntimeStatus.ENDED and self._end_reason is not None:
            raise RuntimeLifecycleError("active runtime cannot have an end reason")
        if len(self._records) != self._world_state.tick:
            raise RuntimeLifecycleError("runtime records must match the world tick")
        for expected_tick, record in enumerate(self._records, start=1):
            if record.tick != expected_tick:
                raise RuntimeLifecycleError("runtime records must have continuous ticks")
