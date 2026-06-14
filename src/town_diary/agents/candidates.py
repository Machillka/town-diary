"""Explainable candidate behavior generation from limited Agent inputs."""

from dataclasses import dataclass

from town_diary.core.contracts import Observation, TimeBlock, Weather
from town_diary.core.ids import AgentId, LocationId
from town_diary.core.random import DeterministicRandom
from town_diary.agents.model import Agent, SubjectiveStateSnapshot


@dataclass(frozen=True, slots=True)
class NeedState:
    """Urgency levels derived only from an Agent's current Observation."""

    energy: float
    hunger: float
    social: float
    writing: float


@dataclass(frozen=True, slots=True)
class ScoreContribution:
    source: str
    value: float
    reason: str


@dataclass(frozen=True, slots=True)
class CandidateAction:
    """Subjective behavior option; it is not an objective fact or proposal yet."""

    action_type: str
    reason: str
    score: float
    contributions: tuple[ScoreContribution, ...]
    target_location_id: LocationId | None = None
    target_agent_id: AgentId | None = None


class CandidateGenerator:
    """Generate deterministic, explainable options without reading WorldState."""

    def generate(
        self,
        *,
        agent: Agent,
        observation: Observation,
        random: DeterministicRandom,
    ) -> tuple[CandidateAction, ...]:
        agent.objective_location(observation)
        needs = derive_needs(agent=agent, observation=observation)
        subjective = agent.subjective_snapshot()
        actions = set(observation.available_actions)
        candidates: list[CandidateAction] = []

        if "stay" in actions:
            contributions = [ScoreContribution("base", 10.0, "staying is always stable")]
            if observation.weather is Weather.HEAVY_RAIN:
                contributions.append(
                    ScoreContribution("weather", 25.0, "heavy rain favors staying")
                )
            candidates.append(
                _candidate(
                    action_type="stay",
                    contributions=contributions,
                    random=random,
                )
            )

        if "rest" in actions:
            candidates.append(
                _candidate(
                    action_type="rest",
                    contributions=[
                        ScoreContribution("base", 5.0, "rest is available"),
                        ScoreContribution(
                            "need",
                            needs.energy * 0.8,
                            f"energy recovery urgency is {needs.energy:.1f}",
                        ),
                    ],
                    random=random,
                )
            )

        habit_targets = _habit_targets(agent, observation)
        if agent.is_novelist:
            if "write_notes" in actions and observation.location_id in habit_targets:
                contributions = [
                    ScoreContribution(
                        "need",
                        needs.writing,
                        f"writing tendency is {needs.writing:.1f}",
                    ),
                    ScoreContribution("habit", 55.0, "a writing habit is active here"),
                    ScoreContribution("location", 10.0, "the writing place matches the habit"),
                ]
                if observation.weather in {Weather.LIGHT_RAIN, Weather.HEAVY_RAIN}:
                    contributions.append(
                        ScoreContribution("weather", 15.0, "rain encourages reflection")
                    )
                contributions.extend(_mood_contribution(subjective, "write_notes"))
                candidates.append(
                    _candidate(
                        action_type="write_notes",
                        contributions=contributions,
                        random=random,
                    )
                )
        elif "work" in actions and observation.location_id in habit_targets:
            contributions = [
                ScoreContribution("base", 20.0, "work is available"),
                ScoreContribution("habit", 60.0, "a work habit is active here"),
                ScoreContribution("location", 10.0, "the current location matches the habit"),
                ScoreContribution(
                    "need",
                    -needs.energy,
                    f"energy recovery urgency reduces work by {needs.energy:.1f}",
                ),
            ]
            contributions.extend(_mood_contribution(subjective, "work"))
            candidates.append(
                _candidate(
                    action_type="work",
                    contributions=contributions,
                    random=random,
                )
            )

        if "observe" in actions:
            contributions = [ScoreContribution("base", 15.0, "observation is available")]
            contributions.extend(_mood_contribution(subjective, "observe"))
            candidates.append(
                _candidate(
                    action_type="observe",
                    contributions=contributions,
                    random=random,
                )
            )

        if "talk" in actions:
            known_relationships = {
                relationship.agent_id for relationship in subjective.relationships
            }
            for target_agent_id in sorted(observation.visible_agents, key=str):
                contributions = [
                    ScoreContribution(
                        "need",
                        needs.social * 0.6,
                        f"social urgency is {needs.social:.1f}",
                    )
                ]
                if target_agent_id in known_relationships:
                    contributions.append(
                        ScoreContribution("relationship", 10.0, "the person is familiar")
                    )
                candidates.append(
                    _candidate(
                        action_type="talk",
                        target_agent_id=target_agent_id,
                        contributions=contributions,
                        random=random,
                    )
                )

        if "move" in actions:
            candidates.extend(
                self._move_candidates(
                    agent=agent,
                    observation=observation,
                    needs=needs,
                    random=random,
                )
            )

        return tuple(
            sorted(
                candidates,
                key=lambda item: (
                    -item.score,
                    item.action_type,
                    str(item.target_location_id or ""),
                    str(item.target_agent_id or ""),
                ),
            )
        )

    def _move_candidates(
        self,
        *,
        agent: Agent,
        observation: Observation,
        needs: NeedState,
        random: DeterministicRandom,
    ) -> tuple[CandidateAction, ...]:
        available = set(observation.available_location_ids)
        targets: dict[LocationId, list[ScoreContribution]] = {}
        for habit in agent.habits:
            if (
                habit.target_location_id in available
                and habit.target_location_id != observation.location_id
                and observation.time_block in habit.preferred_time_blocks
            ):
                targets.setdefault(habit.target_location_id, []).append(
                    ScoreContribution("habit", 45.0, f"habit {habit.id} is active")
                )
        for goal in agent.goals:
            if (
                goal.target_location_id in available
                and goal.target_location_id != observation.location_id
            ):
                targets.setdefault(goal.target_location_id, []).append(
                    ScoreContribution("goal", 20.0, f"goal {goal.id} points here")
                )
        if (
            observation.time_block in {TimeBlock.EVENING, TimeBlock.NIGHT}
            and agent.home_location_id in available
            and agent.home_location_id != observation.location_id
        ):
            targets.setdefault(agent.home_location_id, []).append(
                ScoreContribution("habit", 30.0, "evening routine favors returning home")
            )
        candidates: list[CandidateAction] = []
        for target_location_id in sorted(targets, key=str):
            contributions = [
                ScoreContribution("location", 10.0, "the destination is currently available"),
                *targets[target_location_id],
                ScoreContribution(
                    "need",
                    -needs.energy * 0.25,
                    f"energy recovery urgency reduces movement by {needs.energy * 0.25:.1f}",
                ),
            ]
            if observation.weather is Weather.HEAVY_RAIN:
                contributions.append(
                    ScoreContribution("weather", -50.0, "heavy rain strongly discourages movement")
                )
            elif observation.weather is Weather.LIGHT_RAIN:
                contributions.append(
                    ScoreContribution("weather", -12.0, "light rain discourages movement")
                )
            candidates.append(
                _candidate(
                    action_type="move",
                    target_location_id=target_location_id,
                    contributions=contributions,
                    random=random,
                )
            )
        return tuple(candidates)


