"""Agent static identity and private subjective state."""

from dataclasses import dataclass

from town_diary.core.config import AgentConfig
from town_diary.core.contracts import NamedValue, Observation, TimeBlock
from town_diary.core.ids import AgentId, LocationId


@dataclass(frozen=True, slots=True)
class AgentProfile:
    occupation: str
    traits: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Habit:
    id: str
    description: str
    preferred_time_blocks: tuple[TimeBlock, ...]
    target_location_id: LocationId


@dataclass(frozen=True, slots=True)
class Goal:
    id: str
    description: str
    target_location_id: LocationId | None


@dataclass(frozen=True, slots=True)
class RelationshipCognition:
    agent_id: AgentId
    impression: str


@dataclass(frozen=True, slots=True)
class SubjectiveStateSnapshot:
    mood: str
    memories: tuple[str, ...]
    relationships: tuple[RelationshipCognition, ...]


class SubjectiveState:
    """One Agent's private mutable memory and relationship cognition."""

    def __init__(
        self,
        *,
        mood: str,
        memories: tuple[str, ...] = (),
        relationships: tuple[RelationshipCognition, ...] = (),
    ) -> None:
        self._mood = mood
        self._memories = list(memories)
        self._relationships = {
            relationship.agent_id: relationship.impression
            for relationship in relationships
        }

    def remember(self, memory: str) -> None:
        if not memory:
            raise ValueError("memory must not be empty")
        self._memories.append(memory)

    def set_mood(self, mood: str) -> None:
        if not mood:
            raise ValueError("mood must not be empty")
        self._mood = mood

    def set_relationship(self, agent_id: AgentId | str, impression: str) -> None:
        if not impression:
            raise ValueError("relationship impression must not be empty")
        self._relationships[AgentId(str(agent_id))] = impression

    def snapshot(self) -> SubjectiveStateSnapshot:
        return SubjectiveStateSnapshot(
            mood=self._mood,
            memories=tuple(self._memories),
            relationships=tuple(
                RelationshipCognition(agent_id=agent_id, impression=impression)
                for agent_id, impression in sorted(
                    self._relationships.items(),
                    key=lambda item: str(item[0]),
                )
            ),
        )


@dataclass(frozen=True, slots=True)
class Agent:
    """Resident decision owner with no reference to mutable objective world state."""

    id: AgentId
    name: str
    role: str
    home_location_id: LocationId
    profile: AgentProfile
    habits: tuple[Habit, ...]
    goals: tuple[Goal, ...]
    _subjective_state: SubjectiveState

    @classmethod
    def from_config(cls, config: AgentConfig) -> "Agent":
        return cls(
            id=config.id,
            name=config.name,
            role=config.role,
            home_location_id=config.home_location_id,
            profile=AgentProfile(
                occupation=config.profile.occupation,
                traits=config.profile.traits,
            ),
            habits=tuple(
                Habit(
                    id=habit.id,
                    description=habit.description,
                    preferred_time_blocks=habit.preferred_time_blocks,
                    target_location_id=habit.target_location_id,
                )
                for habit in config.habits
            ),
            goals=tuple(
                Goal(
                    id=goal.id,
                    description=goal.description,
                    target_location_id=goal.target_location_id,
                )
                for goal in config.goals
            ),
            _subjective_state=SubjectiveState(
                mood=config.initial_subjective_state.mood,
                memories=config.initial_subjective_state.memories,
                relationships=tuple(
                    RelationshipCognition(
                        agent_id=relationship.agent_id,
                        impression=relationship.impression,
                    )
                    for relationship in config.initial_subjective_state.relationships
                ),
            ),
        )

    @property
    def is_novelist(self) -> bool:
        return self.role == "novelist"

    def subjective_snapshot(self) -> SubjectiveStateSnapshot:
        return self._subjective_state.snapshot()

    def remember(self, memory: str) -> None:
        self._subjective_state.remember(memory)

    def set_mood(self, mood: str) -> None:
        self._subjective_state.set_mood(mood)

    def set_relationship(self, agent_id: AgentId | str, impression: str) -> None:
        self._subjective_state.set_relationship(agent_id, impression)

    def objective_location(self, observation: Observation) -> LocationId:
        self._validate_observation(observation)
        return observation.location_id

    def objective_body_state(self, observation: Observation) -> tuple[NamedValue, ...]:
        self._validate_observation(observation)
        return observation.body_state

    def _validate_observation(self, observation: Observation) -> None:
        if observation.observer_id != self.id:
            raise ValueError(
                f"observation for {observation.observer_id} cannot be used by {self.id}"
            )


def load_agents(configs: tuple[AgentConfig, ...]) -> tuple[Agent, ...]:
    """Create all configured Agents through the same ordinary behavior path."""
    return tuple(Agent.from_config(config) for config in configs)
