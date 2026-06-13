"""Environment-owned deterministic weather state machine."""

from collections.abc import Mapping
from dataclasses import dataclass

from town_diary.core.config import WeatherEffectConfig, WeatherTransitionConfig, WorldConfig
from town_diary.core.contracts import TimeBlock, Weather
from town_diary.core.errors import SnapshotValidationError
from town_diary.core.random import DeterministicRandom
from town_diary.core.schema import SCHEMA_VERSION, SUPPORTED_SCHEMA_VERSIONS


@dataclass(frozen=True, slots=True)
class WeatherEffects:
    movement_multiplier: float
    foot_traffic_multiplier: float
    observation_multiplier: float
    rumor_multiplier: float

    @classmethod
    def from_config(cls, config: WeatherEffectConfig) -> "WeatherEffects":
        return cls(
            movement_multiplier=config.movement_multiplier,
            foot_traffic_multiplier=config.foot_traffic_multiplier,
            observation_multiplier=config.observation_multiplier,
            rumor_multiplier=config.rumor_multiplier,
        )


@dataclass(frozen=True, slots=True)
class WeatherChange:
    day: int
    time_block: TimeBlock
    previous: Weather
    current: Weather


@dataclass(frozen=True, slots=True)
class WeatherSnapshot:
    current: Weather
    last_transition_day: int | None
    changes: tuple[WeatherChange, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "current": self.current.value,
            "last_transition_day": self.last_transition_day,
            "changes": [
                {
                    "day": change.day,
                    "time_block": change.time_block.value,
                    "previous": change.previous.value,
                    "current": change.current.value,
                }
                for change in self.changes
            ],
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, snapshot: object) -> "WeatherSnapshot":
        if not isinstance(snapshot, Mapping):
            raise SnapshotValidationError("weather snapshot must be a mapping")
        try:
            current = Weather(snapshot["current"])
            last_transition_day = snapshot["last_transition_day"]
            raw_changes = snapshot["changes"]
            schema_version = snapshot["schema_version"]
        except KeyError as error:
            raise SnapshotValidationError(
                f"weather snapshot missing field: {error.args[0]}"
            ) from error
        except (ValueError, TypeError) as error:
            raise SnapshotValidationError("weather snapshot has an invalid weather") from error
        if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise SnapshotValidationError(
                f"unsupported weather schema_version: {schema_version}"
            )
        if last_transition_day is not None and (
            not isinstance(last_transition_day, int) or last_transition_day < 1
        ):
            raise SnapshotValidationError(
                "weather last_transition_day must be null or a positive integer"
            )
        if not isinstance(raw_changes, list):
            raise SnapshotValidationError("weather changes must be a list")
        changes: list[WeatherChange] = []
        for raw in raw_changes:
            if not isinstance(raw, Mapping):
                raise SnapshotValidationError("weather change must be a mapping")
            try:
                day = raw["day"]
                if not isinstance(day, int) or day < 1:
                    raise SnapshotValidationError(
                        "weather change day must be a positive integer"
                    )
                changes.append(
                    WeatherChange(
                        day=day,
                        time_block=TimeBlock(raw["time_block"]),
                        previous=Weather(raw["previous"]),
                        current=Weather(raw["current"]),
                    )
                )
            except (KeyError, ValueError, TypeError) as error:
                raise SnapshotValidationError("weather change is invalid") from error
        return cls(
            current=current,
            last_transition_day=last_transition_day,
            changes=tuple(changes),
            schema_version=str(schema_version),
        )


class WeatherSystem:
    """Mutable weather system that must be advanced by Environment."""

    def __init__(
        self,
        *,
        config: WorldConfig,
        random: DeterministicRandom,
        snapshot: WeatherSnapshot | None = None,
    ) -> None:
        self._transition_time = config.weather_transition_time
        self._transitions = _group_transitions(config.weather_transitions)
        self._effects = {
            effect.weather: WeatherEffects.from_config(effect)
            for effect in config.weather_effects
        }
        self._random = random
        self._current = snapshot.current if snapshot else config.initial_weather
        if self._current not in self._transitions or self._current not in self._effects:
            raise SnapshotValidationError(
                f"weather snapshot current state is not configured: {self._current}"
            )
        self._last_transition_day = snapshot.last_transition_day if snapshot else None
        self._changes = list(snapshot.changes if snapshot else ())

    @property
    def current(self) -> Weather:
        return self._current

    @property
    def effects(self) -> WeatherEffects:
        return self._effects[self._current]

    def advance(self, *, day: int, time_block: TimeBlock) -> WeatherChange | None:
        """Transition at most once per day when Environment calls the configured block."""
        if day < 1:
            raise ValueError("day must be greater than zero")
        if time_block is not self._transition_time or self._last_transition_day == day:
            return None
        options = self._transitions[self._current]
        next_weather = self._random.weighted_choice(
            [transition.target for transition in options],
            [transition.weight for transition in options],
        )
        change = WeatherChange(
            day=day,
            time_block=time_block,
            previous=self._current,
            current=next_weather,
        )
        self._current = next_weather
        self._last_transition_day = day
        self._changes.append(change)
        return change

    def movement_score(self, base_score: float) -> float:
        return base_score * self.effects.movement_multiplier

    def snapshot(self) -> WeatherSnapshot:
        return WeatherSnapshot(
            current=self._current,
            last_transition_day=self._last_transition_day,
            changes=tuple(self._changes),
        )

    @classmethod
    def from_snapshot(
        cls,
        *,
        config: WorldConfig,
        random: DeterministicRandom,
        snapshot: WeatherSnapshot | object,
    ) -> "WeatherSystem":
        parsed = (
            snapshot if isinstance(snapshot, WeatherSnapshot) else WeatherSnapshot.from_dict(snapshot)
        )
        return cls(config=config, random=random, snapshot=parsed)


def _group_transitions(
    transitions: tuple[WeatherTransitionConfig, ...],
) -> dict[Weather, tuple[WeatherTransitionConfig, ...]]:
    grouped: dict[Weather, list[WeatherTransitionConfig]] = {}
    for transition in transitions:
        grouped.setdefault(transition.source, []).append(transition)
    return {weather: tuple(options) for weather, options in grouped.items()}
