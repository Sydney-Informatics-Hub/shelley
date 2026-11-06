"""On-screen copy for the alias picker (docs/reference/alias-picker.md, "Copy deck"), verbatim.

The only three verbs are alias, tick and rename. Builders here return the exact lines drawn in
docs/reference/alias-picker-screens.md, so they can be checked cell for cell.
"""

from rich.cells import cell_len
from rich.text import Text

from ..utils.style import MORE_ABOVE, MORE_BELOW, POINTER, SEP, TICK_OFF, TICK_ON
from .alias_layout import ColumnLayout, shorten_alias, shorten_path, truncate

# Title bar
TITLE_LEFT = "Choose aliases — {container} {version}"
TITLE_RIGHT = "{command} build"
TITLE_RIGHT_NOMOUSE = "Keyboard only"

# Instructions
HELP_LINE1 = (
    "Click [ ] to tick the aliases you'll use. You can rebuild later to add more."
)
HELP_LINE2 = "Click a name to rename it. The Command column needs no action."
HELP_LINE1_NOMOUSE = (
    "Press Space to tick the aliases you'll use. You can rebuild later to add more."
)
HELP_LINE2_NOMOUSE = (
    "Press R to rename the highlighted alias. The Command column needs no action."
)

# Column headings and cells
COL_INCLUDE = "Include"
COL_ALIAS = "Alias name"
COL_COMMAND = "Command"
TICK = {True: TICK_ON, False: TICK_OFF}

# List footer
COUNT = "{n} of {total} ticked"
SCROLL_BELOW = f"{MORE_BELOW} {{n}} more below"
SCROLL_ABOVE = f"{MORE_ABOVE} {{n}} more above"
SCROLL_ALL = "All {total} shown"
MSG_RENAME_SAVED = "Renamed {old} to {new} and ticked it."
MSG_RENAME_SAVED_TICKED = "Renamed {old} to {new}."  # the row was already ticked
MSG_RENAME_CANCELLED = "Rename cancelled. Kept {old}."
MSG_CONFIRM_EMPTY = "Tick at least one alias first."

# Buttons
BTN_CONFIRM = "Confirm"
BTN_CANCEL = "Cancel"
BTN_CONFIRM_REASON = "Tick at least one alias to confirm"

# Dialog
DLG_TITLE = "Discard and exit?"
DLG_BODY = "Nothing will be built, and your ticks and renames will be lost."
DLG_KEEP = "Keep editing"
DLG_DISCARD = "Discard and exit"

# After the widget
CANCEL_LINE = "Cancelled. No aliases were saved and nothing was built."

# Key bars: (key, word) pairs. Optional pairs are added only where they fit.
KEYS_LIST = [
    ("↑↓", "Move"),
    ("Space", "Tick"),
    ("R", "Rename"),
    ("Enter", "Confirm"),
    ("Tab", "Buttons"),
    ("Esc", "Exit"),
]
KEYS_LIST_PAGE = ("PgUp PgDn", "Page")  # after Move, only when the list scrolls
KEYS_BUTTONS = [
    ("←→", "Switch button"),
    ("Enter", "Press button"),
    ("Shift+Tab", "Back to list"),
    ("Esc", "Exit"),
]
KEYS_RENAME_MODE = "Renaming"
KEYS_RENAME = [
    ("Enter", "Save new name"),
    ("Esc", "Keep old name"),
    ("←→", "Move in name"),
]
KEYS_RENAME_ENDS = ("Home End", "Start or end of name")
KEYS_DIALOG = [
    ("Enter", "Choose"),
    ("←→", "Switch button"),
    ("Esc", "Keep editing"),
]
KEY_SEP = "   "


def title_bar(
    container: str, version: str, width: int, *, mouse: bool, command: str = "shelley"
) -> str:
    """Title bar: task on the left, the command (or "Keyboard only") on the right."""
    left = " " + TITLE_LEFT.format(container=container, version=version)
    right = (
        TITLE_RIGHT.format(command=command) if mouse else TITLE_RIGHT_NOMOUSE
    ) + " "
    pad = width - cell_len(left) - cell_len(right)
    if pad < 1:
        return truncate(left, width - cell_len(right) - 1) + " " + right
    return left + " " * pad + right