def derive_needs(*, agent: Agent, observation: Observation) -> NeedState:
    """Derive the minimum MVP needs without storing a second objective truth."""
    agent.objective_body_state(observation)
    body_state = {item.name: item.value for item in observation.body_state}
    energy_value = _numeric(body_state.get("energy"), default=100.0)
    hunger_value = _numeric(body_state.get("hunger"), default=0.0)
    return NeedState(
        energy=_clamp(100.0 - energy_value),
        hunger=_clamp(hunger_value),
        social=20.0 if observation.visible_agents else 60.0,
        writing=(
            75.0
            if agent.is_novelist
            and observation.time_block in {TimeBlock.MORNING, TimeBlock.EVENING}
            else 20.0 if agent.is_novelist else 0.0
        ),
    )


def _candidate(
    *,
    action_type: str,
    contributions: list[ScoreContribution],
    random: DeterministicRandom,
    target_location_id: LocationId | None = None,
    target_agent_id: AgentId | None = None,
) -> CandidateAction:
    disturbance = ScoreContribution(
        "random",
        round(random.random() * 2.0, 6),
        "seed-controlled small disturbance",
    )
    resolved = (*contributions, disturbance)
    return CandidateAction(
        action_type=action_type,
        target_location_id=target_location_id,
        target_agent_id=target_agent_id,
        contributions=resolved,
        score=round(sum(item.value for item in resolved), 6),
        reason="; ".join(item.reason for item in resolved),
    )


def _habit_targets(agent: Agent, observation: Observation) -> set[LocationId]:
    return {
        habit.target_location_id
        for habit in agent.habits
        if observation.time_block in habit.preferred_time_blocks
    }


def _mood_contribution(
    subjective: SubjectiveStateSnapshot,
    action_type: str,
) -> tuple[ScoreContribution, ...]:
    favored = {
        "work": {"focused", "energetic"},
        "observe": {"curious", "calm", "thoughtful"},
        "write_notes": {"curious", "thoughtful", "inspired"},
    }
    if subjective.mood not in favored.get(action_type, set()):
        return ()
    return (
        ScoreContribution(
            "subjective_state",
            5.0,
            f"current mood {subjective.mood} supports {action_type}",
        ),
    )


def _numeric(value: object, *, default: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


def _clamp(value: float) -> float:
    return min(100.0, max(0.0, value))
