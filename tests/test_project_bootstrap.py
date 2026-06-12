from dataclasses import FrozenInstanceError

import pytest

from town_diary.app.cli import run_cli
from town_diary.app.simulator import SimulationRequest, Simulator


def test_cli_accepts_simulation_bootstrap_arguments(capsys) -> None:
    exit_code = run_cli(
        [
            "simulate",
            "--days",
            "3",
            "--seed",
            "17",
            "--config",
            "example-configs",
            "--output",
            "outputs/test_run",
            "--mode",
            "observe",
            "--llm",
            "mock",
        ]
    )

    assert exit_code == 0
    assert capsys.readouterr().out.splitlines() == [
        "Simulation started.",
        "days=3",
        "seed=17",
        "config=example-configs",
        "output=outputs/test_run",
        "mode=observe",
        "llm=mock",
        "Simulation finished.",
    ]


def test_simulation_request_is_immutable() -> None:
    request = SimulationRequest(
        days=1,
        seed=42,
        config_dir="configs",
        output_dir="outputs/run_001",
        mode="world",
        llm="mock",
    )

    assert request.days == 1
    assert request.mode == "world"
    assert Simulator().run(request) == 0

    with pytest.raises(FrozenInstanceError):
        request.days = 2  # type: ignore[misc]


def test_cli_rejects_non_positive_days() -> None:
    with pytest.raises(SystemExit) as error:
        run_cli(["simulate", "--days", "0"])

    assert error.value.code == 2
