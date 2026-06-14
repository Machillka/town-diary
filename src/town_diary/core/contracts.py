"""Immutable data exchanged across the core architecture boundaries."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias

from town_diary.core.ids import (
    ActionId,
    AgentId,
    EventId,
    ExperienceId,
    LocationId,
)
from town_diary.core.schema import SCHEMA_VERSION

Scalar: TypeAlias = str | int | float | bool | None


class TimeBlock(StrEnum):
    MORNING = "morning"
    NOON = "noon"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"


class Weather(StrEnum):
    CLEAR = "clear"
    CLOUDY = "cloudy"
    LIGHT_RAIN = "light_rain"
    HEAVY_RAIN = "heavy_rain"


class PerceptionMode(StrEnum):
    DIRECT = "direct"
    PARTICIPANT = "participant"
    RUMOR = "rumor"
    UNCLEAR = "unclear"


class FactVisibility(StrEnum):
    PUBLIC = "public"
    PARTICIPANT = "participant"
    HIDDEN = "hidden"


@dataclass(frozen=True, slots=True)
class NamedValue:
    """Small immutable key/value field used in proposals and snapshots."""

    name: str
    value: Scalar


@dataclass(frozen=True, slots=True)
class EventFact:
    """Structured event fact with an explicit visibility boundary."""

    name: str
    value: Scalar
    visibility: FactVisibility = FactVisibility.PUBLIC


@dataclass(frozen=True, slots=True)
class LocationStateSnapshot:
    """Read-only objective state for one location."""

    location_id: LocationId
    is_open: bool
    is_public: bool
    is_core_narrative: bool


@dataclass(frozen=True, slots=True)
class AgentStateSnapshot:
    """Read-only objective state for one agent."""

    agent_id: AgentId
    location_id: LocationId
    body_state: tuple[NamedValue, ...] = ()


@dataclass(frozen=True, slots=True)
class WorldSnapshot:
    """Deeply immutable objective world projection."""

    day: int
    time_block: TimeBlock
    weather: Weather
    tick: int
    location_states: tuple[LocationStateSnapshot, ...] = ()
    agent_states: tuple[AgentStateSnapshot, ...] = ()
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class WorldEvent:
    """Structured objective fact committed by Environment."""

    event_id: EventId
    day: int
    time_block: TimeBlock
    location_id: LocationId
    event_type: str
    participants: tuple[AgentId, ...]
    summary: str
    facts: tuple[EventFact, ...]
    source_action_id: ActionId | None = None
    run_id: str = ""
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class ObservedEvent:
    """One agent's limited perception of a world event."""

    source_event_id: EventId
    observer_id: AgentId
    day: int
    time_block: TimeBlock
    description: str
    mode: PerceptionMode
    certainty: float
    perceived_facts: tuple[EventFact, ...] = ()
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class Observation:
    """The only objective-world input allowed for an Agent decision."""

    observer_id: AgentId
    day: int
    time_block: TimeBlock
    location_id: LocationId
    weather: Weather
    body_state: tuple[NamedValue, ...] = ()
    visible_agents: tuple[AgentId, ...] = ()
    visible_events: tuple[ObservedEvent, ...] = ()
    heard_rumors: tuple[ObservedEvent, ...] = ()
    available_actions: tuple[str, ...] = ()
    available_location_ids: tuple[LocationId, ...] = ()
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class ActionProposal:
    """Agent intent submitted for Environment validation."""

    action_id: ActionId
    agent_id: AgentId
    action_type: str
    reason: str
    target_location_id: LocationId | None = None
    target_agent_id: AgentId | None = None
    parameters: tuple[NamedValue, ...] = ()
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class ActionResult:
    """Environment result after validating and committing a proposal."""

    action_id: ActionId
    success: bool
    reason: str
    events: tuple[WorldEvent, ...] = ()
    effects: tuple[NamedValue, ...] = ()
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class Experience:
    """Novelist interpretation derived from already-known material."""

    experience_id: ExperienceId
    day: int
    time_block: TimeBlock
    source_event_ids: tuple[EventId, ...]
    feeling: str
    interpretation: str
    certainty: float
    schema_version: str = SCHEMA_VERSION
