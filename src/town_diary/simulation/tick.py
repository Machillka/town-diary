"""Two-phase deterministic tick coordination."""

from dataclasses import dataclass
from typing import Protocol

from town_diary.actions import (
    SUPPORTED_ACTION_TYPES,
    ActionExecutor,
    ActionValidation,
    ActionValidator,
)
from town_diary.agents import Agent
from town_diary.core.config import AgentConfig, ConfigBundle
from town_diary.core.contracts import (
    ActionProposal,
    ActionResult,
    Observation,
    WorldEvent,
    WorldSnapshot,
)
from town_diary.core.errors import TownDiaryError
from town_diary.core.ids import ActionId, AgentId, LocationId
from town_diary.core.run_context import RunContext
from town_diary.events import EventFactory, WorldLog
from town_diary.simulation.runtime import WorldTickRecord
from town_diary.simulation.world_state import WorldState


class TickTransactionError(TownDiaryError):
    """Raised when a tick cannot be committed atomically."""


class ProposalPolicy(Protocol):
    def propose(
        self,
        *,
        agent: Agent,
        observation: Observation,
        context: RunContext,
    ) -> ActionProposal: ...


@dataclass(frozen=True, slots=True)
class TickReport:
    tick: int
    source_snapshot: WorldSnapshot
    observations: tuple[Observation, ...]
    proposals: tuple[ActionProposal, ...]
    results: tuple[ActionResult, ...]
    events: tuple[WorldEvent, ...]
    record: WorldTickRecord


class ObservationBuilder:
    """Environment-side minimal projection used before full Perception exists."""

    def __init__(self, *, config: ConfigBundle, world_state: WorldState) -> None:
        self._agent_configs = {agent.id: agent for agent in config.agents}
        self._locations = world_state.locations

    def build_all(
        self,
        *,
        snapshot: WorldSnapshot,
        agents: tuple[Agent, ...],
    ) -> tuple[Observation, ...]:
        agent_states = {state.agent_id: state for state in snapshot.agent_states}
        observations: list[Observation] = []
        for agent in sorted(agents, key=lambda item: str(item.id)):
            state = agent_states[agent.id]
            visible_agents = tuple(
                sorted(
                    (
                        other.agent_id
                        for other in snapshot.agent_states
                        if other.agent_id != agent.id
                        and other.location_id == state.location_id
                    ),
                    key=str,
                )
            )
            observations.append(
                Observation(
                    observer_id=agent.id,
                    day=snapshot.day,
                    time_block=snapshot.time_block,
                    location_id=state.location_id,
                    weather=snapshot.weather,
                    body_state=state.body_state,
                    visible_agents=visible_agents,
                    available_actions=tuple(sorted(SUPPORTED_ACTION_TYPES)),
                    available_location_ids=self._available_locations(
                        agent_config=self._agent_configs[agent.id],
                        location_id=state.location_id,
                        snapshot=snapshot,
                    ),
                )
            )
        return tuple(observations)

    def _available_locations(
        self,
        *,
        agent_config: AgentConfig,
        location_id: LocationId,
        snapshot: WorldSnapshot,
    ) -> tuple[LocationId, ...]:
        location_states = {
            state.location_id: state for state in snapshot.location_states
        }
        return tuple(
            target
            for target in sorted(
                self._locations.get(location_id).connected_locations,
                key=str,
            )
            if location_states[target].is_open
            and (
                location_states[target].is_public
                or target == agent_config.home_location_id
            )
        )


class TickCoordinator:
    """Collect all proposals from one snapshot, then resolve and commit."""

    def __init__(
        self,
        *,
        config: ConfigBundle,
        context: RunContext,
        world_state: WorldState,
        world_log: WorldLog,
    ) -> None:
        self._config = config
        self._context = context
        self._world_state = world_state
        self._world_log = world_log
        self._events = EventFactory(
            run_id=str(context.run_id),
            ids=context.ids,
            world_log=world_log,
        )
        self._validator = ActionValidator(config=config)
        self._executor = ActionExecutor(
            world_state=world_state,
            validator=self._validator,
            events=self._events,
        )
        self._observations = ObservationBuilder(config=config, world_state=world_state)

    def run_tick(
        self,
        *,
        agents: tuple[Agent, ...],
        policy: ProposalPolicy,
    ) -> TickReport:
        checkpoint = self._world_state.checkpoint()
        random_snapshot = self._context.random.snapshot()
        ids_snapshot = self._context.ids.snapshot()
        log_length = len(self._world_log.events)
        policy_checkpoint = _policy_checkpoint(policy)
        try:
            return self._run_tick(agents=agents, policy=policy, log_length=log_length)
        except Exception as error:
            self._context.random.restore(random_snapshot)
            self._context.ids.restore(ids_snapshot)
            self._world_log.truncate(log_length)
            self._world_state.restore_checkpoint(
                checkpoint=checkpoint,
                config=self._config,
                random=self._context.random,
            )
            _restore_policy(policy, policy_checkpoint)
            if isinstance(error, TickTransactionError):
                raise
            raise TickTransactionError("tick transaction rolled back") from error

    def _run_tick(
        self,
        *,
        agents: tuple[Agent, ...],
        policy: ProposalPolicy,
        log_length: int,
    ) -> TickReport:
        day = self._world_state.clock.day
        time_block = self._world_state.clock.time_block
        previous_weather = self._world_state.weather.current
        weather_change = self._world_state.weather.advance(
            day=day,
            time_block=time_block,
        )
        if (
            weather_change is not None
            and weather_change.previous != weather_change.current
        ):
            self._events.weather_event(
                change=weather_change,
                location_id=self._config.locations[0].id,
            )

        source_snapshot = self._world_state.snapshot()
        observations = self._observations.build_all(
            snapshot=source_snapshot,
            agents=agents,
        )
        observation_by_agent = {
            observation.observer_id: observation for observation in observations
        }
        proposals = self._collect_proposals(
            agents=agents,
            policy=policy,
            observation_by_agent=observation_by_agent,
        )
        if self._world_state.snapshot() != source_snapshot:
            raise TickTransactionError("proposal phase modified WorldState")

        validations = {
            proposal.action_id: self._validator.validate(proposal, self._world_state)
            for proposal in proposals
        }
        accepted, conflict_reasons = self._resolve_conflicts(
            proposals=proposals,
            validations=validations,
        )
        results_by_action: dict[ActionId, ActionResult] = {}
        for proposal in proposals:
            validation = validations[proposal.action_id]
            if not validation.success:
                results_by_action[proposal.action_id] = ActionResult(
                    action_id=proposal.action_id,
                    success=False,
                    reason=validation.reason,
                )
            elif proposal.action_id in conflict_reasons:
                results_by_action[proposal.action_id] = ActionResult(
                    action_id=proposal.action_id,
                    success=False,
                    reason=conflict_reasons[proposal.action_id],
                )
        for proposal in sorted(accepted, key=lambda item: str(item.action_id)):
            result = self._executor.execute(proposal)
            if not result.success:
                raise TickTransactionError(
                    f"prevalidated action failed during commit: {proposal.action_id}"
                )
            results_by_action[proposal.action_id] = result

        self._world_state.increment_tick()
        record = WorldTickRecord(
            tick=self._world_state.tick,
            day=day,
            time_block=time_block,
            previous_weather=previous_weather,
            weather=self._world_state.weather.current,
            weather_changed=(
                weather_change is not None
                and weather_change.previous != weather_change.current
            ),
        )
        self._world_state.clock.advance()
        self._world_state.validate_invariants()
        return TickReport(
            tick=record.tick,
            source_snapshot=source_snapshot,
            observations=observations,
            proposals=proposals,
            results=tuple(
                results_by_action[proposal.action_id]
                for proposal in sorted(proposals, key=lambda item: str(item.action_id))
            ),
            events=self._world_log.events[log_length:],
            record=record,
        )

    def _collect_proposals(
        self,
        *,
        agents: tuple[Agent, ...],
        policy: ProposalPolicy,
        observation_by_agent: dict[AgentId, Observation],
    ) -> tuple[ActionProposal, ...]:
        if len({agent.id for agent in agents}) != len(agents):
            raise TickTransactionError("tick agents must be unique")
        proposals: list[ActionProposal] = []
        for agent in sorted(agents, key=lambda item: str(item.id)):
            proposal = policy.propose(
                agent=agent,
                observation=observation_by_agent[agent.id],
                context=self._context,
            )
            if proposal.agent_id != agent.id:
                raise TickTransactionError("policy proposal agent does not match actor")
            proposals.append(proposal)
        if len({proposal.action_id for proposal in proposals}) != len(proposals):
            raise TickTransactionError("tick proposal action IDs must be unique")
        return tuple(proposals)

    def _resolve_conflicts(
        self,
        *,
        proposals: tuple[ActionProposal, ...],
        validations: dict[ActionId, ActionValidation],
    ) -> tuple[tuple[ActionProposal, ...], dict[ActionId, str]]:
        valid = [
            proposal
            for proposal in sorted(proposals, key=lambda item: str(item.action_id))
            if validations[proposal.action_id].success
        ]
        priorities = {
            proposal.action_id: self._context.random.random() for proposal in valid
        }
        accepted: list[ActionProposal] = []
        used_resources: set[str] = set()
        conflict_reasons: dict[ActionId, str] = {}
        for proposal in sorted(
            valid,
            key=lambda item: (-priorities[item.action_id], str(item.action_id)),
        ):
            resources = _conflict_resources(proposal)
            if used_resources.intersection(resources):
                conflict_reasons[proposal.action_id] = (
                    "conflict lost by seed-controlled priority"
                )
                continue
            used_resources.update(resources)
            accepted.append(proposal)
        return tuple(accepted), conflict_reasons


def _conflict_resources(proposal: ActionProposal) -> frozenset[str]:
    resources = {f"actor:{proposal.agent_id}"}
    if proposal.action_type == "talk" and proposal.target_agent_id is not None:
        resources.add(f"actor:{proposal.target_agent_id}")
    return frozenset(resources)


def _policy_checkpoint(policy: ProposalPolicy) -> object | None:
    checkpoint = getattr(policy, "checkpoint", None)
    return checkpoint() if callable(checkpoint) else None


def _restore_policy(policy: ProposalPolicy, checkpoint: object | None) -> None:
    if checkpoint is None:
        return
    restore = getattr(policy, "restore", None)
    if callable(restore):
        restore(checkpoint)
