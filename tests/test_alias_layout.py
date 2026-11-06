"""Pure functions behind the alias picker, checked against docs/reference/alias-picker-screens.md."""

import pytest
from rich.cells import cell_len

from shelley.ui import alias_copy as copy
from shelley.ui.alias_layout import (
    ColumnLayout,
    RowLayout,
    column_layout,
    row_layout,
    scroll_counts,
    shorten_alias,
    shorten_path,
    truncate,
)

# --------------------------------------------------------------------------------------------------------------
# Rows
# --------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("height", "items", "expected"),
    [
        (24, 27, RowLayout(list_rows=11, gaps=3)),  # 80×24 frames
        (40, 27, RowLayout(list_rows=27, gaps=3)),  # 120×40, everything fits
        (40, 38, RowLayout(list_rows=27, gaps=3)),  # 120×40, bedtools scrolls
        (23, 27, RowLayout(list_rows=10, gaps=3)),  # tmux: 80×24 gives the app 23 rows
        (18, 27, RowLayout(list_rows=5, gaps=3)),  # smallest with all gaps
        (17, 27, RowLayout(list_rows=5, gaps=2)),  # then gaps go
        (15, 27, RowLayout(list_rows=5, gaps=0)),
        (10, 27, RowLayout(list_rows=5, gaps=0)),  # never below 5 rows
        (24, 3, RowLayout(list_rows=3, gaps=3)),  # short list, short widget
    ],
)
def test_row_layout(height, items, expected):
    assert row_layout(height, items) == expected


def test_widget_fits_terminal_minus_one():
    for height in range(18, 60):
        layout = row_layout(height, 100)
        assert 9 + layout.gaps + layout.list_rows == height - 1


# --------------------------------------------------------------------------------------------------------------
# Columns
# --------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("width", "alias", "command"),
    [
        (80, 22, 42),
        (120, 28, 76),
        (100, 22, 62),  # Command takes extra width first
        (114, 22, 76),
        (117, 25, 76),  # then Alias name, up to 28
        (140, 28, 96),  # then Command again
        (70, 22, 32),  # narrower: Command shrinks first
        (58, 22, 20),
        (50, 14, 20),  # then Alias name down to 14
        (40, 14, 10),  # then Command again
    ],
)
def test_column_layout(width, alias, command):
    cols = column_layout(width)
    assert (cols.alias, cols.command) == (alias, command)
    used = cols.margin + cols.include + cols.gap + cols.alias + cols.gap + cols.command
    assert used + cols.scrollbar == width


# --------------------------------------------------------------------------------------------------------------
# Shortening
# --------------------------------------------------------------------------------------------------------------


def test_shorten_path_spec_example():
    path = "/usr/local/opt/trinity-2.15.1/util/align_and_estimate_abundance.pl"
    assert shorten_path(path, 42) == "/usr/…/align_and_estimate_abundance.pl"


@pytest.mark.parametrize(
    ("width", "expected"),
    [
        (100, "/usr/local/opt/trinity-2.15.1/util/align_and_estimate_abundance.pl"),
        (63, "/usr/local/opt/trinity-2.15.1/…/align_and_estimate_abundance.pl"),
        (62, "/usr/local/opt/…/align_and_estimate_abundance.pl"),
        (50, "/usr/local/opt/…/align_and_estimate_abundance.pl"),
        (34, "…/align_and_estimate_abundance.pl"),
        (31, "align_and_estimate_abundance.pl"),
        (20, "align_and_estimate_…"),
    ],
)
def test_shorten_path_keeps_file_name_then_folders(width, expected):
    path = "/usr/local/opt/trinity-2.15.1/util/align_and_estimate_abundance.pl"
    out = shorten_path(path, width)
    assert out == expected
    assert cell_len(out) <= width


def test_shorten_path_relative_and_bare():
    assert shorten_path("bin/tool", 20) == "bin/tool"
    assert shorten_path("a/b/c/long_tool_name", 18) == "a/…/long_tool_name"
    assert shorten_path("averyveryverylongname", 10) == "averyvery…"


def test_shorten_alias():
    assert shorten_alias("bowtie2sam.pl", 22) == "bowtie2sam.pl"
    assert shorten_alias("seq_cache_populate_extra.pl", 22) == "seq_cache_populate_ex…"
    assert cell_len(shorten_alias("seq_cache_populate_extra.pl", 22)) == 22


