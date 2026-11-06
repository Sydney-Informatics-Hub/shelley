"""Pilot tests for the alias picker: one per row of the interaction tables in
docs/reference/alias-picker.md ("Interactions"), plus the "Other events" rows."""

import pytest
from textual import events
from textual.widgets import Static

from shelley.ui.alias_picker import (
    AliasList,
    AliasPickerApp,
    AliasRow,
    NameField,
    PickedAlias,
    PickerButton,
)

pytestmark = pytest.mark.asyncio

SAMTOOLS = (
    "ace2sam bgzip blast2sam.pl bowtie2sam.pl export2sam.pl fasta-sanitize.pl htsfile "
    "interpolate_sam.pl libdeflate-gunzip libdeflate-gzip maq2sam-long maq2sam-short md5fa "
    "md5sum-lite novo2sam.pl plot-ampliconstats plot-bamstats psl2sam.pl sam2vcf.pl samtools "
    "samtools.pl seq_cache_populate.pl soap2sam.pl tabix wgsim wgsim_eval.pl zoom2sam.pl"
).split()


def aliases(names=SAMTOOLS):
    return [{"name": n, "command": f"/usr/local/bin/{n}"} for n in names]


def make_app(names=SAMTOOLS, **kwargs) -> AliasPickerApp:
    return AliasPickerApp(aliases(names), "samtools", "1.21", **kwargs)


def footer(app) -> str:
    return str(app.query_one("#footer", Static).render())


def keys(app) -> str:
    return str(app.query_one("#keys", Static).render())


def field(app) -> NameField:
    return app.query_one(NameField)


def row(app, index) -> AliasRow:
    return app.rows[index]


async def wheel(pilot, notches=3):
    """Scroll the list down with the mouse wheel."""
    alias_list = pilot.app.list_widget
    for _ in range(notches):
        alias_list.post_message(
            events.MouseScrollDown(alias_list, 5, 2, 0, 1, 0, False, False, False)
        )
        await pilot.pause()
    await pilot.pause(0.1)


async def tick(pilot, *indices):
    """Tick rows by moving to them and pressing Space."""
    app = pilot.app
    for index in indices:
        await pilot.press(*(["down"] * (index - app.highlight)), "space")


# --------------------------------------------------------------------------------------------------------------
# Initial state
# --------------------------------------------------------------------------------------------------------------


async def test_initial_state():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert app.highlight == 0
        assert app.ticked == 0
        assert isinstance(app.focused, AliasList)
        assert app.query_one("#confirm").has_class("-unavailable")
        assert app.query_one("#reason").visible
        assert "0 of 27 ticked" in footer(app) and "▼ 16 more below" in footer(app)
        assert keys(app).startswith(" ↑↓ Move   Space Tick")


# --------------------------------------------------------------------------------------------------------------
# On the list (normal mode)
# --------------------------------------------------------------------------------------------------------------


async def test_move_highlight_with_keys_scrolls_to_keep_it_in_view():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("down", "down", "up")
        assert app.highlight == 1
        await pilot.press(*["down"] * 14)
        await pilot.pause()
        assert app.highlight == 15
        assert app.list_widget.scroll_y > 0
        assert row(app, 15).has_class("-highlight") and not row(app, 1).has_class(
            "-highlight"
        )


async def test_move_highlight_by_clicking_command_cell():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.click(row(app, 5).query_one(".cmd", Static))
        await pilot.pause()
        assert app.highlight == 5
        assert app.ticked == 0 and app.renaming is None


async def test_page_and_ends_keys():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("pagedown")
        assert app.highlight == 11
        await pilot.press("end")
        await pilot.pause()
        assert app.highlight == 26
        assert "▲ 16 more above" in footer(app)
        await pilot.press("pageup")
        assert app.highlight == 15
        await pilot.press("home")
        assert app.highlight == 0


async def test_wheel_scrolls_without_moving_highlight():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await wheel(pilot)
        assert app.highlight == 0
        assert app.list_widget.scroll_y > 0
        assert "more above · ▼" in footer(app)


