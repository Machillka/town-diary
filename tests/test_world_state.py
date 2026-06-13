from dataclasses import FrozenInstanceError
import json

import pytest

from town_diary.core.config import load_config_bundle
from town_diary.core.errors import SnapshotValidationError
from town_diary.core.ids import AgentId, LocationId
from town_diary.core.random import DeterministicRandom
from town_diary.simulation.world_state import WorldState, WorldStateInvariantError


def make_world_state() -> WorldState:
    return WorldState.from_config(
        config=load_config_bundle("configs"),
        random=DeterministicRandom(42),
    )


def test_world_state_owns_agent_locations_and_body_states() -> None:
    state = make_world_state()

    assert state.location_of("novelist") == LocationId("novelist_home")
    assert dict((item.name, item.value) for item in state.body_state_of("novelist")) == {
        "energy": 100,
        "hunger": 0,
    }

    state.move_agent("novelist", "cafe")
    state.set_body_state("novelist", {"energy": 90, "hunger": 10})

    assert state.location_of("novelist") == LocationId("cafe")
    assert dict((item.name, item.value) for item in state.body_state_of("novelist")) == {
        "energy": 90,
        "hunger": 10,
    }


def test_world_snapshot_is_deeply_immutable_and_detached() -> None:
    state = make_world_state()
    snapshot = state.snapshot()
    original_novelist = next(
        agent for agent in snapshot.agent_states if agent.agent_id == AgentId("novelist")
    )

    state.move_agent("novelist", "cafe")

    assert original_novelist.location_id == LocationId("novelist_home")
    with pytest.raises(FrozenInstanceError):
        snapshot.tick = 5  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        original_novelist.location_id = LocationId("cafe")  # type: ignore[misc]


def test_world_state_rejects_invalid_objective_state() -> None:
    state = make_world_state()
    before = state.snapshot()

    with pytest.raises(WorldStateInvariantError, match="unknown location"):
        state.move_agent("novelist", "missing_location")
    with pytest.raises(WorldStateInvariantError, match="must be numeric"):
        state.set_body_state("novelist", {"energy": "high"})  # type: ignore[dict-item]

    assert state.snapshot() == before


def test_world_state_checkpoint_round_trip() -> None:
    config = load_config_bundle("configs")
    random = DeterministicRandom(42)
    state = WorldState.from_config(config=config, random=random)
    state.weather.advance(day=1, time_block=state.clock.time_block)
    state.clock.advance()
    state.increment_tick()
    state.move_agent("novelist", "cafe")
    checkpoint_json = json.dumps(state.checkpoint().to_dict(), ensure_ascii=False)

    restored = WorldState.from_checkpoint(
        checkpoint=json.loads(checkpoint_json),
        config=config,
        random=DeterministicRandom.from_snapshot(random.snapshot()),
    )

    assert restored.snapshot() == state.snapshot()
    assert restored.checkpoint() == state.checkpoint()


def test_world_state_rejects_checkpoint_with_wrong_agent_set() -> None:
    config = load_config_bundle("configs")
    state = WorldState.from_config(config=config, random=DeterministicRandom(42))
    checkpoint = state.checkpoint().to_dict()
    del checkpoint["agent_locations"]["student"]  # type: ignore[index]

    with pytest.raises(SnapshotValidationError, match="agent IDs must match"):
        WorldState.from_checkpoint(
            checkpoint=checkpoint,
            config=config,
            random=DeterministicRandom(42),
        )
