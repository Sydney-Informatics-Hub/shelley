#!/usr/bin/env python3
"""Shelley CLI entry point."""
# TODO: Add docstring to inform agent rules: this file should contain the
# direct command-line interface. Helper functions, and style/rendering
# functions always end up here. They should not. These should be imported from
# the relevant modules.

import sys

from ..commands.interactive import interactive_mode
from ..utils.commands import CORE_COMMANDS
from ..utils.style import (
    ShelleyStyle,
    console,
    print_banner,
    print_rule,
    print_update_notice,
    print_version,
)
from .build import run as run_build
from .discovery import run_clean, run_find, run_search


def _print_usage() -> None:
    console.clear()
    print_banner()
    print_rule("Command Usage", "secondary")

    usage_commands = [
        {**c, "example": f"shelley {c['example']}"} for c in CORE_COMMANDS
    ] + [
        {
            "command": "interactive",
            "description": "Start interactive mode",
            "example": "shelley interactive",
        },
        {
            "command": "update",
            "description": "Upgrade shelley to the latest version",
            "example": "shelley update",
        },
        {
            "command": "help",
            "description": "Show this help message",
            "example": "shelley help",
        },
    ]

    usage_table = ShelleyStyle.create_help_table(usage_commands)
    console.print(usage_table)
    console.print("\n")
    console.print(ShelleyStyle.format_command_examples())
    print_rule()
    print_update_notice()


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 2:
        _print_usage()
        sys.exit(1)

    command = sys.argv[1].lower()

    if command in ("help", "--help", "-h"):
        _print_usage()
        sys.exit(0)

    if command in ("--version", "-V"):
        print_version()
        sys.exit(0)

    if command == "build":
        sys.exit(run_build(sys.argv[2:]))

    if command == "find":
        sys.exit(run_find(sys.argv[2:]))

    if command == "search":
        sys.exit(run_search(sys.argv[2:]))

    if command == "clean":
        sys.exit(run_clean(sys.argv[2:]))

    if command == "interactive":
        interactive_mode()
        sys.exit(0)

    if command == "update":
        from ..commands.update import update_shelley

        sys.exit(update_shelley())

    console.print(
        ShelleyStyle.create_error_panel(
            "Unknown Command",
            f"Unknown command: '{command}'",
            "Run shelley --help for usage",
        )
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