async def test_tick_with_space_updates_count_and_confirm():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("space")
        await pilot.pause()
        assert row(app, 0).ticked
        assert "1 of 27 ticked" in footer(app)
        assert not app.query_one("#confirm").has_class("-unavailable")
        assert not app.query_one("#reason").visible
        assert "[x]" in str(row(app, 0).query_one(".tick", Static).render())
        await pilot.press("space")
        await pilot.pause()
        assert app.ticked == 0
        assert app.query_one("#confirm").has_class("-unavailable")


async def test_tick_by_clicking_box_moves_highlight():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.click(row(app, 3).query_one(".tick", Static))
        await pilot.pause()
        assert row(app, 3).ticked
        assert app.highlight == 3


@pytest.mark.parametrize("key", ["r", "f2"])
async def test_start_renaming_with_key(key):
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("down", key)
        await pilot.pause()
        assert app.renaming == 1
        assert app.focused is field(app)
        assert field(app).selected_text == "bgzip"  # all selected, typing replaces it
        assert keys(app).startswith(" Renaming Enter Save new name")


async def test_start_renaming_by_clicking_name():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.click(row(app, 2).query_one(".name", Static))
        await pilot.pause()
        assert app.renaming == 2 and app.highlight == 2
        assert field(app).region.y == row(app, 2).region.y
        assert field(app).region.x == row(app, 1).query_one(".name", Static).region.x


async def test_confirm_with_enter_on_list():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await tick(pilot, 1, 6)
        await pilot.press("enter")
        await pilot.pause()
    assert app.return_value == [
        PickedAlias("bgzip", "/usr/local/bin/bgzip", "bgzip"),
        PickedAlias("htsfile", "/usr/local/bin/htsfile", "htsfile"),
    ]


async def test_confirm_by_clicking_confirm():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await tick(pilot, 0)
        await pilot.click(app.query_one("#confirm"))
        await pilot.pause()
    assert [a.name for a in app.return_value] == ["ace2sam"]


@pytest.mark.parametrize("press", ["enter", "space"])
async def test_confirm_with_tab_then_enter_or_space(press):
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await tick(pilot, 0)
        await pilot.press("tab")
        assert app.focused.id == "confirm"
        await pilot.press(press)
        await pilot.pause()
    assert [a.name for a in app.return_value] == ["ace2sam"]


async def test_confirm_with_nothing_ticked_enter():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("enter")
        await pilot.pause()
        assert app.is_running
        assert "Tick at least one alias first." in footer(app)
        assert app.query_one("#reason").visible


async def test_confirm_with_nothing_ticked_click():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.click(app.query_one("#confirm"))
        await pilot.pause()
        assert app.is_running
        assert "Tick at least one alias first." in footer(app)


async def test_message_clears_on_next_action():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("enter", "down")
        await pilot.pause()
        assert "Tick at least one" not in footer(app)


async def test_esc_with_nothing_to_lose_exits_straight_away():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("escape")
        await pilot.pause()
    assert app.return_value is None  # exited, so no dialog stood in the way


async def test_esc_with_ticks_asks_first():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("space", "escape")
        await pilot.pause()
        assert app.is_running and app.dialog_open
        assert app.focused.id == "keep"
        assert str(app.focused.render()) == "› Keep editing ‹"
        assert keys(app) == " Enter Choose   ←→ Switch button   Esc Keep editing"


async def test_cancel_with_nothing_to_lose_exits():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.click(app.query_one("#cancel"))
        await pilot.pause()
    assert app.return_value is None


async def test_cancel_with_rename_asks_first():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("r", "x", "enter")
        await pilot.click(app.query_one("#cancel"))
        await pilot.pause()
        assert app.dialog_open


async def test_tab_order_list_confirm_cancel_list():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("space", "tab")
        assert app.focused.id == "confirm"
        assert str(app.focused.render()) == "› Confirm ‹"
        assert row(app, 0).has_class("-dim")  # list highlight dims but keeps ›
        assert "›" in str(row(app, 0).query_one(".marker", Static).render())
        assert keys(app).startswith(" ←→ Switch button")
        await pilot.press("tab")
        assert app.focused.id == "cancel"
        await pilot.press("tab")
        assert isinstance(app.focused, AliasList)
        assert not row(app, 0).has_class("-dim")
        await pilot.press("shift+tab")
        assert app.focused.id == "cancel"
        await pilot.press("left")
        assert app.focused.id == "confirm"
        await pilot.press("right")
        assert app.focused.id == "cancel"


