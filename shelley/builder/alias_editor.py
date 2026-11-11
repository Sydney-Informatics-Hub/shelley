from rich.box import ROUNDED
from rich.console import Group
from rich.table import Table
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.coordinate import Coordinate
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Input, Static

from shelley.utils.style import (
    BIOCOMMONS_COLORS,
    TICK_OFF,
    TICK_ON,
    make_textual_theme,
    status_markup,
)


def normalize_aliases(aliases) -> list[dict]:
    """Return aliases in the canonical ``[{"name", "command"}]`` list form.

    shpc registries store aliases either as a ``{name: command}`` dict (upstream
    shpc-registry ``container.yaml``), as a list of ``{"name", "command"}``
    dicts (what shelley writes), or as a list of ``{name: command}`` dicts (what
    guts emits). Accept any and return the list form so the
    rest of the code has a single shape to work with.
    """
    if not aliases:
        return []
    if isinstance(aliases, dict):
        return [{"name": name, "command": command} for name, command in aliases.items()]
    result = []
    for a in aliases:
        if "name" in a and "command" in a:
            result.append({"name": a["name"], "command": a["command"]})
        else:  # a {name: command} mapping, possibly with several entries
            result.extend({"name": n, "command": c} for n, c in a.items())
    return result


def alias_summary(
    tool: str,
    version: str,
    chosen: list[dict],
    total: int,
    renamed: dict[str, str] | None = None,
) -> Group:
    """The record printed after Confirm: a Done line, the chosen aliases, a re-run hint.

    ``renamed`` maps a chosen alias name to its name before the rename.
    """
    renamed = renamed or {}
    table = Table(box=ROUNDED, border_style="primary", header_style="heading")
    table.add_column("Alias", style="hint.command", no_wrap=True)
    table.add_column("Command", style="path", overflow="fold")  # wrap, never cut
    for alias in chosen:
        command = Text(alias["command"])
        if alias["name"] in renamed:
            command.append(f"  (renamed from {renamed[alias['name']]})", style="muted")
        table.add_row(Text(alias["name"]), command)
    done = Text.from_markup(
        status_markup("success", f"Aliases chosen for {tool} {version}: ")
    )
    done.append(f"{len(chosen)} of {total}")
    hint = Text.assemble(
        "  ",
        ("To add or change aliases, run the build again:", "muted"),
        "\n  ",  # own line, so a long tag never splits the command
        (f"shelley build {tool}/{version} -i", "hint.command"),
    )
    return Group(done, table, hint)


class AliasTable(DataTable):
    """DataTable whose cells are selected by a single click.

    Stock DataTable only posts CellSelected when the clicked cell is already
    highlighted, so the first click just moves the cursor. Moving the cursor
    here, before DataTable's own click handler runs, makes every click select.
    """

    def on_click(self, event: events.Click) -> None:
        meta = event.style.meta
        if meta.get("row", -1) >= 0 and meta.get("column", -1) >= 0:
            self.cursor_coordinate = Coordinate(meta["row"], meta["column"])


class DiscardDialog(ModalScreen[bool]):
    """Ask before throwing away the ticks and renames. Dismisses with True to discard."""

    BINDINGS = [Binding("escape", "keep", "Keep editing")]

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog") as dialog:
            dialog.border_title = "Discard and exit?"  # shown in the panel border
            yield Static(
                "Nothing will be built, and your ticks and renames will be lost."
            )
            with Horizontal(classes="buttons"):
                yield Button("Keep editing", id="keep", compact=True)
                yield Button("Discard and exit", id="discard", compact=True)

    def on_mount(self) -> None:
        self.query_one("#keep", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "discard")

    def action_keep(self) -> None:
        self.dismiss(False)


