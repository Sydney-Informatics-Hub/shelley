"""The alias picker for `shelley build -i` (docs/reference/alias-picker.md).

One inline Textual widget for ticking and renaming the commands found in a container. Renaming
happens in the name cell itself: the row swaps its name cell for a one-line field of the same width,
so the field is part of the row's layout and cannot drift on scroll or resize.

Import this module only when the picker opens; it imports Textual.
"""

from dataclasses import dataclass
from typing import ClassVar

from rich.color import Color as RichColor
from rich.segment import Segment, Segments
from rich.style import Style
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.geometry import Size
from textual.scrollbar import ScrollBarRender, ScrollDown, ScrollTo, ScrollUp
from textual.widgets import Input, Static

from ..utils.style import BIOCOMMONS_COLORS, FOCUS_LEFT, FOCUS_RIGHT, make_textual_theme
from . import alias_copy as copy
from .alias_layout import ColumnLayout, column_layout, row_layout, scroll_counts

MESSAGE_SECONDS = 4.0
DIALOG_ROWS = 8


@dataclass(frozen=True)
class PickedAlias:
    """One ticked alias. `original` is the name it had before any rename."""

    name: str
    command: str
    original: str

    @property
    def renamed(self) -> bool:
        return self.name != self.original


# --------------------------------------------------------------------------------------------------------------
# Scrollbar: │ track and █ thumb, as drawn in alias-picker-screens.md
# --------------------------------------------------------------------------------------------------------------


class TrackScrollBarRender(ScrollBarRender):
    """Whole-cell thumb (█) on a thin track (│), keeping Textual's click and drag behaviour."""

    TRACK_COLOR: ClassVar[RichColor] = RichColor.parse(BIOCOMMONS_COLORS["muted"])

    @classmethod
    def render_bar(
        cls,
        size: int = 25,
        virtual_size: float = 50,
        window_size: float = 20,
        position: float = 0,
        thickness: int = 1,
        vertical: bool = True,
        back_color: RichColor | None = None,
        bar_color: RichColor | None = None,
    ) -> Segments:
        back = back_color
        if not (window_size and size and virtual_size and window_size < virtual_size):
            return Segments(
                [Segment(" " * thickness, Style(bgcolor=back))] * size, new_lines=True
            )
        thumb = max(1, round(window_size * size / virtual_size))
        span = virtual_size - window_size
        start = round((size - thumb) * position / span) if span else 0
        start = max(0, min(size - thumb, start))
        track = cls.TRACK_COLOR
        up = Segment(
            "│" * thickness,
            Style(color=track, bgcolor=back, meta={"@mouse.down": "scroll_up"}),
        )
        down = Segment(
            "│" * thickness,
            Style(color=track, bgcolor=back, meta={"@mouse.down": "scroll_down"}),
        )
        grab = Segment(
            "█" * thickness,
            Style(color=bar_color, bgcolor=back, meta={"@mouse.down": "grab"}),
        )
        segments = [up] * start + [grab] * thumb + [down] * (size - start - thumb)
        return Segments(segments, new_lines=True)


# --------------------------------------------------------------------------------------------------------------
# Rows
# --------------------------------------------------------------------------------------------------------------


class NameField(Input):
    """The rename field. Input already consumes printable keys, so Space and R type into it."""

    BINDINGS = [Binding("tab", "save_and_tab", show=False)]

    def action_save_and_tab(self) -> None:
        self.app.save_rename_then_buttons()

    DEFAULT_CSS = """
    NameField {
        margin-right: 2;
        background: $foreground;
        color: $background;
        &:focus { background-tint: $foreground 0%; }
        & > .input--selection { background: $background; color: $foreground; }
        & > .input--cursor { background: $background; color: $foreground; }
    }
    """


class AliasRow(Horizontal):
    DEFAULT_CSS = """
    AliasRow { height: 1; background: $surface; color: $foreground; }
    AliasRow.-highlight { background: $secondary; color: $shelley-on-selection; }
    AliasRow.-highlight.-dim { background: $panel; color: $foreground; }
    AliasRow > Static { width: auto; height: 1; }
    """

    def __init__(self, index: int, name: str, command: str) -> None:
        super().__init__()
        self.index = index
        self.alias = name
        self.original = name
        self.command = command
        self.ticked = False

    def compose(self) -> ComposeResult:
        for part in ("marker", "tick", "name", "cmd"):
            yield Static("", classes=part, markup=False)

    def draw(self, cols: ColumnLayout, *, highlighted: bool) -> None:
        self.set_class(highlighted, "-highlight")
        cells = copy.row_cells(
            self.alias, self.command, cols, ticked=self.ticked, highlighted=highlighted
        )
        for part, cell in zip(("marker", "tick", "name", "cmd"), cells, strict=True):
            self.query_one(f".{part}", Static).update(cell)
        for field in self.query(NameField):
            field.styles.width = cols.alias

    def on_click(self, event: events.Click) -> None:
        if isinstance(event.widget, NameField):
            return  # clicks inside the open field move its cursor
        self.app.row_clicked(self, event.widget)


