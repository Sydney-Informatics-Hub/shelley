"""Interactive command — guided REPL for shelley."""

from ..client.build import run as run_build
from ..client.discovery import run_clean, run_find, run_search
from ..utils.commands import CORE_COMMANDS
from ..utils.style import (
    ShelleyStyle,
    console,
    print_banner,
    print_info,
    print_rule,
    print_success,
    print_warning,
)

_COMMANDS = CORE_COMMANDS + [
    {"command": "help", "description": "Show this help table", "example": "help"},
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
            run_find(parts[1:])
        elif cmd == "search":
            run_search(parts[1:])
        elif cmd == "build":
            run_build(parts[1:])
        elif cmd == "clean":
            run_clean(parts[1:])
        else:
            print_warning(f"Unknown command: '{cmd}'. Type help for usage.")
