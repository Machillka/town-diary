"""Rule-based seven-day town simulation using the shared WorldRuntime."""

from dataclasses import replace

from town_diary.agents import Agent, RuleDecisionPolicy, load_agents
from town_diary.core.config import ConfigBundle
from town_diary.simulation.clock import TIME_BLOCKS
from town_diary.simulation.runtime import (
    RuntimeEndReason,
    RuntimeLifecycleError,
    RuntimeStatus,
    WorldRunSummary,
    WorldRuntime,
)
from town_diary.simulation.tick import TickCoordinator, TickReport


class RuleBasedTownSimulation:
    """Compose Agents and two-phase ticks around the same WorldRuntime lifecycle."""

    def __init__(
        self,
        *,
        runtime: WorldRuntime,
        agents: tuple[Agent, ...],
        policy: RuleDecisionPolicy,
    ) -> None:
        self.runtime = runtime
        self.agents = agents
        self.policy = policy
        self._coordinator = TickCoordinator(
            config=runtime.config,
            context=runtime.context,
            world_state=runtime.world_state,
            world_log=runtime.world_log,
        )
        self._reports: list[TickReport] = []

    @classmethod
    def create(cls, *, config: ConfigBundle, seed: int) -> "RuleBasedTownSimulation":
        return cls(
            runtime=WorldRuntime.create(config=config, seed=seed),
            agents=load_agents(config.agents),
            policy=RuleDecisionPolicy(),
        )

    @classmethod
    def create_world_mode(
        cls,
        *,
        config: ConfigBundle,
        seed: int,
    ) -> "RuleBasedTownSimulation":
        """Create a resident world with no novelist, Recorder, or Writing."""
        resident_config = replace(
            config,
            agents=tuple(agent for agent in config.agents if agent.role != "novelist"),
        )
        return cls.create(config=resident_config, seed=seed)

    @property
    def reports(self) -> tuple[TickReport, ...]:
        return tuple(self._reports)

    def step(self) -> TickReport:
        if self.runtime.status is RuntimeStatus.CREATED:
            self.runtime.start()
        if self.runtime.status is not RuntimeStatus.RUNNING:
            raise RuntimeLifecycleError("rule simulation runtime must be running")
        report = self._coordinator.run_tick(agents=self.agents, policy=self.policy)
        self.runtime.record_committed_tick(report.record)
        self._reports.append(report)
        return report

    def run_days(self, days: int) -> WorldRunSummary:
        if not isinstance(days, int) or days < 1:
            raise ValueError("days must be a positive integer")
        for _ in range(days * len(TIME_BLOCKS)):
            self.step()
        self.runtime.end(RuntimeEndReason.COMPLETED)
        return self.runtime.summary()