def test_truncate_edges():
    assert truncate("abc", 3) == "abc"
    assert truncate("abcd", 3) == "ab…"
    assert truncate("abcd", 1) == "…"
    assert truncate("abcd", 0) == ""


# --------------------------------------------------------------------------------------------------------------
# Lines drawn in alias-picker-screens.md (the command placeholder there is "shelley-bio")
# --------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("container", "version", "width", "mouse", "line"),
    [
        ("samtools", "1.21", 80, True,
         " Choose aliases — samtools 1.21                               shelley-bio build "),
        ("bedtools", "2.31.1", 80, True,
         " Choose aliases — bedtools 2.31.1                             shelley-bio build "),
        ("samtools", "1.21", 80, False,
         " Choose aliases — samtools 1.21                                   Keyboard only "),
        ("samtools", "1.21", 120, True,
         " Choose aliases — samtools 1.21" + " " * 71 + "shelley-bio build "),
        ("samtools", "1.21", 120, False,
         " Choose aliases — samtools 1.21" + " " * 75 + "Keyboard only "),
    ],
)  # fmt: skip
def test_title_bar(container, version, width, mouse, line):
    built = copy.title_bar(
        container, version, width, mouse=mouse, command="shelley-bio"
    )
    assert built == line
    assert cell_len(built) == width


def test_help_lines():
    assert copy.help_lines(mouse=True) == (
        "Click [ ] to tick the aliases you'll use. You can rebuild later to add more.",
        "Click a name to rename it. The Command column needs no action.",
    )
    line1, line2 = copy.help_lines(mouse=False)
    assert cell_len(" " + line1) == 79  # the widest line at 80 columns
    assert (
        line2
        == "Press R to rename the highlighted alias. The Command column needs no action."
    )


@pytest.mark.parametrize(
    ("args", "message", "line"),
    [
        ((0, 27, 0, 16, 80), "",
         "   0 of 27 ticked                                              ▼ 16 more below  "),
        ((2, 27, 0, 16, 80), "Rename cancelled. Kept bowtie2sam.pl.",
         "   2 of 27 ticked   Rename cancelled. Kept bowtie2sam.pl.      ▼ 16 more below  "),
        ((2, 38, 11, 16, 80), "",
         "   2 of 38 ticked                            ▲ 11 more above · ▼ 16 more below  "),
        ((0, 27, 0, 0, 120), "",
         "   0 of 27 ticked" + " " * 89 + "All 27 shown  "),
        ((4, 27, 0, 0, 120), "Rename cancelled. Kept bowtie2sam.pl.",
         "   4 of 27 ticked   Rename cancelled. Kept bowtie2sam.pl." + " " * 49 + "All 27 shown  "),
        ((3, 38, 6, 5, 120), "",
         "   3 of 38 ticked" + " " * 70 + "▲ 6 more above · ▼ 5 more below  "),
    ],
)  # fmt: skip
def test_footer_line(args, message, line):
    built = copy.footer_line(*args, message=message)
    assert built == line
    assert cell_len(built) == args[-1]


def test_footer_long_message_replaces_scroll_text():
    message = "Renamed bowtie2sam.pl to bowtie2sam and ticked it."
    built = copy.footer_line(1, 27, 0, 16, 80, message=message)
    assert built == "   1 of 27 ticked   " + message + " " * (80 - 20 - len(message))
    assert cell_len(built) == 80


def test_footer_message_is_shortened_when_even_alone_it_does_not_fit():
    built = copy.footer_line(
        2, 38, 11, 16, 60, message="Renamed a_very_long_alias_name.pl to x_y_z."
    )
    assert cell_len(built) == 60
    assert built.rstrip().endswith("…")


def test_scroll_text_variants():
    assert copy.scroll_text(0, 16, 27) == "▼ 16 more below"
    assert copy.scroll_text(22, 0, 38) == "▲ 22 more above"
    assert copy.scroll_text(22, 16, 49) == "▲ 22 more above · ▼ 16 more below"
    assert copy.scroll_text(0, 0, 27) == "All 27 shown"


def test_scroll_counts():
    assert scroll_counts(0, 11, 27) == (0, 16)
    assert scroll_counts(11, 11, 38) == (11, 16)
    assert scroll_counts(0, 27, 27) == (0, 0)


