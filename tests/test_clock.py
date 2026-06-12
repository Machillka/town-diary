import pytest

from town_diary.core.contracts import TimeBlock
from town_diary.core.errors import SnapshotValidationError
from town_diary.simulation.clock import ClockSnapshot, WorldClock


def test_clock_starts_at_day_one_morning() -> None:
    clock = WorldClock()

    assert clock.day == 1
    assert clock.time_block is TimeBlock.MORNING
    assert not clock.is_day_end()
    assert not clock.is_week_end()


def test_clock_advances_through_five_time_blocks() -> None:
    clock = WorldClock()

    observed = [clock.time_block]
    for _ in range(4):
        observed.append(clock.advance().time_block)

    assert observed == list(TimeBlock)
    assert clock.day == 1
    assert clock.is_day_end()

    clock.advance()
    assert clock.day == 2
    assert clock.time_block is TimeBlock.MORNING


def test_thirty_five_advances_cover_seven_complete_days() -> None:
    clock = WorldClock()

    for _ in range(34):
        clock.advance()

    assert clock.day == 7
    assert clock.time_block is TimeBlock.NIGHT
    assert clock.is_week_end()

    clock.advance()
    assert clock.day == 8
    assert clock.time_block is TimeBlock.MORNING


def test_clock_snapshot_round_trip() -> None:
    clock = WorldClock(start_day=3, start_time_block=TimeBlock.AFTERNOON)
    snapshot_dict = clock.snapshot().to_dict()
    restored = WorldClock.from_snapshot(snapshot_dict)

    assert restored.snapshot() == ClockSnapshot(day=3, time_block=TimeBlock.AFTERNOON)


def test_multiple_consumers_receive_the_same_world_time_snapshot() -> None:
    clock = WorldClock(start_day=4, start_time_block=TimeBlock.EVENING)

    first_observer_snapshot = clock.snapshot()
    second_observer_snapshot = clock.snapshot()

    assert first_observer_snapshot == second_observer_snapshot


def test_clock_rejects_invalid_snapshot() -> None:
    with pytest.raises(SnapshotValidationError, match="invalid clock time_block"):
        WorldClock.from_snapshot(
            {"day": 1, "time_block": "midnight", "schema_version": "0.1"}
        )