def help_lines(*, mouse: bool) -> tuple[str, str]:
    if mouse:
        return HELP_LINE1, HELP_LINE2
    return HELP_LINE1_NOMOUSE, HELP_LINE2_NOMOUSE


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - cell_len(text))


def heading_cells(cols: ColumnLayout) -> tuple[str, str, str, str]:
    """(margin, Include, Alias name, Command) heading cells, each padded to its column and gap."""
    return (
        " " * cols.margin,
        _pad(COL_INCLUDE, cols.include + cols.gap),
        _pad(COL_ALIAS, cols.alias + cols.gap),
        _pad(COL_COMMAND, cols.command),
    )


def row_cells(
    alias: str, command: str, cols: ColumnLayout, *, ticked: bool, highlighted: bool
) -> tuple[str, str, str, str]:
    """(marker, tick, name, command) cells for one list row, shortened and padded."""
    marker = f" {POINTER} " if highlighted else " " * cols.margin
    tick = _pad(TICK[ticked].center(cols.include), cols.include + cols.gap)
    name = _pad(shorten_alias(alias, cols.alias), cols.alias + cols.gap)
    path = _pad(shorten_path(command, cols.command), cols.command)
    return marker, tick, name, path


def count_text(ticked: int, total: int) -> str:
    return COUNT.format(n=ticked, total=total)


def scroll_text(above: int, below: int, total: int) -> str:
    if above and below:
        return SCROLL_ABOVE.format(n=above) + SEP + SCROLL_BELOW.format(n=below)
    if below:
        return SCROLL_BELOW.format(n=below)
    if above:
        return SCROLL_ABOVE.format(n=above)
    return SCROLL_ALL.format(total=total)


def rename_saved_message(old: str, new: str, *, was_ticked: bool) -> str:
    template = MSG_RENAME_SAVED_TICKED if was_ticked else MSG_RENAME_SAVED
    return template.format(old=old, new=new)


def rename_cancelled_message(old: str) -> str:
    return MSG_RENAME_CANCELLED.format(old=old)


def footer_line(
    ticked: int, total: int, above: int, below: int, width: int, message: str = ""
) -> str:
    """List footer: count and any message on the left, scroll position on the right.

    A message too long to sit beside the scroll text replaces it for its few seconds; the
    scrollbar thumb still shows the position.
    """
    left = "   " + count_text(ticked, total)
    right = scroll_text(above, below, total) + "  "
    if message:
        room = width - cell_len(left) - cell_len(right) - 4  # 3 before, 1 after
        if cell_len(message) > room:
            right = ""
            room = width - cell_len(left) - 3
        if room > 0:
            left += "   " + truncate(message, room)
    if not right:
        return left + " " * max(0, width - cell_len(left))
    pad = max(1, width - cell_len(left) - cell_len(right))
    return left + " " * pad + right


def _join(pairs: list[tuple[str, str]], lead: str = " ") -> Text:
    text = Text(lead)
    for i, (key, word) in enumerate(pairs):
        if i:
            text.append(KEY_SEP)
        text.append(key, style="bold")
        text.append(" " + word)
    return text


def key_bar(mode: str, width: int, *, scrolls: bool = False) -> Text:
    """Key bar for a mode ("list", "buttons", "rename", "dialog"), keys in bold.

    The optional pairs (PgUp PgDn on a scrolling list, Home End while renaming) are added only
    when the line still fits the width, which in practice means 120 columns.
    """
    if mode == "list":
        full = list(KEYS_LIST)
        if scrolls:
            full.insert(1, KEYS_LIST_PAGE)
        bar = _join(full)
        return bar if cell_len(bar.plain) <= width else _join(KEYS_LIST)
    if mode == "buttons":
        return _join(KEYS_BUTTONS)
    if mode == "rename":
        lead = f" {KEYS_RENAME_MODE} "
        bar = _join([*KEYS_RENAME, KEYS_RENAME_ENDS], lead=lead)
        return bar if cell_len(bar.plain) <= width else _join(KEYS_RENAME, lead=lead)
    if mode == "dialog":
        return _join(KEYS_DIALOG)
    raise ValueError(f"unknown key bar mode: {mode!r}")