def test_messages():
    assert (
        copy.rename_saved_message("bowtie2sam.pl", "bowtie2sam", was_ticked=False)
        == "Renamed bowtie2sam.pl to bowtie2sam and ticked it."
    )
    assert (
        copy.rename_saved_message("bowtie2sam.pl", "bowtie2sam", was_ticked=True)
        == "Renamed bowtie2sam.pl to bowtie2sam."
    )
    assert (
        copy.rename_cancelled_message("bowtie2sam.pl")
        == "Rename cancelled. Kept bowtie2sam.pl."
    )
    assert copy.MSG_CONFIRM_EMPTY == "Tick at least one alias first."
    assert copy.CANCEL_LINE == "Cancelled. No aliases were saved and nothing was built."


@pytest.mark.parametrize(
    ("mode", "width", "scrolls", "line"),
    [
        ("list", 80, True,
         " ↑↓ Move   Space Tick   R Rename   Enter Confirm   Tab Buttons   Esc Exit"),
        ("list", 120, False,
         " ↑↓ Move   Space Tick   R Rename   Enter Confirm   Tab Buttons   Esc Exit"),
        ("list", 120, True,
         " ↑↓ Move   PgUp PgDn Page   Space Tick   R Rename   Enter Confirm   Tab Buttons   Esc Exit"),
        ("buttons", 80, False,
         " ←→ Switch button   Enter Press button   Shift+Tab Back to list   Esc Exit"),
        ("rename", 80, False,
         " Renaming Enter Save new name   Esc Keep old name   ←→ Move in name"),
        ("rename", 120, False,
         " Renaming Enter Save new name   Esc Keep old name   ←→ Move in name   Home End Start or end of name"),
        ("dialog", 80, False,
         " Enter Choose   ←→ Switch button   Esc Keep editing"),
    ],
)  # fmt: skip
def test_key_bar(mode, width, scrolls, line):
    bar = copy.key_bar(mode, width, scrolls=scrolls)
    assert bar.plain == line
    bold = {bar.plain[s.start : s.end] for s in bar.spans if s.style == "bold"}
    assert "Esc" in bold or "Enter" in bold
    assert "Move" not in bold and "Renaming" not in bold


def test_key_bar_unknown_mode():
    with pytest.raises(ValueError):
        copy.key_bar("nope", 80)


# --------------------------------------------------------------------------------------------------------------
# Heading and row cells, against the 80×24 and 120×40 frames
# --------------------------------------------------------------------------------------------------------------


def test_heading_cells():
    assert "".join(copy.heading_cells(column_layout(80))).rstrip() == (
        "   Include  Alias name              Command"
    )
    assert "".join(copy.heading_cells(column_layout(120))).rstrip() == (
        "   Include  Alias name                    Command"
    )


@pytest.mark.parametrize(
    ("width", "highlighted", "ticked", "alias", "line"),
    [
        (80, True, False, "ace2sam",
         " ›   [ ]    ace2sam                 /usr/local/bin/ace2sam                    █"),
        (80, False, True, "bgzip",
         "     [x]    bgzip                   /usr/local/bin/bgzip                      █"),
        (80, True, True, "htsfile",
         " ›   [x]    htsfile                 /usr/local/bin/htsfile                    │"),
        (120, False, False, "seq_cache_populate.pl",
         "     [ ]    seq_cache_populate.pl         /usr/local/bin/seq_cache_populate.pl"),
    ],
)  # fmt: skip
def test_row_cells_match_frames(width, highlighted, ticked, alias, line):
    cols = column_layout(width)
    cells = copy.row_cells(
        alias, f"/usr/local/bin/{alias}", cols, ticked=ticked, highlighted=highlighted
    )
    assert "".join(cells).rstrip() == line[: cols.margin + cols.include + cols.gap * 2
                                           + cols.alias + cols.command].rstrip()  # fmt: skip
    assert cell_len("".join(cells)) == width - cols.scrollbar


def test_row_cells_shorten_long_values():
    cols = ColumnLayout(alias=22, command=42)
    _, _, name, path = copy.row_cells(
        "a_really_long_alias_name_here",
        "/usr/local/opt/trinity-2.15.1/util/align_and_estimate_abundance.pl",
        cols,
        ticked=False,
        highlighted=False,
    )
    assert name.rstrip() == "a_really_long_alias_n…"
    assert path.rstrip() == "/usr/…/align_and_estimate_abundance.pl"
