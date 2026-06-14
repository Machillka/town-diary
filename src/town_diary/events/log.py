"""Append-only objective WorldEvent log and JSONL persistence."""

from collections.abc import Mapping
import json
from pathlib import Path

from town_diary.core.contracts import EventFact, FactVisibility, TimeBlock, WorldEvent
from town_diary.core.errors import SnapshotValidationError, TownDiaryError
from town_diary.core.ids import ActionId, AgentId, EventId, LocationId
from town_diary.core.schema import SUPPORTED_SCHEMA_VERSIONS


class WorldLogError(TownDiaryError):
    """Raised when objective event ordering or persistence is invalid."""


class WorldLog:
    """Environment-owned append-only objective event sequence."""

    def __init__(self, events: tuple[WorldEvent, ...] = ()) -> None:
        self._events: list[WorldEvent] = []
        self._event_ids: set[EventId] = set()
        for event in events:
            self.append(event)

    @property
    def events(self) -> tuple[WorldEvent, ...]:
        return tuple(self._events)

    def append(self, event: WorldEvent) -> None:
        if event.event_id in self._event_ids:
            raise WorldLogError(f"duplicate event id: {event.event_id}")
        if self._events and _event_sequence(event.event_id) <= _event_sequence(
            self._events[-1].event_id
        ):
            raise WorldLogError("event IDs must be appended in increasing order")
        self._events.append(event)
        self._event_ids.add(event.event_id)

    def truncate(self, length: int) -> None:
        if not isinstance(length, int) or length < 0 or length > len(self._events):
            raise ValueError("world log truncate length is invalid")
        del self._events[length:]
        self._event_ids = {event.event_id for event in self._events}

    def to_dicts(self) -> list[dict[str, object]]:
        return [world_event_to_dict(event) for event in self._events]

    @classmethod
    def from_dicts(cls, values: object) -> "WorldLog":
        if not isinstance(values, list):
            raise SnapshotValidationError("world log must be a list")
        return cls(tuple(world_event_from_dict(value) for value in values))

    def save_jsonl(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("x", encoding="utf-8") as file:
                for event in self._events:
                    file.write(
                        json.dumps(
                            world_event_to_dict(event),
                            ensure_ascii=False,
                            sort_keys=True,
                        )
                        + "\n"
                    )
        except FileExistsError as error:
            raise WorldLogError(f"world log already exists: {target}") from error

    @classmethod
    def load_jsonl(cls, path: str | Path) -> "WorldLog":
        target = Path(path)
        try:
            values = [
                json.loads(line)
                for line in target.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except FileNotFoundError as error:
            raise WorldLogError(f"world log does not exist: {target}") from error
        except json.JSONDecodeError as error:
            raise SnapshotValidationError(f"world log is not valid JSONL: {target}") from error
        return cls.from_dicts(values)


def world_event_to_dict(event: WorldEvent) -> dict[str, object]:
    return {
        "event_id": str(event.event_id),
        "run_id": event.run_id,
        "day": event.day,
        "time_block": event.time_block.value,
        "location_id": str(event.location_id),
        "event_type": event.event_type,
        "participants": [str(agent_id) for agent_id in event.participants],
        "summary": event.summary,
        "facts": [
            {
                "name": fact.name,
                "value": fact.value,
                "visibility": fact.visibility.value,
            }
            for fact in event.facts
        ],
        "source_action_id": (
            str(event.source_action_id) if event.source_action_id is not None else None
        ),
        "schema_version": event.schema_version,
    }


def world_event_from_dict(value: object) -> WorldEvent:
    if not isinstance(value, Mapping):
        raise SnapshotValidationError("world event must be a mapping")
    required = {
        "event_id",
        "run_id",
        "day",
        "time_block",
        "location_id",
        "event_type",
        "participants",
        "summary",
        "facts",
        "source_action_id",
        "schema_version",
    }
    missing = sorted(required.difference(value))
    if missing:
        raise SnapshotValidationError(f"world event missing fields: {', '.join(missing)}")
    if value["schema_version"] not in SUPPORTED_SCHEMA_VERSIONS:
        raise SnapshotValidationError(
            f"unsupported world event schema_version: {value['schema_version']}"
        )
    if not isinstance(value["day"], int) or value["day"] < 1:
        raise SnapshotValidationError("world event day must be positive")
    participants = value["participants"]
    facts_value = value["facts"]
    if not isinstance(participants, list) or not isinstance(facts_value, list):
        raise SnapshotValidationError("world event participants and facts must be lists")
    try:
        facts: list[EventFact] = []
        for fact in facts_value:
            if not isinstance(fact, Mapping):
                raise SnapshotValidationError("world event fact must be a mapping")
            facts.append(
                EventFact(
                    name=str(fact["name"]),
                    value=fact["value"],
                    visibility=FactVisibility(fact["visibility"]),
                )
            )
        return WorldEvent(
            event_id=EventId(str(value["event_id"])),
            run_id=str(value["run_id"]),
            day=value["day"],
            time_block=TimeBlock(value["time_block"]),
            location_id=LocationId(str(value["location_id"])),
            event_type=str(value["event_type"]),
            participants=tuple(AgentId(str(item)) for item in participants),
            summary=str(value["summary"]),
            facts=tuple(facts),
            source_action_id=(
                ActionId(str(value["source_action_id"]))
                if value["source_action_id"] is not None
                else None
            ),
            schema_version=str(value["schema_version"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise SnapshotValidationError("world event is invalid") from error


def _event_sequence(event_id: EventId) -> int:
    value = str(event_id)
    try:
        prefix, sequence = value.rsplit("_", 1)
        if prefix != "event":
            raise ValueError
        return int(sequence)
    except ValueError as error:
        raise WorldLogError(f"invalid event id: {event_id}") from error
