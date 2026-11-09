"""Tests for the interactive alias editor used by `build -i/--interactive`."""

import pytest
from rich.console import Console
from rich.text import Text
from textual.coordinate import Coordinate
from textual.widgets import Button, DataTable, Input

from shelley.builder.alias_editor import (
    AliasEditorApp,
    DiscardDialog,
    alias_summary,
    normalize_aliases,
)
from shelley.utils.style import SHELLEY_THEME, TICK_OFF, TICK_ON


def rich_text_center() -> Text:
    return Text(TICK_OFF, justify="center")


@pytest.fixture
def input_aliases() -> list[dict]:
    return [
        {"STAR": "/usr/local/bin/STAR"},
        {
            "plassembler.py": "/usr/local/bin/plassembler.py",
            "log.py": "/usr/local/bin/log.py",
            "capnpc-c++": "/usr/local/bin/capnpc-c++",
        },
    ]


# ---------------------------------------------------------------------------
# normalize_aliases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "index, expected",
    [
        (0, [{"name": "STAR", "command": "/usr/local/bin/STAR"}]),
        (
            1,
            [
                {"name": "plassembler.py", "command": "/usr/local/bin/plassembler.py"},
                {"name": "log.py", "command": "/usr/local/bin/log.py"},
                {"name": "capnpc-c++", "command": "/usr/local/bin/capnpc-c++"},
            ],
        ),
    ],
    ids=["single-entry", "multi-entry"],
)
def test_normalize_aliases_dict_form(input_aliases, index, expected):
    result = normalize_aliases(input_aliases[index])
    assert result == expected


@pytest.mark.parametrize("empty", [None, [], {}])
def test_normalize_aliases_empty(empty):
    result = normalize_aliases(empty)
    assert result == []


# ---------------------------------------------------------------------------
# alias_editor textual App
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "index, expected_aliases, expected_rows",
    [
        (
            0,
            [{"name": "STAR", "command": "/usr/local/bin/STAR"}],
            [(rich_text_center(), "STAR", "/usr/local/bin/STAR")],
        ),
        (
            1,
            [
                {"name": "plassembler.py", "command": "/usr/local/bin/plassembler.py"},
                {"name": "log.py", "command": "/usr/local/bin/log.py"},
                {"name": "capnpc-c++", "command": "/usr/local/bin/capnpc-c++"},
            ],
            [
                (rich_text_center(), "plassembler.py", "/usr/local/bin/plassembler.py"),
                (rich_text_center(), "log.py", "/usr/local/bin/log.py"),
                (rich_text_center(), "capnpc-c++", "/usr/local/bin/capnpc-c++"),
            ],
        ),
    ],
    ids=["single-entry", "multi-entry"],
)
def test_init_app(input_aliases, index, expected_aliases, expected_rows):
    app = AliasEditorApp(input_aliases[index])

    assert app.aliases == expected_aliases
    assert app.rows == expected_rows


@pytest.mark.asyncio
@pytest.mark.parametrize("index, nrows", [(0, 1), (1, 3)])
async def test_nrows_on_mount(input_aliases, index, nrows):
    app = AliasEditorApp(input_aliases[index])

    async with app.run_test():
        # simulate the app starting with asyncio
        table = app.query_one(DataTable)
        buttons = app.query(Button)

        assert table.row_count == nrows
        assert len(buttons) == 2


@pytest.mark.asyncio
async def test_theme_is_biocommons(input_aliases):
    app = AliasEditorApp(input_aliases[0])

    async with app.run_test():
        assert app.theme == "biocommons"


async def tick(pilot, row: int) -> None:
    """Toggle the tick on ``row`` with DataTable's own Enter."""
    table = pilot.app.query_one(DataTable)
    table.focus()
    table.cursor_coordinate = Coordinate(row, 0)
    await pilot.press("enter")


@pytest.mark.asyncio
async def test_confirm_disabled_until_ticked(input_aliases):
    app = AliasEditorApp(input_aliases[1])

    async with app.run_test() as pilot:
        confirm = app.query_one("#confirm", Button)
        assert confirm.disabled

        await tick(pilot, 0)
        assert not confirm.disabled

        await tick(pilot, 0)  # untick
        assert confirm.disabled


