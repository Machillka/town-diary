"""Deterministic objective WorldEvent construction."""

from town_diary.core.contracts import ActionProposal, EventFact, NamedValue, WorldEvent
from town_diary.core.ids import DeterministicIdGenerator, LocationId
from town_diary.events.log import WorldLog
from town_diary.simulation.weather import WeatherChange
from town_diary.simulation.world_state import WorldState


class EventFactory:
    """Environment-only factory that appends structured objective facts."""

    def __init__(
        self,
        *,
        run_id: str,
        ids: DeterministicIdGenerator,
        world_log: WorldLog,
    ) -> None:
        self._run_id = run_id
        self._ids = ids
        self._world_log = world_log

    def action_event(
        self,
        *,
        proposal: ActionProposal,
        current_location_id: LocationId,
        effects: tuple[NamedValue, ...],
        world_state: WorldState,
    ) -> WorldEvent:
        location_id = (
            proposal.target_location_id
            if proposal.action_type == "move" and proposal.target_location_id is not None
            else current_location_id
        )
        participants = [proposal.agent_id]
        if proposal.target_agent_id is not None:
            participants.append(proposal.target_agent_id)
        facts = [
            EventFact("action_type", proposal.action_type),
            *(EventFact(f"effect_{effect.name}", effect.value) for effect in effects),
        ]
        if proposal.target_location_id is not None:
            facts.append(EventFact("target_location_id", str(proposal.target_location_id)))
        if proposal.target_agent_id is not None:
            facts.append(EventFact("target_agent_id", str(proposal.target_agent_id)))
        event = WorldEvent(
            event_id=self._ids.next_event_id(),
            run_id=self._run_id,
            day=world_state.clock.day,
            time_block=world_state.clock.time_block,
            location_id=location_id,
            event_type=f"agent_{proposal.action_type}",
            participants=tuple(participants),
            summary=_action_summary(proposal, location_id),
            facts=tuple(facts),
            source_action_id=proposal.action_id,
        )
        self._world_log.append(event)
        return event

    def weather_event(
        self,
        *,
        change: WeatherChange,
        location_id: LocationId,
    ) -> WorldEvent:
        event = WorldEvent(
            event_id=self._ids.next_event_id(),
            run_id=self._run_id,
            day=change.day,
            time_block=change.time_block,
            location_id=location_id,
            event_type="weather_changed",
            participants=(),
            summary=f"Weather changed from {change.previous.value} to {change.current.value}.",
            facts=(
                EventFact("previous_weather", change.previous.value),
                EventFact("weather", change.current.value),
            ),
        )
        self._world_log.append(event)
        return event


def _action_summary(proposal: ActionProposal, location_id: LocationId) -> str:
    target = ""
    if proposal.target_agent_id is not None:
        target = f" with {proposal.target_agent_id}"
    elif proposal.target_location_id is not None:
        target = f" toward {proposal.target_location_id}"
    return f"{proposal.agent_id} committed {proposal.action_type}{target} at {location_id}."
