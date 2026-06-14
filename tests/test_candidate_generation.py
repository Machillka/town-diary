from town_diary.agents import load_agents
from town_diary.core.config import load_config_bundle
from town_diary.core.contracts import NamedValue, Observation, TimeBlock, Weather
from town_diary.core.ids import AgentId, LocationId
from town_diary.core.random import DeterministicRandom


ALL_ACTIONS = ("stay", "move", "work", "rest", "observe", "talk", "write_notes")


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
    time_block: TimeBlock = TimeBlock.MORNING,
    weather: Weather = Weather.CLEAR,
    energy: int = 90,
    hunger: int = 10,
    visible_agents: tuple[str, ...] = (),
    available_actions: tuple[str, ...] = ALL_ACTIONS,
    available_locations: tuple[str, ...] = (),
) -> Observation:
    return Observation(
        observer_id=AgentId(agent_id),
        day=1,
        time_block=time_block,
        location_id=LocationId(location_id),
        weather=weather,
        body_state=(NamedValue("energy", energy), NamedValue("hunger", hunger)),
        visible_agents=tuple(AgentId(item) for item in visible_agents),
        available_actions=available_actions,
        available_location_ids=tuple(LocationId(item) for item in available_locations),
    )


def test_cafe_owner_morning_work_is_highest_explainable_candidate() -> None:
    owner = get_agent("cafe_owner")

    candidates = owner.generate_candidates(
        observation(agent_id="cafe_owner", location_id="cafe"),
        DeterministicRandom(42),
    )

    assert candidates[0].action_type == "work"
    assert {item.source for item in candidates[0].contributions} >= {
        "habit",
        "random",
        "subjective_state",
    }
    assert candidates[0].reason


def test_novelist_has_stable_time_and_weather_writing_tendency() -> None:
    novelist = get_agent("novelist")
    morning_rain = novelist.generate_candidates(
        observation(
            agent_id="novelist",
            location_id="novelist_home",
            weather=Weather.LIGHT_RAIN,
        ),
        DeterministicRandom(7),
    )
    afternoon = novelist.generate_candidates(
        observation(
            agent_id="novelist",
            location_id="novelist_home",
            time_block=TimeBlock.AFTERNOON,
        ),
        DeterministicRandom(7),
    )

    assert morning_rain[0].action_type == "write_notes"
    assert any(item.source == "weather" for item in morning_rain[0].contributions)
    assert all(candidate.action_type != "write_notes" for candidate in afternoon)


def test_candidates_respect_available_actions_locations_and_visible_agents() -> None:
    novelist = get_agent("novelist")

    candidates = novelist.generate_candidates(
        observation(
            agent_id="novelist",
            location_id="novelist_home",
            visible_agents=("cafe_owner",),
            available_actions=("stay", "move", "talk"),
            available_locations=("cafe",),
        ),
        DeterministicRandom(4),
    )

    assert {candidate.action_type for candidate in candidates} == {"stay", "move", "talk"}
    move = next(candidate for candidate in candidates if candidate.action_type == "move")
    talk = next(candidate for candidate in candidates if candidate.action_type == "talk")
    assert move.target_location_id == LocationId("cafe")
    assert talk.target_agent_id == AgentId("cafe_owner")


def test_same_observation_and_seed_produce_same_candidates_and_scores() -> None:
    student = get_agent("student")
    current = observation(
        agent_id="student",
        location_id="student_home",
        time_block=TimeBlock.AFTERNOON,
        available_locations=("library",),
    )

    first = student.generate_candidates(current, DeterministicRandom(99))
    second = student.generate_candidates(current, DeterministicRandom(99))

    assert first == second
    assert all(candidate.contributions[-1].source == "random" for candidate in first)


def test_low_energy_increases_rest_score_and_candidates_do_not_change_agent_state() -> None:
    student = get_agent("student")
    before = student.subjective_snapshot()
    rested = student.generate_candidates(
        observation(agent_id="student", location_id="library", energy=20),
        DeterministicRandom(2),
    )
    energetic = student.generate_candidates(
        observation(agent_id="student", location_id="library", energy=90),
        DeterministicRandom(2),
    )

    low_energy_rest = next(item for item in rested if item.action_type == "rest")
    high_energy_rest = next(item for item in energetic if item.action_type == "rest")
    assert low_energy_rest.score > high_energy_rest.score
    assert student.subjective_snapshot() == before
