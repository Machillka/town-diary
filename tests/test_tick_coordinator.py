from dataclasses import dataclass

import pytest

from town_diary.agents import Agent, RuleDecisionPolicy, load_agents
from town_diary.core.config import load_config_bundle
from town_diary.core.contracts import ActionProposal, Observation
from town_diary.core.ids import AgentId, LocationId
from town_diary.core.run_context import RunContext
from town_diary.events import WorldLog
from town_diary.simulation.tick import TickCoordinator, TickTransactionError
from town_diary.simulation.world_state import WorldState


@dataclass
class FixedPolicy:
    actions: dict[str, tuple[str, str | None, str | None]]

    def propose(
        self,
        *,
        agent: Agent,
        observation: Observation,
        context: RunContext,
    ) -> ActionProposal:
        action_type, location, target_agent = self.actions.get(
            str(agent.id),
            ("stay", None, None),
        )
        return ActionProposal(
            action_id=context.ids.next_action_id(),
            agent_id=agent.id,
            action_type=action_type,
            reason=f"fixed {action_type}",
            target_location_id=LocationId(location) if location else None,
            target_agent_id=AgentId(target_agent) if target_agent else None,
        )


def make_coordinator(seed: int = 42):
    config = load_config_bundle("configs")
    context = RunContext.create(seed=seed, config=config)
    state = WorldState.from_config(config=config, random=context.random)
    log = WorldLog()
    coordinator = TickCoordinator(
        config=config,
        context=context,
        world_state=state,
        world_log=log,
    )
    agents = load_agents(config.agents)
    return config, context, state, log, coordinator, agents


def test_all_observations_use_same_snapshot_and_input_order_does_not_matter() -> None:
    *_, first_coordinator, first_agents = make_coordinator(seed=12)
    *_, second_coordinator, second_agents = make_coordinator(seed=12)
    policy = FixedPolicy({})

    first = first_coordinator.run_tick(agents=first_agents, policy=policy)
    second = second_coordinator.run_tick(
        agents=tuple(reversed(second_agents)),
        policy=policy,
    )

    assert first.source_snapshot == second.source_snapshot
    assert first.observations == second.observations
    assert first.proposals == second.proposals
    assert first.results == second.results
    assert first.events == second.events
    assert {observation.day for observation in first.observations} == {1}
    assert {observation.time_block for observation in first.observations} == {
        first.source_snapshot.time_block
    }


def test_proposal_phase_world_mutation_rolls_back_everything() -> None:
    config, context, state, log, coordinator, agents = make_coordinator()
    before_state = state.snapshot()
    before_random = context.random.snapshot()
    before_ids = context.ids.snapshot()

    class MutatingPolicy(FixedPolicy):
        def propose(self, *, agent, observation, context):
            state.move_agent(agent.id, agent.home_location_id)
            return super().propose(
                agent=agent,
                observation=observation,
                context=context,
            )

    with pytest.raises(TickTransactionError, match="proposal phase"):
        coordinator.run_tick(agents=agents, policy=MutatingPolicy({}))

    assert state.snapshot() == before_state
    assert context.random.snapshot() == before_random
    assert context.ids.snapshot() == before_ids
    assert log.events == ()
    assert config.schema_version == "0.1"


def test_seed_controlled_conflict_resolution_is_deterministic() -> None:
    outcomes = []
    for _ in range(2):
        _, _, state, _, coordinator, agents = make_coordinator(seed=77)
        state.move_agent("novelist", "cafe")
        state.move_agent("vendor", "cafe")
        selected = tuple(
            agent for agent in agents if str(agent.id) in {"novelist", "vendor"}
        )
        report = coordinator.run_tick(
            agents=selected,
            policy=FixedPolicy(
                {
                    "novelist": ("talk", None, "cafe_owner"),
                    "vendor": ("talk", None, "cafe_owner"),
                }
            ),
        )
        outcomes.append(
            tuple((result.action_id, result.success, result.reason) for result in report.results)
        )
        assert sum(result.success for result in report.results) == 1
        assert sum("conflict lost" in result.reason for result in report.results) == 1

    assert outcomes[0] == outcomes[1]


def test_tick_commit_keeps_state_results_and_events_consistent() -> None:
    _, _, state, log, coordinator, agents = make_coordinator(seed=42)

    report = coordinator.run_tick(agents=agents, policy=FixedPolicy({}))

    assert report.tick == 1
    assert state.tick == 1
    assert state.clock.time_block.value == "noon"
    assert len(report.proposals) == 6
    assert len(report.results) == 6
    assert all(result.success for result in report.results)
    assert len([event for event in report.events if event.source_action_id]) == 6
    assert report.events == log.events
    assert {
        event.source_action_id for event in report.events if event.source_action_id
    } == {proposal.action_id for proposal in report.proposals}


def test_failed_tick_rolls_back_rule_decision_audit() -> None:
    _, _, state, _, coordinator, agents = make_coordinator()

    class MutatingRulePolicy(RuleDecisionPolicy):
        def propose(self, *, agent, observation, context):
            proposal = super().propose(
                agent=agent,
                observation=observation,
                context=context,
            )
            state.move_agent(agent.id, agent.home_location_id)
            return proposal

    policy = MutatingRulePolicy()

    with pytest.raises(TickTransactionError):
        coordinator.run_tick(agents=agents, policy=policy)

    assert policy.decisions == ()
