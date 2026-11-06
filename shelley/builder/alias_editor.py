from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.coordinate import Coordinate
from textual.widgets import Button, DataTable, Header, Input, Static

from shelley.utils.style import TICK_OFF, TICK_ON, make_textual_theme


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


class AliasEditorApp(App):
    TITLE = "Shelley interactive alias editor"
    BINDINGS = [Binding("escape", "cancel", "Cancel")]
    INSTR0 = (
        "An alias is a command from this container that you will need to run in "
        "your shell or scripts, such as [bold]samtools[/bold], "
        "[bold]vcftools[/bold] or [bold]STAR[/bold]."
    )
    INSTR1 = (
        "Leave out helper commands and scripts you won't run yourself, such as "
        "[bold]blast2sam.pl[/bold], [bold]htsfile[/bold] "
        "or [bold]guess-ploidy.py[/bold]."
    )
    INSTR2 = (
        "    • [bold]Click \\[ ][/bold] to tick each command you want to alias. "
        "To change them later, run the interactive build again."
    )
    INSTR3 = "    • [bold]Click an alias name[/bold] to rename it."
    INSTR_INPUT = "   Press ENTER to confirm • Press ESC to cancel"
    CSS_PATH = "alias_editor.tcss"

    def __init__(self, aliases):
        super().__init__(ansi_color=False)  # use the theme colours in all terminals
        self.register_theme(make_textual_theme())
        self.theme = "biocommons"
        self.aliases = normalize_aliases(aliases)
        # DataTable rows; the first cell is the tick ("Include") column. Ticks are
        # Text, not str: DataTable parses str cells as markup and "[x]" would vanish.
        self.rows = [
            (Text(TICK_OFF, justify="center"), a["name"], a["command"])
            for a in self.aliases
        ]
        self.edited = []
        self._renaming = None  # row key of the name currently being edited

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(self.INSTR0)
        yield Static(self.INSTR1)
        yield Static(self.INSTR2)
        yield Static(self.INSTR3)
        yield Input(id="rename", placeholder="New alias name")
        yield Static(self.INSTR_INPUT, id="instruct_input")
        yield AliasTable()
        with Horizontal():
            yield Button("Confirm", id="confirm", variant="success")
            yield Button("Cancel", id="cancel", variant="warning")

    def on_mount(self) -> None:
        table = self.query_one(AliasTable)
        table.cursor_type = "cell"
        self.tick, self.alias, self.path = table.add_columns(
            Text("Include", justify="center"), "Alias name", "Command"
        )
        table.add_rows(self.rows)
        # Hide alias rename widgets by default
        self.query_one(Input).display = False
        self.query_one("#instruct_input", Static).display = False

    def update_tick(self, val: str) -> Text:
        if val == TICK_ON:
            return Text(TICK_OFF, justify="center")
        return Text(TICK_ON, justify="center")

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        column = event.cell_key.column_key
        if column == self.tick:
            # tick or untick Include col
            event.data_table.update_cell(
                row_key=event.cell_key.row_key,
                column_key=self.tick,
                value=self.update_tick(str(event.value)),
            )
        elif column == self.alias:
            # rename aliases
            self._renaming = event.cell_key.row_key
            box = self.query_one(Input)
            box.value = str(event.value)
            box.display = True
            box.focus()

            self.query_one("#instruct_input", Static).display = True

    def _stop_renaming(self) -> None:
        self._renaming = None
        self.query_one(Input).display = False
        self.query_one("#instruct_input").display = False
        self.query_one(AliasTable).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        name = event.value.strip()
        if name and self._renaming is not None:
            self.query_one(AliasTable).update_cell(self._renaming, self.alias, name)
        self._stop_renaming()

    def action_cancel(self) -> None:
        if self._renaming is not None:
            self._stop_renaming()
        self.exit(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.exit(None)

        if event.button.id == "confirm":
            # output list of selected aliases and paths
            table = self.query_one(AliasTable)
            rows = (table.get_row(key) for key in table.rows)
            result = [
                {"name": alias, "command": path}
                for tick, alias, path in rows
                if str(tick) == TICK_ON
            ]
            self.exit(result)
