"""Public command-line entry point."""

from collections.abc import Sequence

from town_diary.app.cli import run_cli


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Town Diary command-line interface."""
    return run_cli(argv)
