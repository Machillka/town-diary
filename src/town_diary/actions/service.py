"""Environment-side ActionProposal validation and execution."""

from dataclasses import dataclass

from town_diary.core.config import AgentConfig, ConfigBundle
from town_diary.core.contracts import ActionProposal, ActionResult, NamedValue
from town_diary.core.ids import AgentId, LocationId
from town_diary.events.factory import EventFactory
from town_diary.simulation.world_state import WorldState

SUPPORTED_ACTION_TYPES = frozenset(
    {"stay", "move", "work", "rest", "observe", "talk", "write_notes"}
)
ACTIVE_ACTION_TYPES = frozenset({"move", "work", "observe", "talk", "write_notes"})


@dataclass(frozen=True, slots=True)
class ActionValidation:
    success: bool
    reason: str
    action_type: str
    agent_id: AgentId
    current_location_id: LocationId | None
    target_location_id: LocationId | None = None
    target_agent_id: AgentId | None = None


class ActionValidator:
    """Read-only Environment policy for deciding whether intent may occur."""

    def __init__(self, *, config: ConfigBundle) -> None:
        self._agents = {agent.id: agent for agent in config.agents}

    def validate(
        self,
        proposal: ActionProposal,
        world_state: WorldState,
    ) -> ActionValidation:
        if proposal.action_type not in SUPPORTED_ACTION_TYPES:
            return self._failure(proposal, "unknown action type")
        agent_config = self._agents.get(proposal.agent_id)
        if agent_config is None:
            return self._failure(proposal, "unknown agent")
        try:
            current_location = world_state.location_of(proposal.agent_id)
        except KeyError:
            return self._failure(proposal, "agent is missing from WorldState")
        if (
            proposal.action_type in ACTIVE_ACTION_TYPES
            and _body_value(world_state, proposal.agent_id, "energy", 100.0) <= 0
        ):
            return self._failure(
                proposal,
                "agent has no energy for this action",
                current_location=current_location,
            )

        method = getattr(self, f"_validate_{proposal.action_type}")
        reason = method(
            proposal=proposal,
            world_state=world_state,
            agent_config=agent_config,
            current_location=current_location,
        )
        if reason is not None:
            return self._failure(
                proposal,
                reason,
                current_location=current_location,
            )
        return ActionValidation(
            success=True,
            reason="action accepted",
            action_type=proposal.action_type,
            agent_id=proposal.agent_id,
            current_location_id=current_location,
            target_location_id=proposal.target_location_id,
            target_agent_id=proposal.target_agent_id,
        )

    def _validate_stay(
        self,
        *,
        proposal: ActionProposal,
        **_: object,
    ) -> str | None:
        return _unexpected_targets(proposal)

    def _validate_move(
        self,
        *,
        proposal: ActionProposal,
        world_state: WorldState,
        agent_config: AgentConfig,
        current_location: LocationId,
        **_: object,
    ) -> str | None:
        if proposal.target_agent_id is not None:
            return "move does not accept a target agent"
        target = proposal.target_location_id
        if target is None:
            return "move requires a target location"
        if not world_state.locations.exists(target):
            return "target location does not exist"
        if not world_state.locations.are_connected(current_location, target):
            return "target location is not adjacent"
        if not world_state.locations.is_open(target, world_state.clock.time_block):
            return "target location is closed"
        location = world_state.locations.get(target)
        if not location.is_public and target != agent_config.home_location_id:
            return "target private location is not the agent's home"
        return None

    def _validate_work(
        self,
        *,
        proposal: ActionProposal,
        world_state: WorldState,
        agent_config: AgentConfig,
        current_location: LocationId,
        **_: object,
    ) -> str | None:
        targets = _unexpected_targets(proposal)
        if targets is not None:
            return targets
        if agent_config.role == "novelist":
            return "novelist uses write_notes instead of work"
        if not world_state.locations.is_open(current_location, world_state.clock.time_block):
            return "current work location is closed"
        if not any(
            habit.target_location_id == current_location
            and world_state.clock.time_block in habit.preferred_time_blocks
            for habit in agent_config.habits
        ):
            return "no active work habit at the current location"
        return None

    def _validate_rest(
        self,
        *,
        proposal: ActionProposal,
        **_: object,
    ) -> str | None:
        return _unexpected_targets(proposal)

    def _validate_observe(
        self,
        *,
        proposal: ActionProposal,
        **_: object,
    ) -> str | None:
        return _unexpected_targets(proposal)

    def _validate_talk(
        self,
        *,
        proposal: ActionProposal,
        world_state: WorldState,
        current_location: LocationId,
        **_: object,
    ) -> str | None:
        if proposal.target_location_id is not None:
            return "talk does not accept a target location"
        target = proposal.target_agent_id
        if target is None:
            return "talk requires a target agent"
        if target == proposal.agent_id:
            return "agent cannot talk to itself"
        try:
            target_location = world_state.location_of(target)
        except KeyError:
            return "target agent does not exist"
        if target_location != current_location:
            return "target agent is not at the same location"
        return None

    def _validate_write_notes(
        self,
        *,
        proposal: ActionProposal,
        agent_config: AgentConfig,
        **_: object,
    ) -> str | None:
        targets = _unexpected_targets(proposal)
        if targets is not None:
            return targets
        if agent_config.role != "novelist":
            return "only the novelist can write notes"
        return None

    @staticmethod
    def _failure(
        proposal: ActionProposal,
        reason: str,
        *,
        current_location: LocationId | None = None,
    ) -> ActionValidation:
        return ActionValidation(
            success=False,
            reason=reason,
            action_type=proposal.action_type,
            agent_id=proposal.agent_id,
            current_location_id=current_location,
            target_location_id=proposal.target_location_id,
            target_agent_id=proposal.target_agent_id,
        )


class ActionExecutor:
    """The only Environment-side entry point that commits accepted behavior."""

    def __init__(
        self,
        *,
        world_state: WorldState,
        validator: ActionValidator,
        events: EventFactory,
    ) -> None:
        self._world_state = world_state
        self._validator = validator
        self._events = events

    def execute(self, proposal: ActionProposal) -> ActionResult:
        validation = self._validator.validate(proposal, self._world_state)
        if not validation.success:
            return ActionResult(
                action_id=proposal.action_id,
                success=False,
                reason=validation.reason,
            )

        effects = self._commit(proposal)
        self._world_state.validate_invariants()
        assert validation.current_location_id is not None
        event = self._events.action_event(
            proposal=proposal,
            current_location_id=validation.current_location_id,
            effects=effects,
            world_state=self._world_state,
        )
        return ActionResult(
            action_id=proposal.action_id,
            success=True,
            reason="action committed",
            events=(event,),
            effects=effects,
        )

    def _commit(self, proposal: ActionProposal) -> tuple[NamedValue, ...]:
        if proposal.action_type == "move":
            assert proposal.target_location_id is not None
            self._world_state.move_agent(proposal.agent_id, proposal.target_location_id)
            return (NamedValue("location_id", str(proposal.target_location_id)),)
        if proposal.action_type == "work":
            return self._change_body(proposal.agent_id, energy=-10, hunger=10)
        if proposal.action_type == "rest":
            return self._change_body(proposal.agent_id, energy=20, hunger=5)
        if proposal.action_type == "talk":
            return self._change_body(proposal.agent_id, energy=-2, hunger=2)
        return ()

    def _change_body(
        self,
        agent_id: AgentId,
        *,
        energy: float,
        hunger: float,
    ) -> tuple[NamedValue, ...]:
        current = {
            item.name: item.value for item in self._world_state.body_state_of(agent_id)
        }
        next_energy = _clamp(_numeric(current.get("energy"), 100.0) + energy)
        next_hunger = _clamp(_numeric(current.get("hunger"), 0.0) + hunger)
        updated = {**current, "energy": next_energy, "hunger": next_hunger}
        self._world_state.set_body_state(agent_id, updated)
        return (
            NamedValue("energy", next_energy),
            NamedValue("hunger", next_hunger),
        )


def _unexpected_targets(proposal: ActionProposal) -> str | None:
    if proposal.target_location_id is not None or proposal.target_agent_id is not None:
        return f"{proposal.action_type} does not accept targets"
    return None


def _body_value(
    world_state: WorldState,
    agent_id: AgentId,
    name: str,
    default: float,
) -> float:
    values = {item.name: item.value for item in world_state.body_state_of(agent_id)}
    return _numeric(values.get(name), default)


def _numeric(value: object, default: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


def _clamp(value: float) -> float:
    return min(100.0, max(0.0, value))
