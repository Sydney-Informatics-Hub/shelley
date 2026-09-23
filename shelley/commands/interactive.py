"""Interactive command — guided REPL for shelley."""

from .build import build_module
from .clean import clean_module
from .find import find_tool_sync
from .search import search_tools
from ..utils.args import parse_build_flags, parse_force_flag, parse_verbose
from ..utils.commands import CORE_COMMANDS
from ..utils.style import (
    console, ShelleyStyle, print_banner, print_rule,
    print_warning, print_info, print_success,
)

_COMMANDS = CORE_COMMANDS + [
    {"command": "help", "description": "Show this help table",  "example": "help"},
    {"command": "exit", "description": "Exit interactive mode", "example": "exit"},
]


def interactive_mode() -> None:
    """Guided REPL — dispatches user input to command functions."""
    console.clear()
    print_banner()
    help_table = ShelleyStyle.create_help_table(_COMMANDS)
    console.print(help_table)
    print_rule()

    while True:
        try:
            raw = console.input("\n[prompt]shelley>[/prompt] ").strip()
        except (KeyboardInterrupt, EOFError):
            print_info("\nExiting interactive mode...")
            break

        if not raw:
            continue

        parts = raw.split()
        cmd = parts[0].lower()

        if cmd in ("exit", "quit", "q"):
            print_success("Goodbye!")
            break
        elif cmd == "help":
            console.print(help_table)
        elif cmd == "find":
            verbose, positional = parse_verbose(parts[1:])
            if positional:
                find_tool_sync(positional[0], verbose=verbose)
            else:
                print_warning("Usage: find <tool_name> [-v]")
        elif cmd == "search":
            if len(parts) > 1:
                search_tools(" ".join(parts[1:]))
            else:
                print_warning("Usage: search <description>")
        elif cmd == "build":
            interactive, positional = parse_build_flags(parts[1:])
            if positional:
                build_module(positional[0], interactive=interactive)
            else:
                print_warning("Usage: build <tool_name>[/version] [-i|--interactive]")
        elif cmd == "clean":
            force, positional = parse_force_flag(parts[1:])
            if positional:
                clean_module(positional[0], force=force)
            else:
                print_warning("Usage: clean <tool>:<version> [-y]")
        else:
            print_warning(f"Unknown command: '{cmd}'. Type help for usage.")
