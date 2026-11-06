"""Layout maths and text shortening for the alias picker (docs/reference/alias-picker.md, "Layout").

Pure functions, no Textual import, so they can be unit-tested directly.
"""

from dataclasses import dataclass

from rich.cells import cell_len

from ..utils.style import ELLIPSIS

# Rows, top to bottom (the launching command above the widget is not counted).
FIXED_ROWS = 9  # title bar, 2 instruction lines, column headings, list footer, 3 button rows, key bar
GAP_ROWS = 3  # after the instructions, after the list footer, after the buttons
MIN_LIST_ROWS = 5

# Columns, left to right, in character cells.
MARGIN = 3  # margin + highlight marker
INCLUDE = 7  # "[ ]" centred
GAP = 2
SCROLLBAR = 2  # scrollbar + right margin
FIXED_COLUMNS = MARGIN + INCLUDE + GAP + GAP + SCROLLBAR
ALIAS_MIN, ALIAS_BASE, ALIAS_MAX = 14, 22, 28
COMMAND_BASE, COMMAND_WIDE = 42, 76  # at 80 and at 120 columns
COMMAND_MIN = 20  # not in the spec: the floor before Alias name starts shrinking


@dataclass(frozen=True)
class RowLayout:
    list_rows: int  # rows the list gets (it is the only part that scrolls)
    gaps: int  # blank gap rows kept, 0 to 3; drop the one after the buttons first


@dataclass(frozen=True)
class ColumnLayout:
    alias: int
    command: int
    margin: int = MARGIN
    include: int = INCLUDE
    gap: int = GAP
    scrollbar: int = SCROLLBAR


def row_layout(terminal_height: int, items: int) -> RowLayout:
    """Rows for the list: terminal height − 13, at least 5, never more than there are items.

    The widget is at most terminal height − 1 (the launching command stays visible), so an 80×24
    terminal gives an 11-row list and tmux's 80×23 a 10-row list. When the list would fall below 5
    rows, the gaps go first, then the widget simply needs more rows than the terminal has.
    """
    list_rows = terminal_height - 1 - FIXED_ROWS - GAP_ROWS
    gaps = GAP_ROWS
    while list_rows < MIN_LIST_ROWS and gaps:
        gaps -= 1
        list_rows += 1
    list_rows = max(MIN_LIST_ROWS, list_rows)
    return RowLayout(list_rows=min(items, list_rows), gaps=gaps)


def column_layout(terminal_width: int) -> ColumnLayout:
    """Alias name and Command widths: 22 / 42 at 80 columns, 28 / 76 at 120.

    Wider than 80, extra width goes to Command first (up to its 120-column width), then to Alias
    name up to 28, then to Command again. Narrower than 80, Command shrinks first (to COMMAND_MIN),
    then Alias name down to 14, then Command again.
    """
    space = terminal_width - FIXED_COLUMNS
    base = ALIAS_BASE + COMMAND_BASE
    if space >= base:
        extra = space - base
        to_command = min(extra, COMMAND_WIDE - COMMAND_BASE)
        alias = ALIAS_BASE + min(extra - to_command, ALIAS_MAX - ALIAS_BASE)
        return ColumnLayout(alias=alias, command=space - alias)
    if space - ALIAS_BASE >= COMMAND_MIN:
        return ColumnLayout(alias=ALIAS_BASE, command=space - ALIAS_BASE)
    alias = max(ALIAS_MIN, space - COMMAND_MIN)
    return ColumnLayout(alias=alias, command=max(1, space - alias))


def truncate(text: str, width: int) -> str:
    """Cut the end of `text` with … so it fits `width` cells."""
    if cell_len(text) <= width:
        return text
    if width <= 0:
        return ""
    out = ""
    for ch in text:
        if cell_len(out + ch) > width - 1:
            break
        out += ch
    return out + ELLIPSIS


def shorten_alias(name: str, width: int) -> str:
    """Alias names: cut the end with …. The full name shows when you rename it."""
    return truncate(name, width)


def shorten_path(path: str, width: int) -> str:
    """Command paths: keep the file name whole and as many leading folders as fit, then …/.

    At 42 cells "/usr/local/opt/trinity-2.15.1/util/align_and_estimate_abundance.pl" becomes
    "/usr/…/align_and_estimate_abundance.pl". If the file name alone is too long, cut its end with ….
    """
    if cell_len(path) <= width:
        return path
    head, _, name = path.rpartition("/")
    lead = "/" if head.startswith("/") else ""
    folders = [f for f in head.split("/") if f]
    for keep in range(len(folders) - 1, 0, -1):
        candidate = f"{lead}{'/'.join(folders[:keep])}/{ELLIPSIS}/{name}"
        if cell_len(candidate) <= width:
            return candidate
    for candidate in (f"{ELLIPSIS}/{name}", name):
        if cell_len(candidate) <= width:
            return candidate
    return truncate(name, width)


def scroll_counts(first_visible: int, visible_rows: int, total: int) -> tuple[int, int]:
    """(rows above, rows below) the visible part of the list."""
    above = max(0, first_visible)
    below = max(0, total - first_visible - visible_rows)
    return above, below
