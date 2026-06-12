"""Environment-owned world clock."""

from dataclasses import dataclass
from collections.abc import Mapping

from town_diary.core.contracts import TimeBlock
from town_diary.core.errors import SnapshotValidationError
from town_diary.core.schema import SCHEMA_VERSION, SUPPORTED_SCHEMA_VERSIONS

TIME_BLOCKS = tuple(TimeBlock)


@dataclass(frozen=True, slots=True)
class ClockSnapshot:
    """Immutable, serializable clock state."""

    day: int
    time_block: TimeBlock
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "day": self.day,
            "time_block": self.time_block.value,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, snapshot: object) -> "ClockSnapshot":
        if not isinstance(snapshot, Mapping):
            raise SnapshotValidationError("clock snapshot must be a mapping")
        try:
            day = snapshot["day"]
            time_block = snapshot["time_block"]
            schema_version = snapshot["schema_version"]
        except KeyError as error:
            raise SnapshotValidationError(f"clock snapshot missing field: {error.args[0]}") from error
        if not isinstance(day, int) or day < 1:
            raise SnapshotValidationError("clock day must be an integer greater than zero")
        if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise SnapshotValidationError(f"unsupported clock schema_version: {schema_version}")
        try:
            parsed_time_block = TimeBlock(time_block)
        except (ValueError, TypeError) as error:
            raise SnapshotValidationError(f"invalid clock time_block: {time_block}") from error
        return cls(day=day, time_block=parsed_time_block, schema_version=str(schema_version))


class WorldClock:
    """Mutable world time that must be owned and advanced by Environment."""

    def __init__(
        self,
        *,
        start_day: int = 1,
        start_time_block: TimeBlock = TimeBlock.MORNING,
    ) -> None:
        if start_day < 1:
            raise ValueError("start_day must be greater than zero")
        self._day = start_day
        self._time_block = TimeBlock(start_time_block)

    @property
    def day(self) -> int:
        return self._day

    @property
    def time_block(self) -> TimeBlock:
        return self._time_block

    def is_day_end(self) -> bool:
        """Return whether the current block is the final block of a day."""
        return self._time_block is TimeBlock.NIGHT

    def is_week_end(self, *, week_length: int = 7) -> bool:
        """Return whether the current block ends the requested week."""
        if week_length < 1:
            raise ValueError("week_length must be greater than zero")
        return self._day % week_length == 0 and self.is_day_end()

    def advance(self) -> ClockSnapshot:
        """Advance one time block and return the new immutable snapshot."""
        index = TIME_BLOCKS.index(self._time_block)
        if index == len(TIME_BLOCKS) - 1:
            self._day += 1
            self._time_block = TimeBlock.MORNING
        else:
            self._time_block = TIME_BLOCKS[index + 1]
        return self.snapshot()

    def snapshot(self) -> ClockSnapshot:
        return ClockSnapshot(day=self._day, time_block=self._time_block)

    @classmethod
    def from_snapshot(cls, snapshot: ClockSnapshot | object) -> "WorldClock":
        parsed = snapshot if isinstance(snapshot, ClockSnapshot) else ClockSnapshot.from_dict(snapshot)
        return cls(start_day=parsed.day, start_time_block=parsed.time_block)
