"""Project-owned deterministic pseudo-random number generator."""

from collections.abc import Sequence
from typing import TypeVar

from town_diary.core.errors import SnapshotValidationError

T = TypeVar("T")
_MASK_64 = (1 << 64) - 1
_MASK_32 = (1 << 32) - 1


class DeterministicRandom:
    """Small PCG32 generator with JSON-compatible snapshots."""

    _MULTIPLIER = 6364136223846793005
    _DEFAULT_INCREMENT = 1442695040888963407

    def __init__(self, seed: int, *, state: int | None = None, increment: int | None = None) -> None:
        if not isinstance(seed, int):
            raise TypeError("seed must be an integer")
        self.seed = seed
        self._increment = (
            self._DEFAULT_INCREMENT if increment is None else increment
        ) & _MASK_64
        self._increment |= 1
        if state is None:
            self._state = 0
            self._next_uint32()
            self._state = (self._state + (seed & _MASK_64)) & _MASK_64
            self._next_uint32()
        else:
            self._state = state & _MASK_64

    def random(self) -> float:
        """Return a deterministic float in the half-open interval [0, 1)."""
        return self._next_uint32() / float(1 << 32)

    def randint(self, start: int, end: int) -> int:
        """Return a deterministic integer in the inclusive interval."""
        if end < start:
            raise ValueError("end must be greater than or equal to start")
        return start + self._randbelow(end - start + 1)

    def choice(self, values: Sequence[T]) -> T:
        """Choose one value from a non-empty sequence."""
        if not values:
            raise ValueError("cannot choose from an empty sequence")
        return values[self._randbelow(len(values))]

    def weighted_choice(self, values: Sequence[T], weights: Sequence[float]) -> T:
        """Choose one value according to positive numeric weights."""
        if len(values) != len(weights) or not values:
            raise ValueError("values and weights must have the same non-zero length")
        if any(weight < 0 for weight in weights):
            raise ValueError("weights must not be negative")
        total = float(sum(weights))
        if total <= 0:
            raise ValueError("at least one weight must be positive")
        threshold = self.random() * total
        cumulative = 0.0
        for value, weight in zip(values, weights, strict=True):
            cumulative += weight
            if threshold < cumulative:
                return value
        return values[-1]

    def snapshot(self) -> dict[str, int]:
        """Return JSON-compatible state for checkpointing."""
        return {
            "seed": self.seed,
            "state": self._state,
            "increment": self._increment,
        }

    def restore(self, snapshot: object) -> None:
        """Restore this shared generator in place for transaction rollback."""
        restored = self.from_snapshot(snapshot)
        self.seed = restored.seed
        self._state = restored._state
        self._increment = restored._increment

    @classmethod
    def from_snapshot(cls, snapshot: object) -> "DeterministicRandom":
        if not isinstance(snapshot, dict):
            raise SnapshotValidationError("random snapshot must be a mapping")
        try:
            seed = snapshot["seed"]
            state = snapshot["state"]
            increment = snapshot["increment"]
        except KeyError as error:
            raise SnapshotValidationError(f"random snapshot missing field: {error.args[0]}") from error
        if not all(isinstance(value, int) for value in (seed, state, increment)):
            raise SnapshotValidationError("random snapshot fields must be integers")
        return cls(seed, state=state, increment=increment)

    def _randbelow(self, upper_bound: int) -> int:
        if upper_bound <= 0:
            raise ValueError("upper_bound must be positive")
        if upper_bound > 1 << 32:
            raise ValueError("upper_bound must not exceed 2**32")
        threshold = (1 << 32) % upper_bound
        while True:
            candidate = self._next_uint32()
            if candidate >= threshold:
                return candidate % upper_bound

    def _next_uint32(self) -> int:
        old_state = self._state
        self._state = (
            old_state * self._MULTIPLIER + self._increment
        ) & _MASK_64
        xorshifted = (((old_state >> 18) ^ old_state) >> 27) & _MASK_32
        rotation = (old_state >> 59) & 31
        return (
            (xorshifted >> rotation)
            | (xorshifted << ((-rotation) & 31))
        ) & _MASK_32