@pytest.mark.asyncio
async def test_confirm_returns_ticked_rows(input_aliases):
    app = AliasEditorApp(input_aliases[1])

    async with app.run_test() as pilot:
        await tick(pilot, 0)
        await tick(pilot, 2)
        await pilot.click("#confirm")

    assert app.return_value == [
        {"name": "plassembler.py", "command": "/usr/local/bin/plassembler.py"},
        {"name": "capnpc-c++", "command": "/usr/local/bin/capnpc-c++"},
    ]


async def rename(pilot, row: int, new: str) -> None:
    """Open the edit bar on ``row`` with Enter on its name cell, type ``new`` and save."""
    table = pilot.app.query_one(DataTable)
    table.focus()
    table.cursor_coordinate = Coordinate(row, 1)
    await pilot.press("enter")
    pilot.app.query_one(Input).value = new
    await pilot.press("enter")


def cells(app, row: int) -> tuple[str, str]:
    """The (tick, name) shown on ``row``."""
    table = app.query_one(DataTable)
    tick, name, _ = table.get_row_at(row)
    return str(tick), str(name)


@pytest.mark.asyncio
async def test_rename_opens_bar_with_old_name(input_aliases):
    app = AliasEditorApp(input_aliases[1])

    async with app.run_test() as pilot:
        assert not app.query_one("#rename_bar").display
        table = app.query_one(DataTable)
        table.focus()
        table.cursor_coordinate = Coordinate(1, 1)
        await pilot.press("enter")

        assert app.query_one("#rename_bar").display
        assert app.query_one(Input).value == "log.py"
        assert "Rename log.py to:" in str(app.query_one("#rename_label").render())


@pytest.mark.asyncio
async def test_rename_saves_and_ticks(input_aliases):
    app = AliasEditorApp(input_aliases[1])

    async with app.run_test() as pilot:
        await rename(pilot, 1, "plassembler-log")

        assert cells(app, 1) == (TICK_ON, "plassembler-log")
        assert not app.query_one("#rename_bar").display
        assert not app.query_one("#confirm", Button).disabled
        assert "log.py" in app.original.values()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "new", ["log.py", "  ", ""], ids=["unchanged", "spaces", "blank"]
)
async def test_rename_unchanged_or_blank_does_nothing(input_aliases, new):
    app = AliasEditorApp(input_aliases[1])

    async with app.run_test() as pilot:
        await rename(pilot, 1, new)

        assert cells(app, 1) == (TICK_OFF, "log.py")
        assert not app.query_one("#rename_bar").display
        assert app.query_one("#confirm", Button).disabled


@pytest.mark.asyncio
@pytest.mark.parametrize("new", ["log py", "bin/log"], ids=["space", "slash"])
async def test_rename_refuses_space_and_slash(input_aliases, new):
    app = AliasEditorApp(input_aliases[1])

    async with app.run_test() as pilot:
        await rename(pilot, 1, new)

        assert cells(app, 1) == (TICK_OFF, "log.py")
        assert app.query_one("#rename_bar").display  # still open to fix the name
        assert "spaces or /" in str(app.query_one("#rename_error").render())


@pytest.mark.asyncio
async def test_esc_cancels_rename_only(input_aliases):
    app = AliasEditorApp(input_aliases[1])

    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        table.focus()
        table.cursor_coordinate = Coordinate(1, 1)
        await pilot.press("enter")
        app.query_one(Input).value = "changed"
        await pilot.press("escape")

        assert app.is_running
        assert not app.query_one("#rename_bar").display
        assert cells(app, 1) == (TICK_OFF, "log.py")


@pytest.mark.asyncio
async def test_confirm_hint_hides_once_ticked(input_aliases):
    app = AliasEditorApp(input_aliases[1])

    async with app.run_test() as pilot:
        hint = app.query_one("#confirm_hint")
        assert hint.display
        await tick(pilot, 0)
        assert not hint.display
        await tick(pilot, 0)
        assert hint.display


