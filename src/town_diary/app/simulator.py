"""Application-level simulator placeholder for the bootstrap step."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SimulationRequest:
    """Validated request passed from the CLI to the application layer."""

    days: int
    seed: int
    config_dir: str
    output_dir: str
    mode: str
    llm: str


class Simulator:
    """Bootstrap simulator that reports configuration without simulating."""

    def run(self, request: SimulationRequest) -> int:
        """Report the requested run.

        World, agent, perception, and writing behavior intentionally belong to
        later implementation steps.
        """
        print("Simulation started.")
        print(f"days={request.days}")
        print(f"seed={request.seed}")
        print(f"config={request.config_dir}")
        print(f"output={request.output_dir}")
        print(f"mode={request.mode}")
        print(f"llm={request.llm}")
        print("Simulation finished.")
        return 0
