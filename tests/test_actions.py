import pytest

from town_diary.actions import ActionExecutor, ActionValidator
from town_diary.agents import CandidateAction, ScoreContribution, load_agents
from town_diary.core.config import load_config_bundle
from town_diary.core.contracts import ActionProposal, NamedValue, TimeBlock
from town_diary.core.ids import ActionId, AgentId, LocationId
from town_diary.core.run_context import RunContext
from town_diary.events import EventFactory, WorldLog
from town_diary.simulation.world_state import WorldState


def make_services():
    config = load_config_bundle("configs")
    context = RunContext.create(seed=42, config=config)
    state = WorldState.from_config(config=config, random=context.random)
    return config, state, ActionExecutor(
        world_state=state,
        validator=ActionValidator(config=config),
        events=EventFactory(
            run_id=str(context.run_id),
            ids=context.ids,
            world_log=WorldLog(),
        ),
    )


def proposal(
    action_type: str,
    *,
    agent_id: str = "novelist",
    target_location_id: str | None = None,
    target_agent_id: str | None = None,
) -> ActionProposal:
    return ActionProposal(
        action_id=ActionId("action_000001"),
        agent_id=AgentId(agent_id),
        action_type=action_type,
        reason="test proposal",
        target_location_id=(
            LocationId(target_location_id) if target_location_id is not None else None
        ),
        target_agent_id=(
            AgentId(target_agent_id) if target_agent_id is not None else None
        ),
    )


def test_agent_can_only_convert_candidate_to_proposal() -> None:
    agent = load_agents(load_config_bundle("configs").agents)[0]
    candidate = CandidateAction(
        action_type="move",
        reason="visit the cafe",
        score=20,
        contributions=(ScoreContribution("goal", 20, "visit the cafe"),),
        target_location_id=LocationId("cafe"),
    )

    result = agent.propose(candidate, action_id=ActionId("action_000007"))

    assert result.action_id == ActionId("action_000007")
    assert result.agent_id == agent.id
    assert result.target_location_id == LocationId("cafe")
    assert not hasattr(agent, "execute")
    assert not hasattr(agent, "world_state")


def test_legal_move_succeeds_through_executor() -> None:
    _, state, executor = make_services()

    result = executor.execute(proposal("move", target_location_id="cafe"))

    assert result.success
    assert state.location_of("novelist") == LocationId("cafe")
    assert result.effects == (NamedValue("location_id", "cafe"),)


@pytest.mark.parametrize(
    ("target", "reason"),
    [
        ("station", "not adjacent"),
        ("cafe_owner_home", "not adjacent"),
    ],
)
def test_invalid_move_fails_without_changing_world(target: str, reason: str) -> None:
    _, state, executor = make_services()
    before = state.snapshot()

    result = executor.execute(proposal("move", target_location_id=target))

    assert not result.success
    assert reason in result.reason
    assert result.effects == ()
    assert state.snapshot() == before


def test_move_to_closed_location_fails_without_changing_world() -> None:
    _, state, executor = make_services()
    for _ in range(4):
        state.clock.advance()
    assert state.clock.time_block is TimeBlock.NIGHT
    before = state.snapshot()

    result = executor.execute(proposal("move", target_location_id="library"))

    assert not result.success
    assert "closed" in result.reason
    assert state.snapshot() == before


def test_talk_to_agent_at_different_location_fails_without_changing_world() -> None:
    _, state, executor = make_services()
    before = state.snapshot()

    result = executor.execute(
        proposal("talk", target_agent_id="cafe_owner")
    )

    assert not result.success
    assert "same location" in result.reason
    assert state.snapshot() == before


def test_unknown_action_is_rejected_without_changing_world() -> None:
    _, state, executor = make_services()
    before = state.snapshot()

    result = executor.execute(proposal("teleport", target_location_id="station"))

    assert not result.success
    assert result.reason == "unknown action type"
    assert state.snapshot() == before


def test_work_and_rest_have_structured_objective_effects() -> None:
    _, state, executor = make_services()

    work = executor.execute(proposal("work", agent_id="cafe_owner"))
    rest = executor.execute(proposal("rest", agent_id="cafe_owner"))

    assert work.success and rest.success
    assert dict((item.name, item.value) for item in work.effects) == {
        "energy": 90.0,
        "hunger": 10.0,
    }
    assert dict((item.name, item.value) for item in rest.effects) == {
        "energy": 100.0,
        "hunger": 15.0,
    }


@pytest.mark.parametrize("action_type", ["stay", "observe", "write_notes"])
def test_non_mutating_supported_actions_return_structured_success(
    action_type: str,
) -> None:
    _, state, executor = make_services()
    before = state.snapshot()

    result = executor.execute(proposal(action_type))

    assert result.success
    assert result.reason == "action committed"
    assert result.effects == ()
    assert state.snapshot() == before


def test_same_location_talk_succeeds_and_changes_only_actor_body_state() -> None:
    _, state, executor = make_services()
    state.move_agent("novelist", "cafe")
    target_before = state.body_state_of("cafe_owner")

    result = executor.execute(proposal("talk", target_agent_id="cafe_owner"))

    assert result.success
    assert state.body_state_of("cafe_owner") == target_before
    assert dict((item.name, item.value) for item in result.effects) == {
        "energy": 98.0,
        "hunger": 2.0,
    }


def test_active_action_requires_energy_and_failure_is_atomic() -> None:
    _, state, executor = make_services()
    state.set_body_state("cafe_owner", {"energy": 0, "hunger": 30})
    before = state.snapshot()

    result = executor.execute(proposal("work", agent_id="cafe_owner"))

    assert not result.success
    assert "no energy" in result.reason
    assert state.snapshot() == before


def test_resident_cannot_use_novelist_only_action() -> None:
    _, state, executor = make_services()
    before = state.snapshot()

    result = executor.execute(proposal("write_notes", agent_id="cafe_owner"))

    assert not result.success
    assert "only the novelist" in result.reason
    assert state.snapshot() == before
