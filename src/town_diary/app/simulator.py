"""Application-level simulation entry point."""

from dataclasses import dataclass

from town_diary.core.config import load_config_bundle
from town_diary.simulation.town import RuleBasedTownSimulation


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
    """Run implemented simulation modes and report their result."""

    def run(self, request: SimulationRequest) -> int:
        """Run world mode or report later modes that are not implemented yet."""
        print("Simulation started.")
        print(f"days={request.days}")
        print(f"seed={request.seed}")
        print(f"config={request.config_dir}")
        print(f"output={request.output_dir}")
        print(f"mode={request.mode}")
        print(f"llm={request.llm}")
        if request.mode == "world":
            simulation = RuleBasedTownSimulation.create_world_mode(
                config=load_config_bundle(request.config_dir),
                seed=request.seed,
            )
            summary = simulation.run_days(request.days)
            for record in simulation.runtime.records:
                if record.weather_changed:
                    print(
                        "weather_change="
                        f"day:{record.day},time:{record.time_block.value},"
                        f"from:{record.previous_weather.value},to:{record.weather.value}"
                    )
            print(
                "world_summary="
                f"ticks:{summary.ticks_completed},days:{summary.days_completed},"
                f"weather_changes:{summary.weather_changes},"
                f"world_events:{summary.world_events},"
                f"end_reason:{summary.end_reason.value}"
            )
        print("Simulation finished.")
        return 0
