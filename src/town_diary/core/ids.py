"""Stable identifier types, validation, and deterministic generation."""

from collections import defaultdict
from collections.abc import Mapping
import re
from typing import NewType

RunId = NewType("RunId", str)
AgentId = NewType("AgentId", str)
LocationId = NewType("LocationId", str)
EventId = NewType("EventId", str)
ActionId = NewType("ActionId", str)
ExperienceId = NewType("ExperienceId", str)

_STATIC_ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_RUN_ID_PATTERN = re.compile(r"^run_[a-z0-9]+(?:_[a-z0-9]+)*$")
_GENERATED_KINDS = frozenset({"action", "event", "experience"})


def is_stable_static_id(value: object) -> bool:
    """Return whether a configured ID follows lower snake-case rules."""
    return isinstance(value, str) and _STATIC_ID_PATTERN.fullmatch(value) is not None


def is_run_id(value: object) -> bool:
    """Return whether a run ID uses the reserved stable run prefix."""
    return isinstance(value, str) and _RUN_ID_PATTERN.fullmatch(value) is not None


class DeterministicIdGenerator:
    """Generate replayable, unique sequential IDs within one run."""

    def __init__(self, counters: Mapping[str, int] | None = None) -> None:
        self._counters: defaultdict[str, int] = defaultdict(int)
        if counters is not None:
            for kind, counter in counters.items():
                self._validate_kind(kind)
                if not isinstance(counter, int) or counter < 0:
                    raise ValueError("ID counters must be non-negative integers")
                self._counters[kind] = counter

    def next_action_id(self) -> ActionId:
        return ActionId(self._next("action"))

    def next_event_id(self) -> EventId:
        return EventId(self._next("event"))

    def next_experience_id(self) -> ExperienceId:
        return ExperienceId(self._next("experience"))

    def snapshot(self) -> dict[str, int]:
        """Return JSON-compatible generator state."""
        return dict(sorted(self._counters.items()))

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, int]) -> "DeterministicIdGenerator":
        return cls(snapshot)

    def _next(self, kind: str) -> str:
        self._validate_kind(kind)
        self._counters[kind] += 1
        return f"{kind}_{self._counters[kind]:06d}"

    @staticmethod
    def _validate_kind(kind: str) -> None:
        if kind not in _GENERATED_KINDS:
            raise ValueError(f"Unsupported generated ID kind: {kind}")