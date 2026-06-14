"""Rule-based Agent decision selection and audit records."""

from dataclasses import dataclass

from town_diary.agents.candidates import CandidateAction, ScoreContribution
from town_diary.agents.model import Agent
from town_diary.core.contracts import ActionProposal, Observation
from town_diary.core.ids import AgentId
from town_diary.core.run_context import RunContext


@dataclass(frozen=True, slots=True)
class DecisionAudit:
    agent_id: AgentId
    observation: Observation
    candidates: tuple[CandidateAction, ...]
    selected: CandidateAction
    proposal: ActionProposal
    used_fallback: bool


class RuleDecisionPolicy:
    """Choose the highest explainable candidate with an explicit fallback."""

    def __init__(self) -> None:
        self._decisions: list[DecisionAudit] = []

    @property
    def decisions(self) -> tuple[DecisionAudit, ...]:
        return tuple(self._decisions)

    def checkpoint(self) -> int:
        return len(self._decisions)

    def restore(self, checkpoint: int) -> None:
        if not isinstance(checkpoint, int) or checkpoint < 0 or checkpoint > len(self._decisions):
            raise ValueError("decision audit checkpoint is invalid")
        del self._decisions[checkpoint:]

    def propose(
        self,
        *,
        agent: Agent,
        observation: Observation,
        context: RunContext,
    ) -> ActionProposal:
        candidates = agent.generate_candidates(observation, context.random)
        used_fallback = not candidates
        selected = candidates[0] if candidates else _fallback_candidate()
        proposal = agent.propose(
            selected,
            action_id=context.ids.next_action_id(),
        )
        self._decisions.append(
            DecisionAudit(
                agent_id=agent.id,
                observation=observation,
                candidates=candidates,
                selected=selected,
                proposal=proposal,
                used_fallback=used_fallback,
            )
        )
        return proposal


def _fallback_candidate() -> CandidateAction:
    contribution = ScoreContribution(
        source="fallback",
        value=0.0,
        reason="no available scored candidate; stay safely",
    )
    return CandidateAction(
        action_type="stay",
        reason=contribution.reason,
        score=0.0,
        contributions=(contribution,),
    )
