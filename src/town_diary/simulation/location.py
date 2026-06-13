"""Immutable location topology and time-based opening rules."""

from dataclasses import dataclass

from town_diary.core.config import LocationConfig, OpenRuleConfig
from town_diary.core.contracts import LocationStateSnapshot, TimeBlock
from town_diary.core.ids import LocationId


@dataclass(frozen=True, slots=True)
class OpenRule:
    always: bool
    open_blocks: frozenset[TimeBlock] = frozenset()

    @classmethod
    def from_config(cls, config: OpenRuleConfig) -> "OpenRule":
        return cls(always=config.always, open_blocks=frozenset(config.open_blocks))

    def is_open(self, time_block: TimeBlock) -> bool:
        return self.always or time_block in self.open_blocks


@dataclass(frozen=True, slots=True)
class Location:
    id: LocationId
    name: str
    kind: str
    is_public: bool
    is_core_narrative: bool
    connected_locations: frozenset[LocationId]
    open_rule: OpenRule

    @classmethod
    def from_config(cls, config: LocationConfig) -> "Location":
        return cls(
            id=config.id,
            name=config.name,
            kind=config.kind,
            is_public=config.is_public,
            is_core_narrative=config.is_core_narrative,
            connected_locations=frozenset(config.connected_locations),
            open_rule=OpenRule.from_config(config.open_rule),
        )


class LocationSystem:
    """Read-only topology that Environment uses to validate world movement."""

    def __init__(self, locations: tuple[Location, ...]) -> None:
        self._locations = {location.id: location for location in locations}
        if len(self._locations) != len(locations):
            raise ValueError("location IDs must be unique")

    @classmethod
    def from_config(cls, configs: tuple[LocationConfig, ...]) -> "LocationSystem":
        return cls(tuple(Location.from_config(config) for config in configs))

    def exists(self, location_id: LocationId | str) -> bool:
        return LocationId(str(location_id)) in self._locations

    def get(self, location_id: LocationId | str) -> Location:
        try:
            return self._locations[LocationId(str(location_id))]
        except KeyError as error:
            raise KeyError(f"unknown location: {location_id}") from error

    def are_connected(
        self,
        from_location_id: LocationId | str,
        to_location_id: LocationId | str,
    ) -> bool:
        if not self.exists(from_location_id) or not self.exists(to_location_id):
            return False
        return LocationId(str(to_location_id)) in self.get(from_location_id).connected_locations

    def is_open(self, location_id: LocationId | str, time_block: TimeBlock) -> bool:
        return self.get(location_id).open_rule.is_open(time_block)

    def public_locations(self) -> tuple[Location, ...]:
        return tuple(
            location
            for location in self._sorted_locations()
            if location.is_public
        )

    def private_locations(self) -> tuple[Location, ...]:
        return tuple(
            location
            for location in self._sorted_locations()
            if not location.is_public
        )

    def core_narrative_locations(self) -> tuple[Location, ...]:
        return tuple(
            location
            for location in self._sorted_locations()
            if location.is_core_narrative
        )

    def snapshots(self, time_block: TimeBlock) -> tuple[LocationStateSnapshot, ...]:
        return tuple(
            LocationStateSnapshot(
                location_id=location.id,
                is_open=location.open_rule.is_open(time_block),
                is_public=location.is_public,
                is_core_narrative=location.is_core_narrative,
            )
            for location in self._sorted_locations()
        )

    def _sorted_locations(self) -> tuple[Location, ...]:
        return tuple(
            self._locations[location_id]
            for location_id in sorted(self._locations, key=str)
        )
