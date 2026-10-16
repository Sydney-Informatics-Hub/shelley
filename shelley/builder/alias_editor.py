from textual.app import App, ComposeResult
from textual.widgets import DataTable, Button, Header

class AliasEditorApp(App):

    TITLE = "Shelley interactive aliases editor"
    SUB_TITLE = "Select and edit aliases for modules"

    def __init__(self, aliases: list[tuple]):
        super().__init__()
        self.aliases = aliases
        self.rows = [tuple(" ") + a for a in self.aliases] # prepend a blank " " for selection
        self.edited = [] 

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable()
        yield Button("Confirm", id="confirm", variant="success")
        yield Button("Cancel", id="cancel", variant="warning")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "cell"
        self.tick, self.alias, self.path = table.add_columns("Include", "Alias name", "Command")
        table.add_rows(self.rows)

    def update_tick(self, val:str) -> str:
        if val == "✓":
            return " "
        return "✓"

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        # triggered by mouse click or Enter
        if event.cell_key.column_key == self.tick:
            event.data_table.update_cell(
                row_key=event.cell_key.row_key, 
                column_key=self.tick, 
                value=self.update_tick(str(event.value))
            )

        if event.cell_key.column_key == self.name or self.path:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            # output list of selected aliases and paths
            table = self.query_one(DataTable)
            rows = (table.get_row(key) for key in table.rows)
            result = [{"name": alias, "command": path} for tick, alias, path in rows if tick == "✓"]
            self.exit(result)