class AliasList(VerticalScroll, can_focus=True):
    DEFAULT_CSS = """
    AliasList {
        height: 11;
        margin-right: 1;
        background: $surface;
        scrollbar-size-vertical: 1;
        scrollbar-background: $surface;
        scrollbar-background-hover: $surface;
        scrollbar-background-active: $surface;
        scrollbar-color: $foreground;
        scrollbar-color-hover: $foreground;
        scrollbar-color-active: $foreground;
    }
    """
    BINDINGS = [
        Binding("up", "move(-1)", show=False),
        Binding("down", "move(1)", show=False),
        Binding("pageup", "page(-1)", show=False),
        Binding("pagedown", "page(1)", show=False),
        Binding("home", "ends(0)", show=False),
        Binding("end", "ends(1)", show=False),
        Binding("space", "tick", show=False),
        Binding("r,f2", "rename", show=False),
        Binding("enter", "confirm", show=False),
    ]

    def on_mount(self) -> None:
        self.vertical_scrollbar.renderer = TrackScrollBarRender

    def on_resize(self, event: events.Resize) -> None:
        # Keep the highlighted row in view once the new height is laid out.
        self.call_after_refresh(self.app._keep_highlight_visible)

    def watch_scroll_y(self, old: float, new: float) -> None:
        super().watch_scroll_y(old, new)
        if old != new and self.is_mounted:
            self.app.refresh_status()

    # Scrolling by the user (wheel, scrollbar) saves an open rename first. Scrolling done by the
    # layout (resize, keeping the highlight in view) does not, so a rename survives a resize.
    def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        self.app.save_rename()

    def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        self.app.save_rename()

    def on_scroll_up(self, message: ScrollUp) -> None:
        self.app.save_rename()

    def on_scroll_down(self, message: ScrollDown) -> None:
        self.app.save_rename()

    def on_scroll_to(self, message: ScrollTo) -> None:
        self.app.save_rename()

    def action_move(self, step: int) -> None:
        self.app.move_highlight(step)

    def action_page(self, direction: int) -> None:
        self.app.move_highlight(direction * max(1, self.size.height))

    def action_ends(self, end: int) -> None:
        self.app.move_highlight(10**6 if end else -(10**6))

    def action_tick(self) -> None:
        self.app.toggle_highlighted()

    def action_rename(self) -> None:
        self.app.start_rename()

    def action_confirm(self) -> None:
        self.app.try_confirm()


# --------------------------------------------------------------------------------------------------------------
# Buttons and dialog
# --------------------------------------------------------------------------------------------------------------


class PickerButton(Static, can_focus=True):
    """A plain button: label centred, `› Label ‹` when focused, Enter or Space to press."""

    BINDINGS = [Binding("enter,space", "press", show=False)]

    def __init__(self, label: str, *, id: str) -> None:
        super().__init__("", id=id, markup=False)
        self.label = label

    def on_mount(self) -> None:
        self.draw()

    def draw(self, focused: bool = False) -> None:
        self.update(
            f"{FOCUS_LEFT} {self.label} {FOCUS_RIGHT}" if focused else self.label
        )

    def on_focus(self) -> None:
        self.draw(focused=True)

    def on_blur(self) -> None:
        self.draw(focused=False)

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.app.button_pressed(self.id)

    def action_press(self) -> None:
        self.app.button_pressed(self.id)


