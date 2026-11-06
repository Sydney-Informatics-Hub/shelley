"""Textual pickers for shelley (docs/reference/style-guide.md, "Pickers").

Kept off the CLI's import path: Textual is imported only inside the functions that open a widget.
"""

import os
import sys

MOUSE_ENV = "SHELLEY_MOUSE"
NO_MOUSE_FLAG = "--no-mouse"


def mouse_enabled(no_mouse_flag: bool = False) -> bool:
    """Mouse is on unless `--no-mouse` was given or SHELLEY_MOUSE=0 is set."""
    return not no_mouse_flag and os.environ.get(MOUSE_ENV, "1").strip() != "0"


def interactive_terminal() -> bool:
    """True when a picker can open: keys come from stdin and Textual draws on stderr."""
    return sys.stdin.isatty() and sys.stderr.isatty()


def alias_picker(
    aliases: list[dict],
    container: str,
    version: str,
    *,
    mouse: bool = True,
    command: str = "shelley",
):
    """Open the alias picker inline (docs/reference/alias-picker.md).

    `aliases` is the canonical ``[{"name", "command"}]`` list. Returns the ticked aliases as
    ``PickedAlias`` (with the name before any rename) on Confirm, or None when the user cancels.
    """
    from .alias_picker import AliasPickerApp

    app = AliasPickerApp(aliases, container, version, mouse=mouse, command=command)
    return app.run(inline=True, mouse=mouse)
