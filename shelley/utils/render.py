"""Shared rendering utilities used across multiple command modules."""

import math

import questionary
from rich.box import ROUNDED
from rich.table import Table

from .style import console


def paginate(items: list, render_fn, page_size: int = 10) -> None:
    """Render items in pages, using questionary.select() for navigation.

    render_fn(page_items, page, total_pages, total) is called once per page.
    Navigation is skipped when all items fit on a single page.
    """
    total = len(items)
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    page = 0

    while True:
        start = page * page_size
        render_fn(items[start : start + page_size], page, total_pages, total)

        if total_pages <= 1:
            break

        choices = []
        if page < total_pages - 1:
            choices.append(questionary.Choice("Next →", value="next"))
        if page > 0:
            choices.append(questionary.Choice("← Previous", value="prev"))
        choices.append(questionary.Choice("Exit", value="quit"))

        action = questionary.select("", choices=choices).ask()
        if action is None or action == "quit":
            break
        elif action == "next":
            page += 1
        elif action == "prev":
            page -= 1


def truncate(text: str, max_len: int = 60) -> str:
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def render_tool_table(
    results: list[tuple[str, str]],
    title: str,
    border_style: str = "primary",
) -> None:
    """Render a Rich table of (name, description) tool pairs."""
    table = Table(
        title=title,
        box=ROUNDED,
        border_style=border_style,
        header_style="table.header",
        show_lines=False,
    )
    table.add_column("Tool", style="tool", no_wrap=True)
    table.add_column("Description", style="muted")
    for name, desc in results:
        table.add_row(name, truncate(desc))
    console.print(table)


def print_find_hint(source_note: str | None = None) -> None:
    """Print the 'use shelley find' footer line."""
    suffix = f" · Source: {source_note}" if source_note else ""
    console.print(
        f"[muted]For more information about a specific tool, use "
        f"[command]shelley find <name>[/command]{suffix}[/muted]"
    )
