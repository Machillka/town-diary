"""Deterministic run metadata, random state, and ID state."""

from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from town_diary.core.errors import SnapshotValidationError
from town_diary.core.ids import DeterministicIdGenerator, RunId, is_run_id
from town_diary.core.random import DeterministicRandom
from town_diary.core.schema import SCHEMA_VERSION, SUPPORTED_SCHEMA_VERSIONS


@dataclass(frozen=True, slots=True)
class RunContext:
    """Immutable run identity containing mutable deterministic services."""

    run_id: RunId
    seed: int
    schema_version: str
    config_digest: str
    random: DeterministicRandom
    ids: DeterministicIdGenerator

    @classmethod
    def create(cls, *, seed: int, config: object, run_id: str | None = None) -> "RunContext":
        digest = config_digest(config)
        seed_token = str(seed) if seed >= 0 else f"n{abs(seed)}"
        resolved_run_id = run_id or f"run_{seed_token}_{digest[:12]}"
        if not is_run_id(resolved_run_id):
            raise ValueError("run_id must start with run_ and use lower snake-case")
        return cls(
            run_id=RunId(resolved_run_id),
            seed=seed,
            schema_version=SCHEMA_VERSION,
            config_digest=digest,
            random=DeterministicRandom(seed),
            ids=DeterministicIdGenerator(),
        )

    def to_manifest(self) -> dict[str, object]:
        """Return all metadata required to continue a deterministic run."""
        return {
            "run_id": str(self.run_id),
            "seed": self.seed,
            "schema_version": self.schema_version,
            "config_digest": self.config_digest,
            "random": self.random.snapshot(),
            "ids": self.ids.snapshot(),
        }

    @classmethod
    def from_manifest(cls, manifest: object) -> "RunContext":
        if not isinstance(manifest, Mapping):
            raise SnapshotValidationError("run manifest must be a mapping")
        required = {
            "run_id",
            "seed",
            "schema_version",
            "config_digest",
            "random",
            "ids",
        }
        missing = sorted(required.difference(manifest))
        if missing:
            raise SnapshotValidationError(f"run manifest missing fields: {', '.join(missing)}")
        schema_version = manifest["schema_version"]
        if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise SnapshotValidationError(f"unsupported run schema_version: {schema_version}")
        if not isinstance(manifest["run_id"], str):
            raise SnapshotValidationError("run_id must be a string")
        if not is_run_id(manifest["run_id"]):
            raise SnapshotValidationError(
                "run_id must start with run_ and use lower snake-case"
            )
        if not isinstance(manifest["seed"], int):
            raise SnapshotValidationError("seed must be an integer")
        if not isinstance(manifest["config_digest"], str):
            raise SnapshotValidationError("config_digest must be a string")
        ids = manifest["ids"]
        if not isinstance(ids, Mapping):
            raise SnapshotValidationError("ids snapshot must be a mapping")
        return cls(
            run_id=RunId(manifest["run_id"]),
            seed=manifest["seed"],
            schema_version=str(schema_version),
            config_digest=manifest["config_digest"],
            random=DeterministicRandom.from_snapshot(manifest["random"]),
            ids=DeterministicIdGenerator.from_snapshot(ids),
        )


def config_digest(config: object) -> str:
    """Create a stable SHA-256 digest for JSON-like or dataclass config."""
    canonical = json.dumps(
        _canonicalize(config),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _canonicalize(value: object) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _canonicalize(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {
            str(key): _canonicalize(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_canonicalize(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported config digest value: {type(value).__name__}")
