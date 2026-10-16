from textual.app import App, ComposeResult
from textual.widgets import Button, DataTable, Header


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


class AliasEditorApp(App):
    TITLE = "Shelley interactive aliases editor"
    SUB_TITLE = "Select and edit aliases for modules"

    def __init__(self, aliases):
        super().__init__()
        self.aliases = normalize_aliases(aliases)
        # DataTable rows are tuples; prepend a blank " " for the selection column
        self.rows = [(" ", a["name"], a["command"]) for a in self.aliases]
        self.edited = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable()
        yield Button("Confirm", id="confirm", variant="success")
        yield Button("Cancel", id="cancel", variant="warning")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "cell"
        self.tick, self.alias, self.path = table.add_columns(
            "Include", "Alias name", "Command"
        )
        table.add_rows(self.rows)

    def update_tick(self, val: str) -> str:
        if val == "✓":
            return " "
        return "✓"

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        # triggered by mouse click or Enter
        if event.cell_key.column_key == self.tick:
            event.data_table.update_cell(
                row_key=event.cell_key.row_key,
                column_key=self.tick,
                value=self.update_tick(str(event.value)),
            )

        if event.cell_key.column_key == self.alias or self.path:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.exit()
        
        if event.button.id == "confirm":
            # output list of selected aliases and paths
            table = self.query_one(DataTable)
            rows = (table.get_row(key) for key in table.rows)
            result = [
                {"name": alias, "command": path}
                for tick, alias, path in rows
                if tick == "✓"
            ]
            self.exit(result)