async def test_tab_skips_greyed_confirm():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("tab")
        assert app.focused.id == "cancel"
        await pilot.press("left")
        assert app.focused.id == "cancel"


async def test_ctrl_c_exits_at_once_without_dialog():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("space", "ctrl+c")
        await pilot.pause()
    assert app.return_value is None  # exited, so no dialog stood in the way


# --------------------------------------------------------------------------------------------------------------
# While renaming
# --------------------------------------------------------------------------------------------------------------


async def test_rename_typing_backspace_delete():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("r", *"abcd", "backspace", "home", "delete")
        await pilot.pause()
        assert field(app).value == "bc"


async def test_rename_move_within_name():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("r", "end", "left", "left")
        assert field(app).cursor_position == len("ace2sam") - 2
        await pilot.press("home")
        assert field(app).cursor_position == 0
        await pilot.click(field(app), offset=(3, 0))
        await pilot.pause()
        assert app.renaming == 0  # a click inside the field keeps it open
        assert field(app).cursor_position == 3


async def test_space_and_r_type_into_the_field():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("r", "end", "space", "r")
        await pilot.pause()
        assert field(app).value == "ace2sam r"
        assert not row(app, 0).ticked


async def test_rename_enter_saves_ticks_and_says_so():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("down", "down", "down", "r", *"bowtie2sam", "enter")
        await pilot.pause()
        assert app.renaming is None
        assert row(app, 3).alias == "bowtie2sam" and row(app, 3).ticked
        assert "Renamed bowtie2sam.pl to bowtie2sam and ticked it." in footer(app)
        assert isinstance(app.focused, AliasList)


async def test_rename_already_ticked_row_message():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("space", "r", "x", "enter")
        await pilot.pause()
        assert "Renamed ace2sam to x." in footer(app)


async def test_rename_unchanged_does_not_tick():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("r", "enter")
        await pilot.pause()
        assert app.renaming is None and not row(app, 0).ticked
        assert "Renamed" not in footer(app)


async def test_rename_click_outside_saves_and_acts():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("r", "x")
        await pilot.click(row(app, 4).query_one(".tick", Static))
        await pilot.pause()
        assert app.renaming is None
        assert row(app, 0).alias == "x" and row(app, 0).ticked
        assert row(app, 4).ticked and app.highlight == 4


async def test_rename_esc_cancels_without_dialog():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("down", "down", "down", "r", "x", "escape")
        await pilot.pause()
        assert app.is_running and not app.dialog_open
        assert app.renaming is None
        assert row(app, 3).alias == "bowtie2sam.pl" and not row(app, 3).ticked
        assert app.highlight == 3
        assert "Rename cancelled. Kept bowtie2sam.pl." in footer(app)
        assert keys(app).startswith(" ↑↓ Move")


async def test_rename_scrolling_saves_first():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("down", "r", "x")
        await wheel(pilot)
        assert app.renaming is None
        assert row(app, 1).alias == "x"
        assert app.highlight == 1


@pytest.mark.parametrize(
    ("key", "lands_on"), [("down", 2), ("up", 0), ("pagedown", 12)]
)
async def test_rename_moving_saves_first(key, lands_on):
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("down", "r", "x", key)
        await pilot.pause()
        assert app.renaming is None
        assert row(app, 1).alias == "x"
        assert app.highlight == lands_on


async def test_rename_tab_saves_then_focuses_confirm():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("r", "x", "tab")
        await pilot.pause()
        assert app.renaming is None
        assert row(app, 0).alias == "x"
        assert app.focused.id == "confirm"


async def test_confirm_returns_renames():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press(*["down"] * 18, "r", *"sam2vcf", "enter", "enter")
        await pilot.pause()
    (picked,) = app.return_value
    assert picked == PickedAlias("sam2vcf", "/usr/local/bin/sam2vcf.pl", "sam2vcf.pl")
    assert picked.renamed


