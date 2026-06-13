"""Environment-owned objective world state and immutable snapshots."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from town_diary.core.config import ConfigBundle
from town_diary.core.contracts import AgentStateSnapshot, NamedValue, WorldSnapshot
from town_diary.core.errors import SnapshotValidationError, TownDiaryError
from town_diary.core.ids import AgentId, LocationId
from town_diary.core.random import DeterministicRandom
from town_diary.core.schema import SCHEMA_VERSION, SUPPORTED_SCHEMA_VERSIONS
from town_diary.simulation.clock import ClockSnapshot, WorldClock
from town_diary.simulation.location import LocationSystem
from town_diary.simulation.weather import WeatherSnapshot, WeatherSystem


class WorldStateInvariantError(TownDiaryError):
    """Raised when objective world state violates an invariant."""


@dataclass(frozen=True, slots=True)
class WorldStateCheckpoint:
    tick: int
    clock: ClockSnapshot
    weather: WeatherSnapshot
    agent_locations: tuple[tuple[AgentId, LocationId], ...]
    agent_body_states: tuple[tuple[AgentId, tuple[NamedValue, ...]], ...]
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "tick": self.tick,
            "clock": self.clock.to_dict(),
            "weather": self.weather.to_dict(),
            "agent_locations": {
                str(agent_id): str(location_id)
                for agent_id, location_id in self.agent_locations
            },
            "agent_body_states": {
                str(agent_id): {
                    value.name: value.value for value in body_state
                }
                for agent_id, body_state in self.agent_body_states
            },
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, checkpoint: object) -> "WorldStateCheckpoint":
        return _checkpoint_from_dict(checkpoint)


class WorldState:
    """Unique mutable source of objective world truth."""

    def __init__(
        self,
        *,
        clock: WorldClock,
        weather: WeatherSystem,
        locations: LocationSystem,
        agent_locations: Mapping[AgentId, LocationId],
        agent_body_states: Mapping[AgentId, Mapping[str, int | float]],
        tick: int = 0,
    ) -> None:
        self._clock = clock
        self._weather = weather
        self._locations = locations
        self._agent_locations = {
            AgentId(str(agent_id)): LocationId(str(location_id))
            for agent_id, location_id in agent_locations.items()
        }
        self._agent_body_states = {
            AgentId(str(agent_id)): dict(body_state)
            for agent_id, body_state in agent_body_states.items()
        }
        self._tick = tick
        self.validate_invariants()

    @classmethod
    def from_config(
        cls,
        *,
        config: ConfigBundle,
        random: DeterministicRandom,
        default_body_state: Mapping[str, int | float] | None = None,
    ) -> "WorldState":
        body_state = dict(default_body_state or {"energy": 100, "hunger": 0})
        return cls(
            clock=WorldClock(),
            weather=WeatherSystem(config=config.world, random=random),
            locations=LocationSystem.from_config(config.locations),
            agent_locations={
                agent.id: agent.initial_location_id for agent in config.agents
            },
            agent_body_states={agent.id: body_state for agent in config.agents},
        )

    @property
    def clock(self) -> WorldClock:
        """Environment-only mutable clock access."""
        return self._clock

    @property
    def weather(self) -> WeatherSystem:
        """Environment-only mutable weather access."""
        return self._weather

    @property
    def locations(self) -> LocationSystem:
        return self._locations

    @property
    def tick(self) -> int:
        return self._tick

    def location_of(self, agent_id: AgentId | str) -> LocationId:
        try:
            return self._agent_locations[AgentId(str(agent_id))]
        except KeyError as error:
            raise KeyError(f"unknown agent: {agent_id}") from error

    def body_state_of(self, agent_id: AgentId | str) -> tuple[NamedValue, ...]:
        try:
            state = self._agent_body_states[AgentId(str(agent_id))]
        except KeyError as error:
            raise KeyError(f"unknown agent: {agent_id}") from error
        return _named_values(state)

    def move_agent(self, agent_id: AgentId | str, location_id: LocationId | str) -> None:
        """Environment mutation boundary for objective position."""
        resolved_agent = AgentId(str(agent_id))
        resolved_location = LocationId(str(location_id))
        if resolved_agent not in self._agent_locations:
            raise WorldStateInvariantError(f"unknown agent: {agent_id}")
        if not self._locations.exists(resolved_location):
            raise WorldStateInvariantError(f"unknown location: {location_id}")
        self._agent_locations[resolved_agent] = resolved_location
        self.validate_invariants()

    def set_body_state(
        self,
        agent_id: AgentId | str,
        body_state: Mapping[str, int | float],
    ) -> None:
        """Environment mutation boundary for objective body state."""
        resolved_agent = AgentId(str(agent_id))
        if resolved_agent not in self._agent_locations:
            raise WorldStateInvariantError(f"unknown agent: {agent_id}")
        candidate = dict(body_state)
        _validate_body_state(resolved_agent, candidate)
        self._agent_body_states[resolved_agent] = candidate

    def increment_tick(self) -> None:
        self._tick += 1

    def snapshot(self) -> WorldSnapshot:
        return WorldSnapshot(
            day=self._clock.day,
            time_block=self._clock.time_block,
            weather=self._weather.current,
            tick=self._tick,
            location_states=self._locations.snapshots(self._clock.time_block),
            agent_states=tuple(
                AgentStateSnapshot(
                    agent_id=agent_id,
                    location_id=self._agent_locations[agent_id],
                    body_state=_named_values(self._agent_body_states[agent_id]),
                )
                for agent_id in sorted(self._agent_locations, key=str)
            ),
        )

    def checkpoint(self) -> WorldStateCheckpoint:
        return WorldStateCheckpoint(
            tick=self._tick,
            clock=self._clock.snapshot(),
            weather=self._weather.snapshot(),
            agent_locations=tuple(
                (agent_id, self._agent_locations[agent_id])
                for agent_id in sorted(self._agent_locations, key=str)
            ),
            agent_body_states=tuple(
                (agent_id, _named_values(self._agent_body_states[agent_id]))
                for agent_id in sorted(self._agent_body_states, key=str)
            ),
        )

    @classmethod
    def from_checkpoint(
        cls,
        *,
        checkpoint: WorldStateCheckpoint | object,
        config: ConfigBundle,
        random: DeterministicRandom,
    ) -> "WorldState":
        parsed = (
            checkpoint
            if isinstance(checkpoint, WorldStateCheckpoint)
            else _checkpoint_from_dict(checkpoint)
        )
        expected_agent_ids = {agent.id for agent in config.agents}
        checkpoint_agent_ids = {agent_id for agent_id, _ in parsed.agent_locations}
        checkpoint_body_ids = {agent_id for agent_id, _ in parsed.agent_body_states}
        if (
            checkpoint_agent_ids != expected_agent_ids
            or checkpoint_body_ids != expected_agent_ids
        ):
            raise SnapshotValidationError(
                "world checkpoint agent IDs must match the active configuration"
            )
        return cls(
            clock=WorldClock.from_snapshot(parsed.clock),
            weather=WeatherSystem.from_snapshot(
                config=config.world,
                random=random,
                snapshot=parsed.weather,
            ),
            locations=LocationSystem.from_config(config.locations),
            agent_locations=dict(parsed.agent_locations),
            agent_body_states={
                agent_id: {value.name: value.value for value in body_state}
                for agent_id, body_state in parsed.agent_body_states
            },
            tick=parsed.tick,
        )

    def validate_invariants(self) -> None:
        if not isinstance(self._tick, int) or self._tick < 0:
            raise WorldStateInvariantError("tick must be a non-negative integer")
        agent_ids = set(self._agent_locations)
        if agent_ids != set(self._agent_body_states):
            raise WorldStateInvariantError(
                "agent_locations and agent_body_states must contain the same agents"
            )
        for agent_id, location_id in self._agent_locations.items():
            if not self._locations.exists(location_id):
                raise WorldStateInvariantError(
                    f"agent {agent_id} references unknown location {location_id}"
                )
        for agent_id, state in self._agent_body_states.items():
            _validate_body_state(agent_id, state)


def _named_values(values: Mapping[str, Any]) -> tuple[NamedValue, ...]:
    return tuple(
        NamedValue(name=name, value=values[name])
        for name in sorted(values)
    )


def _validate_body_state(
    agent_id: AgentId,
    state: Mapping[str, object],
) -> None:
    for name, value in state.items():
        if not isinstance(name, str) or not name:
            raise WorldStateInvariantError(
                f"agent {agent_id} has an invalid body state name"
            )
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise WorldStateInvariantError(
                f"agent {agent_id} body state {name} must be numeric"
            )


def _checkpoint_from_dict(checkpoint: object) -> WorldStateCheckpoint:
    if not isinstance(checkpoint, Mapping):
        raise SnapshotValidationError("world checkpoint must be a mapping")
    try:
        tick = checkpoint["tick"]
        schema_version = checkpoint["schema_version"]
        raw_locations = checkpoint["agent_locations"]
        raw_body_states = checkpoint["agent_body_states"]
        raw_clock = checkpoint["clock"]
        raw_weather = checkpoint["weather"]
    except KeyError as error:
        raise SnapshotValidationError(
            f"world checkpoint missing field: {error.args[0]}"
        ) from error
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise SnapshotValidationError(
            f"unsupported world checkpoint schema_version: {schema_version}"
        )
    if not isinstance(tick, int) or tick < 0:
        raise SnapshotValidationError("world checkpoint tick must be non-negative")
    if not isinstance(raw_locations, Mapping) or not isinstance(raw_body_states, Mapping):
        raise SnapshotValidationError(
            "world checkpoint agent state fields must be mappings"
        )
    body_states: list[tuple[AgentId, tuple[NamedValue, ...]]] = []
    for agent_id, state in raw_body_states.items():
        if not isinstance(agent_id, str) or not isinstance(state, Mapping):
            raise SnapshotValidationError("world checkpoint body state is invalid")
        body_states.append((AgentId(agent_id), _named_values(state)))
    return WorldStateCheckpoint(
        tick=tick,
        clock=ClockSnapshot.from_dict(raw_clock),
        weather=WeatherSnapshot.from_dict(raw_weather),
        agent_locations=tuple(
            (AgentId(str(agent_id)), LocationId(str(location_id)))
            for agent_id, location_id in sorted(raw_locations.items())
        ),
        agent_body_states=tuple(sorted(body_states, key=lambda item: str(item[0]))),
        schema_version=str(schema_version),
    )