class AliasEditorApp(App):
    TITLE = "Shelley alias editor"
    BINDINGS = [
        Binding("escape", "cancel", "Exit"),
        # priority: also wins over copy in the rename Input
        Binding("ctrl+c", "abort", "Quit now", priority=True),
    ]
    INSTR0 = (
        "An alias is a command from this container that you will need to run in "
        "your shell or scripts, such as [bold]samtools[/bold], "
        "[bold]vcftools[/bold] or [bold]STAR[/bold]. "
        "Leave out helper commands and scripts you won't run yourself, such as "
        "[bold]blast2sam.pl[/bold], [bold]htsfile[/bold] "
        "or [bold]guess-ploidy.py[/bold]. "
        "To change these later, run the interactive build again."
    )
    INSTR1 = (
        "Tick [bold]\\[ ][/bold] the commands you'll run yourself, such as [bold]samtools[/bold]. "
        "Omit helper scripts like [bold]blast2sam.pl[/bold].\n"
        "Optionally, click an alias name to rename it."
    )
    INSTR_INPUT = "Press Enter to save, or Esc to cancel the rename."
    RENAME_BAR_ROWS = 4  # border, label + input row, help/error row, border
    RENAME_ERROR = "Alias names can't contain spaces or /."
    CONFIRM_HINT = "Select at least one alias to proceed."
    TICK_COUNT = "{ticked} of {total} ticked"
    CSS_PATH = "alias_editor.tcss"
    ENABLE_COMMAND_PALETTE = False

    def __init__(self, aliases, tool: str = "", version: str = ""):
        super().__init__(ansi_color=False)  # use the theme colours in all terminals
        if tool:
            self.sub_title = f"{tool} {version}".rstrip()
        self.register_theme(make_textual_theme())
        self.theme = "biocommons"
        self.aliases = normalize_aliases(aliases)
        # DataTable rows; the first cell is the tick ("Include") column. Ticks are
        # Text, not str: DataTable parses str cells as markup and "[x]" would vanish.
        self.rows = [
            (
                Text(TICK_OFF, justify="center"),
                Text(a["name"], style=BIOCOMMONS_COLORS["command"]),  # sage
                Text(a["command"], style=BIOCOMMONS_COLORS["path"]),
            )  # teal
            for a in self.aliases
        ]
        self.original = {}  # row key -> name before any rename, for the summary
        self.renamed = {}  # set on Confirm: chosen name -> name before the rename
        self._renaming = None  # row key of the name currently being edited

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(self.INSTR1)
        yield AliasTable()
        with Vertical(id="rename_bar") as bar:  # the edit bar, shown while renaming
            bar.border_title = "Rename alias"  # shown in the panel border
            with Horizontal(id="rename_row"):  # "Rename x to: [input]" on one line
                yield Static(id="rename_label")
                yield Input(id="rename", placeholder="New alias name", compact=True)
            yield Static(id="rename_error")  # the Enter/Esc help, or the error
        yield Static(id="confirm_hint")
        with Horizontal(id="buttons", classes="buttons"):
            yield Button("Confirm", id="confirm", disabled=True, compact=True)
            yield Button("Cancel", id="cancel", compact=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(AliasTable)
        table.cursor_type = "cell"
        self.tick, self.alias, self.path = table.add_columns(
            Text("Include", justify="center"), "Alias name", "Command"
        )
        keys = table.add_rows(self.rows)
        self.original = {
            key: str(row[1]) for key, row in zip(keys, self.rows, strict=True)
        }
        self.query_one("#rename_bar").display = False
        # ensure screen starts at the top of the page
        self.call_after_refresh(self.screen.scroll_home, animate=False)
        self._update_confirm()  # show "0 of N ticked" from the start

    def on_resize(self, event: events.Resize) -> None:
        self._fit_table()

    def _fit_table(self) -> None:
        """Cap the table so the rest of the page, and the rename bar if open, fits."""
        # everything but the table takes ~12 rows: header, text, hint, buttons, footer
        reserved = 12 + (self.RENAME_BAR_ROWS if self._renaming is not None else 0)
        self.query_one(AliasTable).styles.max_height = max(
            5, self.size.height - reserved
        )

    def update_tick(self, val: str) -> Text:
        if val == TICK_ON:
            return Text(TICK_OFF, justify="center")
        return Text(TICK_ON, justify="center")

    def _update_confirm(self) -> None:
        """Update the tick counter, and enable Confirm once at least one row is ticked."""
        ticks = self.query_one(AliasTable).get_column(self.tick)
        ticked = sum(str(t) == TICK_ON for t in ticks)
        self.query_one("#confirm", Button).disabled = not ticked
        self.query_one("#confirm_hint", Static).update(
            self.TICK_COUNT.format(ticked=ticked, total=len(self.aliases))
            if ticked
            else self.CONFIRM_HINT
        )

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        column = event.cell_key.column_key
        if column == self.tick:
            event.data_table.update_cell(
                row_key=event.cell_key.row_key,
                column_key=self.tick,
                value=self.update_tick(str(event.value)),
            )
            self._update_confirm()
        elif column == self.alias:
            self._start_renaming(event.cell_key.row_key, str(event.value))

    def _start_renaming(self, row_key, name: str) -> None:
        self._renaming = row_key
        self.query_one("#rename_label", Static).update(
            Text.assemble("Rename ", (name, "bold"), " to:")
        )
        error = self.query_one("#rename_error", Static)
        error.update(self.INSTR_INPUT)
        error.remove_class("-error")
        self.query_one("#rename_bar").display = True
        self._fit_table()
        box = self.query_one(Input)
        box.value = name
        box.focus()

    def _stop_renaming(self) -> None:
        self._renaming = None
        self.query_one("#rename_bar").display = False
        self._fit_table()
        self.query_one(AliasTable).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self._renaming is None:
            return
        table = self.query_one(AliasTable)
        name = event.value.strip()
        old = str(table.get_cell(self._renaming, self.alias))
        if not name or name == old:  # nothing to change
            self._stop_renaming()
            return
        if any(c.isspace() for c in name) or "/" in name:
            error = self.query_one("#rename_error", Static)
            error.update(self.RENAME_ERROR)
            error.add_class("-error")
            return  # keep the bar open so the name can be fixed
        table.update_cell(
            self._renaming, self.alias, Text(name, style=BIOCOMMONS_COLORS["command"])
        )
        table.update_cell(self._renaming, self.tick, Text(TICK_ON, justify="center"))
        self._update_confirm()
        self._stop_renaming()

    def action_cancel(self) -> None:
        if self._renaming is not None:  # Esc while renaming cancels the rename only
            self._stop_renaming()
            return
        self._ask_discard()

    def action_abort(self) -> None:
        self.exit(None)

    def _ask_discard(self) -> None:
        def done(discard: bool | None) -> None:
            if discard:
                self.exit(None)

        self.push_screen(DiscardDialog(), done)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self._ask_discard()

        if event.button.id == "confirm":
            # output list of selected aliases and paths
            table = self.query_one(AliasTable)
            result = []
            for key in table.rows:
                tick, name, command = map(str, table.get_row(key))
                if str(tick) != TICK_ON:
                    continue
                result.append({"name": name, "command": command})
                if name != self.original[key]:
                    self.renamed[name] = self.original[key]
            self.exit(result)
