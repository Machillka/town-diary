import pytest

from town_diary.actions import ActionExecutor, ActionValidator
from town_diary.core.config import load_config_bundle
from town_diary.core.contracts import ActionProposal
from town_diary.core.ids import ActionId, AgentId, LocationId
from town_diary.core.run_context import RunContext
from town_diary.events import EventFactory, WorldLog, WorldLogError
from town_diary.simulation.runtime import WorldRuntime
from town_diary.simulation.world_state import WorldState


def make_executor():
    config = load_config_bundle("configs")
    context = RunContext.create(seed=42, config=config)
    state = WorldState.from_config(config=config, random=context.random)
    log = WorldLog()
    executor = ActionExecutor(
        world_state=state,
        validator=ActionValidator(config=config),
        events=EventFactory(run_id=str(context.run_id), ids=context.ids, world_log=log),
    )
    return state, log, executor


def test_successful_action_creates_traceable_structured_event() -> None:
    state, log, executor = make_executor()
    proposal = ActionProposal(
        action_id=ActionId("action_000001"),
        agent_id=AgentId("novelist"),
        action_type="move",
        reason="subjective reason is not an objective fact",
        target_location_id=LocationId("cafe"),
    )

    result = executor.execute(proposal)
    event = result.events[0]

    assert result.success
    assert log.events == result.events
    assert event.source_action_id == proposal.action_id
    assert event.event_type == "agent_move"
    assert event.location_id == LocationId("cafe")
    assert event.participants == (AgentId("novelist"),)
    assert {fact.name for fact in event.facts} >= {
        "action_type",
        "effect_location_id",
        "target_location_id",
    }
    assert proposal.reason not in {str(fact.value) for fact in event.facts}
    assert state.location_of("novelist") == LocationId("cafe")


def test_failed_action_does_not_create_world_event() -> None:
    state, log, executor = make_executor()
    before = state.snapshot()

    result = executor.execute(
        ActionProposal(
            action_id=ActionId("action_000001"),
            agent_id=AgentId("novelist"),
            action_type="move",
            reason="invalid",
            target_location_id=LocationId("station"),
        )
    )

    assert not result.success
    assert result.events == ()
    assert log.events == ()
    assert state.snapshot() == before


def test_world_log_jsonl_round_trip_preserves_order(tmp_path) -> None:
    _, log, executor = make_executor()
    for action_id, action_type in (("action_000001", "stay"), ("action_000002", "observe")):
        executor.execute(
            ActionProposal(
                action_id=ActionId(action_id),
                agent_id=AgentId("novelist"),
                action_type=action_type,
                reason="test",
            )
        )
    path = tmp_path / "world.jsonl"

    log.save_jsonl(path)
    restored = WorldLog.load_jsonl(path)

    assert restored.events == log.events
    assert [str(event.event_id) for event in restored.events] == [
        "event_000001",
        "event_000002",
    ]
    with pytest.raises(WorldLogError, match="already exists"):
        log.save_jsonl(path)


def test_world_runtime_records_environment_weather_events_deterministically() -> None:
    config = load_config_bundle("configs")
    first = WorldRuntime.create(config=config, seed=42)
    second = WorldRuntime.create(config=config, seed=42)

    first.run_days(1)
    second.run_days(1)

    assert first.world_log.events
    assert first.world_log.events == second.world_log.events
    assert all(event.source_action_id is None for event in first.world_log.events)