@pytest.mark.asyncio
@pytest.mark.parametrize("opener", ["escape", "#cancel"], ids=["esc", "cancel-button"])
async def test_exit_opens_discard_dialog(input_aliases, opener):
    app = AliasEditorApp(input_aliases[1])

    async with app.run_test() as pilot:
        if opener == "escape":
            await pilot.press("escape")
        else:
            await pilot.click(opener)

        assert isinstance(app.screen, DiscardDialog)
        assert app.focused.id == "keep"


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", ["escape", "#keep"], ids=["esc", "keep-button"])
async def test_dialog_keep_editing_returns_to_list(input_aliases, answer):
    app = AliasEditorApp(input_aliases[1])

    async with app.run_test() as pilot:
        await tick(pilot, 0)
        await pilot.press("escape")
        if answer == "escape":
            await pilot.press("escape")
        else:
            await pilot.click(answer)

        assert app.is_running
        assert not isinstance(app.screen, DiscardDialog)
        assert cells(app, 0)[0] == TICK_ON  # ticks kept


@pytest.mark.asyncio
async def test_dialog_discard_exits_with_none(input_aliases):
    app = AliasEditorApp(input_aliases[1])

    async with app.run_test() as pilot:
        await tick(pilot, 0)
        await pilot.press("escape")
        await pilot.click("#discard")
        await pilot.pause()
        assert not app.is_running

    assert app.return_value is None


@pytest.mark.asyncio
@pytest.mark.parametrize("renaming", [False, True], ids=["list", "renaming"])
async def test_ctrl_c_exits_without_dialog(input_aliases, renaming):
    app = AliasEditorApp(input_aliases[1])

    async with app.run_test() as pilot:
        await tick(pilot, 0)
        if renaming:
            table = app.query_one(DataTable)
            table.cursor_coordinate = Coordinate(1, 1)
            await pilot.press("enter")
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert not app.is_running

    assert app.return_value is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs, sub_title",
    [
        (
            {"tool": "samtools", "version": "1.21--h50ea8bc_3"},
            "samtools 1.21--h50ea8bc_3",
        ),
        ({}, ""),
    ],
    ids=["tool-version", "no-tool"],
)
async def test_subtitle_names_tool_and_version(input_aliases, kwargs, sub_title):
    app = AliasEditorApp(input_aliases[0], **kwargs)

    async with app.run_test():
        assert app.title == "Shelley alias editor"
        assert app.sub_title == sub_title


# ---------------------------------------------------------------------------
# summary printed after Confirm
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_records_renames(input_aliases):
    app = AliasEditorApp(input_aliases[1])

    async with app.run_test() as pilot:
        await rename(pilot, 1, "plassembler-log")
        await tick(pilot, 0)
        await pilot.click("#confirm")

    assert app.renamed == {"plassembler-log": "log.py"}
    assert {"name": "plassembler-log", "command": "/usr/local/bin/log.py"} in (
        app.return_value
    )


def render(renderable, width: int = 80) -> str:
    console = Console(theme=SHELLEY_THEME, width=width, record=True)
    console.print(renderable)
    return console.export_text()


def test_alias_summary():
    chosen = [
        {"name": "bgzip", "command": "/usr/local/bin/bgzip"},
        {"name": "sam2vcf", "command": "/usr/local/bin/sam2vcf.pl"},
    ]
    out = render(
        alias_summary(
            "samtools", "1.21--h50ea8bc_3", chosen, 27, {"sam2vcf": "sam2vcf.pl"}
        )
    )

    assert "√ Done: Aliases chosen for samtools 1.21--h50ea8bc_3: 2 of 27" in out
    assert "╭" in out  # rounded box
    assert "/usr/local/bin/sam2vcf.pl  (renamed from sam2vcf.pl)" in out
    assert "(renamed from" not in out.split("bgzip")[1].split("\n")[0]
    assert "To add or change aliases, run the build again:" in out
    assert "shelley build samtools/1.21--h50ea8bc_3 -i" in out


def test_alias_summary_wraps_long_paths_instead_of_cutting():
    path = "/usr/local/" + "deep/" * 20 + "tool.py"
    out = render(alias_summary("t", "1", [{"name": "tool", "command": path}], 1))

    joined = "".join(
        line.split("│")[2].strip() for line in out.splitlines() if "│" in line
    )
    assert path in joined
    assert "…" not in out