class Dialog(Vertical):
    """ "Discard and exit?", drawn over the dimmed list. It must be answered."""

    DEFAULT_CSS = """
    Dialog {
        layer: dialog;
        display: none;
        width: 50;
        height: 8;
        border: solid $foreground;
        background: $surface;
        color: $foreground;
        padding: 0 1;
    }
    Dialog.-open { display: block; }
    Dialog #dlg-title { text-style: bold; height: 1; }
    Dialog #dlg-body { height: 2; margin-top: 1; }
    Dialog #dlg-buttons { height: 1; margin-top: 1; align-horizontal: right; }
    Dialog PickerButton { height: 1; content-align: center middle; }
    Dialog #keep { width: 16; background: $secondary; color: $shelley-on-selection; }
    Dialog #discard {
        width: 20; margin: 0 3; background: $warning; color: $shelley-on-primary;
    }
    """
    BINDINGS = [
        Binding("left,right,tab,shift+tab", "switch", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Static(copy.DLG_TITLE, id="dlg-title", markup=False)
        yield Static(copy.DLG_BODY, id="dlg-body", markup=False)
        with Horizontal(id="dlg-buttons"):
            yield PickerButton(copy.DLG_KEEP, id="keep")
            yield PickerButton(copy.DLG_DISCARD, id="discard")

    def action_switch(self) -> None:
        keep = self.query_one("#keep", PickerButton)
        target = "#discard" if keep.has_focus else "#keep"
        self.query_one(target, PickerButton).focus()


# --------------------------------------------------------------------------------------------------------------
# The app
# --------------------------------------------------------------------------------------------------------------


class AliasPickerApp(App[list[PickedAlias] | None]):
    """Returns the ticked aliases on Confirm, or None when the user cancels or discards."""

    CSS = """
    Screen { layers: base dialog; background: $background; color: $foreground; height: auto; }
    /* Textual pads an inline screen with a blank row above and below. The widget is already
       terminal height − 1, so those rows would push it past the terminal and cut off the key bar. */
    Screen:inline { border-top: none; border-bottom: none; }
    #title { height: 1; background: $panel; text-style: bold; }
    #help { height: 2; }
    .gap { height: 1; }
    #headings { height: 1; background: $panel; text-style: bold; }
    #footer { height: 1; }
    #buttons { height: 3; }
    #reason { width: 1fr; height: 3; content-align: left middle; color: $shelley-muted; padding-left: 3; }
    #buttons PickerButton { height: 3; content-align: center middle; }
    #confirm { width: 13; background: $primary; color: $shelley-on-primary; text-style: bold; }
    #confirm.-unavailable { background: $surface; color: $shelley-muted; text-style: none; }
    #cancel { width: 12; margin: 0 2; background: $shelley-cancel; color: $foreground; }
    #keys { height: 1; background: $surface; }
    .-dimmed { text-opacity: 50%; }
    """
    BINDINGS = [
        Binding("escape", "escape", show=False),
        Binding("ctrl+c", "abort", show=False, priority=True),
        Binding("left,right", "switch_button", show=False),
    ]

    def __init__(
        self,
        aliases: list[dict],
        container: str,
        version: str,
        *,
        mouse: bool = True,
        command: str = "shelley",
    ) -> None:
        super().__init__(ansi_color=False)
        self.register_theme(make_textual_theme())
        self.theme = "biocommons"
        self.aliases = [(a["name"], a["command"]) for a in aliases]
        self.container = container
        self.version = version
        self.mouse = mouse
        self.command_name = command
        self.highlight = 0
        self.renaming: int | None = None
        self.message = ""
        self.message_style = ""
        self._message_timer = None
        self.cols = column_layout(80)
        self.list_rows = 0

    # ---- composition and layout ----------------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Vertical(id="main"):
            yield Static("", id="title", markup=False)
            line1, line2 = copy.help_lines(mouse=self.mouse)
            yield Static(f" {line1}\n {line2}", id="help", markup=False)
            yield Static("", classes="gap", id="gap-help")
            yield Static("", id="headings", markup=False)
            with AliasList():
                for i, (name, command) in enumerate(self.aliases):
                    yield AliasRow(i, name, command)
            yield Static("", id="footer")
            yield Static("", classes="gap", id="gap-footer")
            with Horizontal(id="buttons"):
                yield Static(copy.BTN_CONFIRM_REASON, id="reason", markup=False)
                yield PickerButton(copy.BTN_CONFIRM, id="confirm")
                yield PickerButton(copy.BTN_CANCEL, id="cancel")
            yield Static("", classes="gap", id="gap-buttons")
            yield Static("", id="keys")
        yield Dialog()

    def on_mount(self) -> None:
        self.apply_layout(self.size)
        self.query_one(AliasList).focus()

    def on_resize(self, event: events.Resize) -> None:
        self.apply_layout(event.size)

    @property
    def rows(self) -> list[AliasRow]:
        return list(self.query(AliasRow))

    @property
    def list_widget(self) -> AliasList:
        return self.query_one(AliasList)

    def apply_layout(self, size: Size) -> None:
        rows = row_layout(size.height, len(self.aliases))
        self.cols = column_layout(size.width)
        self.list_rows = rows.list_rows
        self.list_widget.styles.height = rows.list_rows
        for name, keep in (("gap-help", 3), ("gap-footer", 2), ("gap-buttons", 1)):
            self.query_one(f"#{name}").display = rows.gaps >= keep
        self.query_one("#title", Static).update(
            copy.title_bar(
                self.container,
                self.version,
                size.width,
                mouse=self.mouse,
                command=self.command_name,
            )
        )
        self.query_one("#headings", Static).update(
            "".join(copy.heading_cells(self.cols))
        )
        for row in self.rows:
            row.draw(self.cols, highlighted=row.index == self.highlight)
        self.refresh_status()
        self.call_after_refresh(self._keep_highlight_visible)

    def _keep_highlight_visible(self) -> None:
        if self.rows:
            self.rows[self.highlight].scroll_visible(animate=False, immediate=True)

    # ---- state -----------------------------------------------------------------------------------------

    @property
    def ticked(self) -> int:
        return sum(row.ticked for row in self.rows)

    @property
    def dirty(self) -> bool:
        return any(row.ticked or row.alias != row.original for row in self.rows)

    @property
    def dialog(self) -> Dialog:
        return self.query_one(Dialog)

    @property
    def dialog_open(self) -> bool:
        return self.dialog.has_class("-open")

    def refresh_status(self) -> None:
        """Footer, Confirm availability and the key bar."""
        total = len(self.aliases)
        alias_list = self.list_widget
        above, below = scroll_counts(round(alias_list.scroll_y), self.list_rows, total)
        width = self.size.width
        line = copy.footer_line(
            self.ticked, total, above, below, width, message=self.message
        )
        footer = Text(line)
        scroll = copy.scroll_text(above, below, total)
        if line.endswith(scroll + "  "):
            footer.stylize(
                BIOCOMMONS_COLORS["muted"], len(line) - len(scroll) - 2, len(line) - 2
            )
        if self.message and self.message_style:
            start = 3 + len(copy.count_text(self.ticked, total)) + 3
            footer.stylize(self.message_style, start, start + len(self.message))
        self.query_one("#footer", Static).update(footer)

        confirm = self.query_one("#confirm", PickerButton)
        available = self.ticked > 0
        confirm.set_class(not available, "-unavailable")
        confirm.can_focus = available
        self.query_one("#reason").visible = not available

        self.query_one("#keys", Static).update(
            copy.key_bar(self.key_mode(), width, scrolls=below + above > 0)
        )

    def key_mode(self) -> str:
        focused = self.focused
        if self.dialog_open:
            return "dialog"
        if isinstance(focused, NameField):
            return "rename"
        if isinstance(focused, PickerButton):
            return "buttons"
        return "list"

    def say(self, message: str, style: str = "") -> None:
        self.message, self.message_style = message, style
        if self._message_timer is not None:
            self._message_timer.stop()
        self._message_timer = self.set_timer(MESSAGE_SECONDS, self.clear_message)
        self.refresh_status()

    def clear_message(self) -> None:
        if self.message:
            self.message = ""
            self.refresh_status()

    # ---- list actions --------------------------------------------------------------------------------------

    def redraw_row(self, index: int) -> None:
        self.rows[index].draw(self.cols, highlighted=index == self.highlight)

    def set_highlight(self, index: int) -> None:
        index = max(0, min(len(self.aliases) - 1, index))
        old, self.highlight = self.highlight, index
        if old != index:
            self.redraw_row(old)
        self.redraw_row(index)
        self.rows[index].scroll_visible(animate=False, immediate=True)

    def move_highlight(self, step: int) -> None:
        self.save_rename()
        self.clear_message()
        self.set_highlight(self.highlight + step)
        self.refresh_status()

    def toggle(self, index: int) -> None:
        self.clear_message()
        row = self.rows[index]
        row.ticked = not row.ticked
        self.redraw_row(index)
        self.refresh_status()

    def toggle_highlighted(self) -> None:
        self.toggle(self.highlight)

    def row_clicked(self, row: AliasRow, cell) -> None:
        if self.dialog_open:
            return
        self.save_rename()
        self.list_widget.focus()
        self.set_highlight(row.index)
        if cell is not None and cell.has_class("tick"):
            self.toggle(row.index)
        elif cell is not None and cell.has_class("name"):
            self.start_rename()
        else:
            self.clear_message()
            self.refresh_status()

    # ---- renaming ------------------------------------------------------------------------------------------

    def start_rename(self) -> None:
        if self.renaming is not None or self.dialog_open:
            return
        self.clear_message()
        index = self.highlight
        row = self.rows[index]
        cell = row.query_one(".name", Static)
        field = NameField(value=row.alias, compact=True, select_on_focus=False)
        field.styles.width = self.cols.alias
        cell.display = False
        row.mount(field, after=cell)
        self.renaming = index
        field.focus()
        field.select_all()
        self.refresh_status()

    def _close_rename(self, new_name: str | None) -> None:
        index, self.renaming = self.renaming, None
        row = self.rows[index]
        field = row.query_one(NameField)
        old = row.alias
        if new_name is None:
            self.message = ""
            self.say(copy.rename_cancelled_message(old))
        else:
            new = new_name.strip()
            if new and new != old:
                was_ticked = row.ticked
                row.alias = new
                row.ticked = True
                self.say(copy.rename_saved_message(old, new, was_ticked=was_ticked))
        field.remove()
        row.query_one(".name", Static).display = True
        self.redraw_row(index)
        self.refresh_status()

    def save_rename(self) -> None:
        if self.renaming is not None:
            self._close_rename(self.rows[self.renaming].query_one(NameField).value)

    def save_rename_then_buttons(self) -> None:
        """Tab while renaming: save, then focus Confirm (Cancel if nothing is ticked)."""
        self.save_rename()
        confirm = self.query_one("#confirm", PickerButton)
        (
            confirm if confirm.can_focus else self.query_one("#cancel", PickerButton)
        ).focus()

    def cancel_rename(self) -> None:
        if self.renaming is not None:
            self._close_rename(None)
            self.list_widget.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.save_rename()
        self.list_widget.focus()

    def on_descendant_blur(self, event: events.DescendantBlur) -> None:
        # Tab, a click elsewhere or any other focus change saves the edit.
        if isinstance(event.widget, NameField) and self.renaming is not None:
            self.save_rename()

    def on_descendant_focus(self, event: events.DescendantFocus) -> None:
        on_list = isinstance(event.widget, (AliasList, NameField))
        if self.rows:
            self.rows[self.highlight].set_class(not on_list, "-dim")
        self.refresh_status()

    # ---- buttons, exit and the dialog -------------------------------------------------------------------

    def try_confirm(self) -> None:
        self.save_rename()
        if self.ticked == 0:
            self.say(copy.MSG_CONFIRM_EMPTY, BIOCOMMONS_COLORS["warning"])
            return
        self.exit(
            [
                PickedAlias(name=row.alias, command=row.command, original=row.original)
                for row in self.rows
                if row.ticked
            ]
        )

    def button_pressed(self, button_id: str | None) -> None:
        if button_id == "keep":
            self.close_dialog()
        elif button_id == "discard":
            self.exit(None)
        elif self.dialog_open:
            return  # the dialog must be answered
        elif button_id == "confirm":
            self.try_confirm()
        elif button_id == "cancel":
            self.save_rename()
            self.request_exit()

    def request_exit(self) -> None:
        """Esc on the list or Cancel: ask only when ticks or renames would be lost."""
        if self.dirty:
            self.open_dialog()
        else:
            self.exit(None)

    def open_dialog(self) -> None:
        dialog = self.dialog
        width = self.size.width
        dialog_width = max(40, min(56, width - 30))
        dialog.styles.width = dialog_width
        alias_list = self.list_widget
        top = alias_list.region.y + max(0, -(-(self.list_rows - DIALOG_ROWS) // 2))
        dialog.styles.offset = ((width - dialog_width) // 2, top)
        dialog.add_class("-open")
        self.query_one("#main").add_class("-dimmed")
        self.query_one("#keep", PickerButton).focus()
        self.refresh_status()

    def close_dialog(self) -> None:
        self.dialog.remove_class("-open")
        self.query_one("#main").remove_class("-dimmed")
        self.list_widget.focus()
        self.refresh_status()

    def action_escape(self) -> None:
        if self.renaming is not None:
            self.cancel_rename()
        elif self.dialog_open:
            self.close_dialog()
        else:
            self.request_exit()

    def action_abort(self) -> None:
        self.exit(None)

    def action_switch_button(self) -> None:
        focused = self.focused
        if self.dialog_open or not isinstance(focused, PickerButton):
            return
        confirm = self.query_one("#confirm", PickerButton)
        cancel = self.query_one("#cancel", PickerButton)
        if focused is cancel and confirm.can_focus:
            confirm.focus()
        elif focused is confirm:
            cancel.focus()
