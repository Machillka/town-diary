import pytest

from town_diary.agents import RuleDecisionPolicy, load_agents
from town_diary.core.config import load_config_bundle
from town_diary.core.contracts import NamedValue, Observation, TimeBlock, Weather
from town_diary.core.ids import AgentId, LocationId
from town_diary.core.run_context import RunContext
from town_diary.simulation.town import RuleBasedTownSimulation
from town_diary.simulation.runtime import RuntimeLifecycleError


def get_agent(agent_id: str):
    return next(
        agent
        for agent in load_agents(load_config_bundle("configs").agents)
        if agent.id == AgentId(agent_id)
    )


def observation(
    *,
    agent_id: str,
    location_id: str,
    energy: int = 90,
    weather: Weather = Weather.CLEAR,
    time_block: TimeBlock = TimeBlock.MORNING,
    available_actions: tuple[str, ...] = (
        "stay",
        "move",
        "work",
        "rest",
        "observe",
        "talk",
        "write_notes",
    ),
    available_locations: tuple[str, ...] = (),
) -> Observation:
    return Observation(
        observer_id=AgentId(agent_id),
        day=1,
        time_block=time_block,
        location_id=LocationId(location_id),
        weather=weather,
        body_state=(NamedValue("energy", energy), NamedValue("hunger", 10)),
        available_actions=available_actions,
        available_location_ids=tuple(LocationId(item) for item in available_locations),
    )


def test_rule_policy_selects_work_rest_and_explicit_fallback() -> None:
    config = load_config_bundle("configs")
    owner = get_agent("cafe_owner")
    policy = RuleDecisionPolicy()
    context = RunContext.create(seed=42, config=config)

    work = policy.propose(
        agent=owner,
        observation=observation(agent_id="cafe_owner", location_id="cafe"),
        context=context,
    )
    rest = policy.propose(
        agent=owner,
        observation=observation(agent_id="cafe_owner", location_id="cafe", energy=10),
        context=context,
    )
    fallback = policy.propose(
        agent=owner,
        observation=observation(
            agent_id="cafe_owner",
            location_id="cafe",
            available_actions=(),
        ),
        context=context,
    )

    assert work.action_type == "work"
    assert rest.action_type == "rest"
    assert fallback.action_type == "stay"
    assert policy.decisions[-1].used_fallback
    assert policy.decisions[-1].selected.contributions[0].source == "fallback"


def test_heavy_rain_changes_rule_selected_movement() -> None:
    config = load_config_bundle("configs")
    student = get_agent("student")
    clear_policy = RuleDecisionPolicy()
    rain_policy = RuleDecisionPolicy()

    clear = clear_policy.propose(
        agent=student,
        observation=observation(
            agent_id="student",
            location_id="student_home",
            time_block=TimeBlock.AFTERNOON,
            available_locations=("library",),
        ),
        context=RunContext.create(seed=9, config=config),
    )
    rain = rain_policy.propose(
        agent=student,
        observation=observation(
            agent_id="student",
            location_id="student_home",
            time_block=TimeBlock.AFTERNOON,
            weather=Weather.HEAVY_RAIN,
            available_locations=("library",),
        ),
        context=RunContext.create(seed=9, config=config),
    )

    assert clear.action_type == "move"
    assert rain.action_type != "move"


def test_seven_day_rule_simulation_is_reproducible_and_auditable() -> None:
    config = load_config_bundle("configs")
    first = RuleBasedTownSimulation.create(config=config, seed=42)
    second = RuleBasedTownSimulation.create(config=config, seed=42)

    first_summary = first.run_days(7)
    second_summary = second.run_days(7)

    assert first_summary.ticks_completed == 35
    assert len(first.reports) == 35
    assert len(first.policy.decisions) == 35 * 6
    assert all(report.proposals for report in first.reports)
    assert all(decision.proposal.reason for decision in first.policy.decisions)
    assert first.runtime.world_log.events == second.runtime.world_log.events
    assert first.runtime.snapshot() == second.runtime.snapshot()
    assert first.policy.decisions == second.policy.decisions
    assert any(
        event.event_type == "agent_work"
        and event.participants == (AgentId("cafe_owner"),)
        for event in first.runtime.world_log.events
    )
    assert len({event.event_type for event in first.runtime.world_log.events}) > 3


def test_world_mode_runs_residents_without_novelist_or_writing() -> None:
    simulation = RuleBasedTownSimulation.create_world_mode(
        config=load_config_bundle("configs"),
        seed=42,
    )

    summary = simulation.run_days(1)

    assert summary.ticks_completed == 5
    assert len(simulation.agents) == 5
    assert all(not agent.is_novelist for agent in simulation.agents)
    assert len(simulation.policy.decisions) == 25
    assert simulation.runtime.world_log.events
    assert not hasattr(simulation, "recorder")
    assert not hasattr(simulation, "writer")


def test_ended_rule_simulation_rejects_tick_before_world_changes() -> None:
    simulation = RuleBasedTownSimulation.create(
        config=load_config_bundle("configs"),
        seed=42,
    )
    simulation.run_days(1)
    before = simulation.runtime.snapshot()
    event_count = len(simulation.runtime.world_log.events)

    with pytest.raises(RuntimeLifecycleError):
        simulation.step()

    assert simulation.runtime.snapshot() == before
    assert len(simulation.runtime.world_log.events) == event_count
