import json
from dataclasses import FrozenInstanceError

import pytest

from town_diary.core.ids import DeterministicIdGenerator
from town_diary.core.random import DeterministicRandom
from town_diary.core.run_context import RunContext, config_digest


def test_same_seed_produces_same_random_sequence() -> None:
    first = DeterministicRandom(42)
    second = DeterministicRandom(42)

    assert [first.randint(1, 100) for _ in range(10)] == [
        second.randint(1, 100) for _ in range(10)
    ]


def test_different_seeds_produce_different_random_sequences() -> None:
    first = DeterministicRandom(42)
    second = DeterministicRandom(43)

    assert [first.random() for _ in range(5)] != [second.random() for _ in range(5)]


def test_random_snapshot_restores_next_value() -> None:
    random = DeterministicRandom(12)
    random.random()
    restored = DeterministicRandom.from_snapshot(random.snapshot())

    assert restored.random() == random.random()


def test_id_generator_is_unique_and_restorable() -> None:
    ids = DeterministicIdGenerator()

    assert str(ids.next_action_id()) == "action_000001"
    assert str(ids.next_action_id()) == "action_000002"
    assert str(ids.next_event_id()) == "event_000001"

    restored = DeterministicIdGenerator.from_snapshot(ids.snapshot())
    assert str(restored.next_action_id()) == "action_000003"
    assert str(restored.next_event_id()) == "event_000002"


def test_run_context_manifest_round_trip_preserves_replay_state() -> None:
    config = {"schema_version": "0.1", "locations": ["cafe", "library"]}
    context = RunContext.create(seed=42, config=config)
    context.random.random()
    context.ids.next_event_id()

    manifest_json = json.dumps(context.to_manifest(), sort_keys=True)
    restored = RunContext.from_manifest(json.loads(manifest_json))

    assert restored.config_digest == config_digest(config)
    assert restored.to_manifest()["run_id"] == context.to_manifest()["run_id"]
    assert restored.random.random() == context.random.random()
    assert restored.ids.next_event_id() == context.ids.next_event_id()


def test_run_context_rejects_unstable_run_id() -> None:
    with pytest.raises(ValueError, match="run_id"):
        RunContext.create(seed=42, config={}, run_id="Custom Run")


def test_negative_seed_gets_a_stable_default_run_id() -> None:
    context = RunContext.create(seed=-7, config={})

    assert str(context.run_id).startswith("run_n7_")


def test_run_context_identity_is_immutable() -> None:
    context = RunContext.create(seed=42, config={})

    with pytest.raises(FrozenInstanceError):
        context.seed = 99  # type: ignore[misc]
