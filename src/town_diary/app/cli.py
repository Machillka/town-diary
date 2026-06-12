"""Minimal CLI used to verify the project bootstrap."""

import argparse
from collections.abc import Sequence

from town_diary.app.simulator import SimulationRequest, Simulator


def build_parser() -> argparse.ArgumentParser:
    """Build the root command-line parser."""
    parser = argparse.ArgumentParser(prog="town-diary")
    subparsers = parser.add_subparsers(dest="command", required=True)

    simulate = subparsers.add_parser(
        "simulate",
        help="Start a town simulation run.",
    )
    simulate.add_argument("--days", type=_positive_int, default=7)
    simulate.add_argument("--seed", type=int, default=42)
    simulate.add_argument("--config", default="configs")
    simulate.add_argument("--output", default="outputs/run_001")
    simulate.add_argument(
        "--mode",
        choices=("world", "observe", "full"),
        default="full",
    )
    simulate.add_argument("--llm", choices=("mock",), default="mock")

    return parser


def run_cli(argv: Sequence[str] | None = None) -> int:
    """Parse CLI arguments and invoke the application boundary."""
    args = build_parser().parse_args(argv)

    if args.command == "simulate":
        request = SimulationRequest(
            days=args.days,
            seed=args.seed,
            config_dir=args.config,
            output_dir=args.output,
            mode=args.mode,
            llm=args.llm,
        )
        return Simulator().run(request)

    raise AssertionError(f"Unhandled command: {args.command}")


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed
