from dataclasses import replace

import pytest

from town_diary.core.config import load_config_bundle
from town_diary.simulation.runtime import (
    RuntimeEndReason,
    RuntimeLifecycleError,
    RuntimeStatus,
    WorldRuntime,
)


def make_runtime(seed: int = 42) -> WorldRuntime:
    return WorldRuntime.create(config=load_config_bundle("configs"), seed=seed)


def test_world_runtime_has_explicit_lifecycle() -> None:
    runtime = make_runtime()

    assert runtime.status is RuntimeStatus.CREATED
    runtime.start()
    runtime.step()
    runtime.pause()
    runtime.resume()
    runtime.end()

    assert runtime.status is RuntimeStatus.ENDED
    assert runtime.end_reason is RuntimeEndReason.STOPPED
    with pytest.raises(RuntimeLifecycleError):
        runtime.step()


def test_world_mode_runs_seven_days_without_agent_or_writing_components() -> None:
    runtime = make_runtime()

    summary = runtime.run_days(7)

    assert summary.status is RuntimeStatus.ENDED
    assert summary.end_reason is RuntimeEndReason.COMPLETED
    assert summary.days_completed == 7
    assert summary.ticks_completed == 35
    assert summary.current_day == 8
    assert len(runtime.records) == 35
    assert {record.day for record in runtime.records} == set(range(1, 8))
    assert not hasattr(runtime, "agents")
    assert not hasattr(runtime, "recorder")
    assert not hasattr(runtime, "writer")


def test_world_runtime_runs_when_novelist_is_removed() -> None:
    config = load_config_bundle("configs")
    without_novelist = replace(
        config,
        agents=tuple(agent for agent in config.agents if agent.role != "novelist"),
    )
    runtime = WorldRuntime.create(config=without_novelist, seed=42)

    summary = runtime.run_days(7)

    assert summary.days_completed == 7
    assert all(
        agent.agent_id != "novelist"
        for agent in runtime.snapshot().agent_states
    )


def test_world_runtime_output_is_deterministic_and_objective() -> None:
    first = make_runtime(seed=17)
    second = make_runtime(seed=17)

    first.run_days(7)
    second.run_days(7)

    assert first.records == second.records
    assert first.summary() == second.summary()
    assert all(record.tick > 0 for record in first.records)