# --------------------------------------------------------------------------------------------------------------
# In the "Discard and exit?" dialog
# --------------------------------------------------------------------------------------------------------------


async def open_dialog(pilot):
    await pilot.press("down", "space", "escape")
    await pilot.pause()
    assert pilot.app.dialog_open


@pytest.mark.parametrize("how", ["escape", "enter", "click"])
async def test_dialog_keep_editing(how):
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await open_dialog(pilot)
        scroll = app.list_widget.scroll_y
        if how == "click":
            await pilot.click(app.query_one("#keep"))
        else:
            await pilot.press(how)
        await pilot.pause()
        assert app.is_running and not app.dialog_open
        assert row(app, 1).ticked and app.highlight == 1
        assert app.list_widget.scroll_y == scroll
        assert isinstance(app.focused, AliasList)


@pytest.mark.parametrize("keys_", [("right", "enter"), ("tab", "enter")])
async def test_dialog_discard_with_keys(keys_):
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await open_dialog(pilot)
        await pilot.press(keys_[0])
        assert app.focused.id == "discard"
        assert str(app.focused.render()) == "› Discard and exit ‹"
        await pilot.press(keys_[1])
        await pilot.pause()
    assert app.return_value is None


async def test_dialog_discard_with_click():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await open_dialog(pilot)
        await pilot.click(app.query_one("#discard"))
        await pilot.pause()
    assert app.return_value is None


async def test_dialog_click_outside_does_nothing():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await open_dialog(pilot)
        await pilot.click(row(app, 0).query_one(".tick", Static))
        await pilot.click(app.query_one("#confirm"))
        await pilot.pause()
        assert app.is_running and app.dialog_open
        assert not row(app, 0).ticked


async def test_dialog_is_centred_over_the_list():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await open_dialog(pilot)
        dialog = app.dialog.region
        assert (dialog.x, dialog.width, dialog.height) == (15, 50, 8)
        assert dialog.y == app.list_widget.region.y + 2
        assert app.query_one("#main").has_class("-dimmed")


# --------------------------------------------------------------------------------------------------------------
# Other events
# --------------------------------------------------------------------------------------------------------------


async def test_resize_recalculates_and_keeps_highlight_and_rename():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press(*["down"] * 20, "r")
        await pilot.pause()
        for size, list_rows, alias_width in [
            ((120, 40), 27, 28),
            ((80, 23), 10, 22),
            ((80, 24), 11, 22),
        ]:
            await pilot.resize_terminal(*size)
            await pilot.pause()
            assert app.list_rows == list_rows
            assert app.cols.alias == alias_width
            assert app.renaming == 20
            assert field(app).region.width == alias_width
            visible = app.list_widget.region
            assert visible.y <= row(app, 20).region.y < visible.bottom


async def test_smaller_than_80x24():
    app = make_app()
    async with app.run_test(size=(70, 20)) as pilot:
        await pilot.pause()
        assert app.list_rows == 7
        assert (app.cols.alias, app.cols.command) == (22, 32)


async def test_short_list_makes_short_widget():
    app = make_app(names=["bgzip", "tabix", "samtools"])
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert app.list_rows == 3
        assert "All 3 shown" in footer(app)


async def test_no_mouse_mode_copy():
    app = make_app(mouse=False)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        title = str(app.query_one("#title", Static).render())
        assert title.rstrip().endswith("Keyboard only")
        help_text = str(app.query_one("#help", Static).render())
        assert "Press Space to tick" in help_text and "Press R to rename" in help_text


async def test_everything_works_by_keyboard():
    app = make_app(mouse=False)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("down", "space", "r", "x", "enter", "tab", "enter")
        await pilot.pause()
    assert app.return_value == [PickedAlias("x", "/usr/local/bin/bgzip", "bgzip")]


async def test_buttons_are_picker_buttons():
    app = make_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert isinstance(app.query_one("#confirm"), PickerButton)
        assert isinstance(app.query_one("#cancel"), PickerButton)
