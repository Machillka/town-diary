from copy import deepcopy
from dataclasses import replace

import pytest

from town_diary.core.config import load_config_bundle
from town_diary.core.errors import SnapshotValidationError
from town_diary.simulation.checkpoint import (
    create_runtime_checkpoint,
    load_runtime_checkpoint,
    replay_world_runtime,
    restore_world_runtime,
    save_runtime_checkpoint,
)
from town_diary.simulation.runtime import RuntimeEndReason, RuntimeStatus, WorldRuntime


def make_runtime(seed: int = 42) -> WorldRuntime:
    return WorldRuntime.create(config=load_config_bundle("configs"), seed=seed)


def test_interrupted_restore_matches_continuous_objective_records() -> None:
    continuous = make_runtime()
    continuous.run_days(7)

    interrupted = make_runtime()
    interrupted.run_ticks(15)
    checkpoint = create_runtime_checkpoint(interrupted)
    restored = restore_world_runtime(
        checkpoint=checkpoint.to_dict(),
        config=load_config_bundle("configs"),
    )

    assert restored.status is RuntimeStatus.PAUSED
    restored.resume()
    restored.run_ticks(20, end_when_complete=True)

    assert restored.records == continuous.records
    assert restored.snapshot() == continuous.snapshot()
    assert restored.end_reason is RuntimeEndReason.COMPLETED


def test_replay_uses_original_seed_and_config_digest() -> None:
    runtime = make_runtime(seed=17)
    runtime.run_ticks(18)
    checkpoint = create_runtime_checkpoint(runtime)

    replay = replay_world_runtime(
        checkpoint=checkpoint,
        config=load_config_bundle("configs"),
    )

    assert replay.context.seed == 17
    assert replay.context.config_digest == runtime.context.config_digest
    assert replay.records == runtime.records
    assert replay.snapshot() == runtime.snapshot()


def test_checkpoint_file_round_trip_and_no_overwrite(tmp_path) -> None:
    runtime = make_runtime()
    runtime.run_ticks(5)
    checkpoint = create_runtime_checkpoint(runtime)
    path = tmp_path / "checkpoint.json"

    save_runtime_checkpoint(path, checkpoint)

    assert load_runtime_checkpoint(path).to_dict() == checkpoint.to_dict()
    with pytest.raises(SnapshotValidationError, match="already exists"):
        save_runtime_checkpoint(path, checkpoint)


def test_checkpoint_rejects_missing_and_incompatible_versions() -> None:
    runtime = make_runtime()
    runtime.run_ticks(1)
    checkpoint = create_runtime_checkpoint(runtime).to_dict()
    missing = deepcopy(checkpoint)
    del missing["world_state"]
    incompatible = deepcopy(checkpoint)
    incompatible["schema_version"] = "9.9"

    with pytest.raises(SnapshotValidationError, match="missing fields"):
        restore_world_runtime(checkpoint=missing, config=load_config_bundle("configs"))
    with pytest.raises(SnapshotValidationError, match="unsupported runtime checkpoint"):
        restore_world_runtime(
            checkpoint=incompatible,
            config=load_config_bundle("configs"),
        )


def test_checkpoint_rejects_different_active_config() -> None:
    config = load_config_bundle("configs")
    runtime = WorldRuntime.create(config=config, seed=42)
    runtime.run_ticks(1)
    checkpoint = create_runtime_checkpoint(runtime)
    different_config = replace(config, agents=config.agents[:-1])

    with pytest.raises(SnapshotValidationError, match="config digest"):
        restore_world_runtime(checkpoint=checkpoint, config=different_config)
