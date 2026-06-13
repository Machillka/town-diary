from dataclasses import FrozenInstanceError

import pytest

from town_diary.agents import Agent, load_agents
from town_diary.core.config import load_config_bundle
from town_diary.core.contracts import NamedValue, Observation, TimeBlock, Weather
from town_diary.core.ids import AgentId, LocationId


def make_observation(
    agent_id: str = "novelist",
    location_id: str = "novelist_home",
) -> Observation:
    return Observation(
        observer_id=AgentId(agent_id),
        day=1,
        time_block=TimeBlock.MORNING,
        location_id=LocationId(location_id),
        weather=Weather.CLEAR,
        body_state=(NamedValue("energy", 90), NamedValue("hunger", 10)),
    )


def test_loads_six_agents_with_static_profiles_habits_and_goals() -> None:
    agents = load_agents(load_config_bundle("configs").agents)

    assert len(agents) == 6
    assert all(agent.profile.occupation for agent in agents)
    assert all(agent.profile.traits for agent in agents)
    assert all(agent.habits for agent in agents)
    assert all(agent.goals for agent in agents)


def test_novelist_is_distinguished_but_uses_same_agent_path() -> None:
    agents = load_agents(load_config_bundle("configs").agents)
    novelist = next(agent for agent in agents if agent.is_novelist)
    residents = tuple(agent for agent in agents if not agent.is_novelist)

    assert type(novelist) is Agent
    assert all(type(resident) is Agent for resident in residents)
    assert len(residents) == 5


def test_subjective_state_is_private_mutable_and_snapshot_is_immutable() -> None:
    novelist = load_agents(load_config_bundle("configs").agents)[0]
    before = novelist.subjective_snapshot()

    novelist.remember("Saw rain outside the window.")
    novelist.set_mood("inspired")
    novelist.set_relationship("cafe_owner", "interesting neighbor")
    after = novelist.subjective_snapshot()

    assert before != after
    assert before.mood == "curious"
    assert after.mood == "inspired"
    assert after.memories[-1] == "Saw rain outside the window."
    with pytest.raises(FrozenInstanceError):
        after.mood = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        novelist.role = "resident"  # type: ignore[misc]


def test_agent_reads_objective_position_and_body_only_from_own_observation() -> None:
    novelist = load_agents(load_config_bundle("configs").agents)[0]
    observation = make_observation()

    assert novelist.objective_location(observation) == LocationId("novelist_home")
    assert novelist.objective_body_state(observation) == (
        NamedValue("energy", 90),
        NamedValue("hunger", 10),
    )
    assert not hasattr(novelist, "location_id")
    assert not hasattr(novelist, "body_state")
    assert not hasattr(novelist, "world_state")

    with pytest.raises(ValueError, match="cannot be used"):
        novelist.objective_location(make_observation(agent_id="cafe_owner"))
