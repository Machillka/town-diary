from dataclasses import FrozenInstanceError

import pytest

from town_diary.core.contracts import (
    EventFact,
    FactVisibility,
    TimeBlock,
    Weather,
    WorldEvent,
)
from town_diary.core.ids import ActionId, AgentId, EventId, LocationId, is_stable_static_id
from town_diary.core.schema import SCHEMA_VERSION


def test_core_contracts_are_immutable_and_versioned() -> None:
    event = WorldEvent(
        event_id=EventId("event_000001"),
        day=1,
        time_block=TimeBlock.MORNING,
        location_id=LocationId("cafe"),
        event_type="work",
        participants=(AgentId("cafe_owner"),),
        summary="The cafe owner opened the cafe.",
        facts=(
            EventFact("opened", True),
            EventFact("private_reason", "habit", FactVisibility.HIDDEN),
        ),
        source_action_id=ActionId("action_000001"),
    )

    assert event.schema_version == SCHEMA_VERSION
    assert event.facts[1].visibility is FactVisibility.HIDDEN
    with pytest.raises(FrozenInstanceError):
        event.day = 2  # type: ignore[misc]


@pytest.mark.parametrize("value", ["novelist", "cafe_owner", "station_2"])
def test_static_ids_accept_lower_snake_case(value: str) -> None:
    assert is_stable_static_id(value)


@pytest.mark.parametrize("value", ["CafeOwner", "cafe-owner", "", "2_station"])
def test_static_ids_reject_unstable_formats(value: str) -> None:
    assert not is_stable_static_id(value)


def test_contract_enums_define_the_mvp_values() -> None:
    assert tuple(TimeBlock) == (
        TimeBlock.MORNING,
        TimeBlock.NOON,
        TimeBlock.AFTERNOON,
        TimeBlock.EVENING,
        TimeBlock.NIGHT,
    )
    assert set(Weather) == {
        Weather.CLEAR,
        Weather.CLOUDY,
        Weather.LIGHT_RAIN,
        Weather.HEAVY_RAIN,
    }
