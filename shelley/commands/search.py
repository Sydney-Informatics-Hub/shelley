"""Search command — full-text search across the RSEC tool corpus."""

from ..search.rsec import RsecSource
from ..utils.cache import load_cvmfs_tool_ids
from ..utils.render import paginate, print_find_hint, render_tool_table
from ..utils.style import ShelleyStyle, console


def search_tools(query: str) -> None:
    """Search the RSEC corpus directly (no MCP server needed)."""
    with ShelleyStyle.create_status(f"Searching for: {query}") as status:
        try:
            source = RsecSource().load()
        except FileNotFoundError:
            console.print(
                ShelleyStyle.create_error_panel(
                    "Corpus Not Found",
                    "rsec_meta.json.gz is missing.",
                    "Run: shelley-build-rsec",
                )
            )
            return

        cvmfs_ids = load_cvmfs_tool_ids()
        if cvmfs_ids is not None:
            source.entries = [
                e
                for e in source.entries
                if e.get("id", "").lower().replace("-", "_") in cvmfs_ids
            ]

        names = source.search(query)

    if not names:
        console.print(
            ShelleyStyle.create_error_panel(
                "No Results",
                f"No tools matched '{query}'.",
                "Try broader terms — e.g. 'alignment' instead of 'short-read alignment'",
            )
        )
        return

    desc_for = {
        str(e.get("name") or e.get("id") or ""): str(e.get("description") or "")
        for e in source.entries
    }
    results = [(name, desc_for.get(name, "")) for name in names]

    def render_page(page_items, page, total_pages, total):
        _render_search_page(
            page_items,
            page,
            total_pages,
            total,
            query,
            cvmfs_filtered=(cvmfs_ids is not None),
        )

    paginate(results, render_page)


def _render_search_page(
    results: list[tuple[str, str]],
    page: int,
    total_pages: int,
    total: int,
    query: str,
    cvmfs_filtered: bool = False,
) -> None:
    """Render one page of search results."""
    count = total
    suffix = "es" if count != 1 else ""
    page_info = f" — page {page + 1} of {total_pages}" if total_pages > 1 else ""
    title = f"[header]Results for '[tool]{query}[/tool]' ({count} match{suffix}){page_info}[/header]"
    source_note = (
        "RSEC bio.tools (CVMFS-available tools)" if cvmfs_filtered else "RSEC bio.tools"
    )
    render_tool_table(results, title)
    print_find_hint(source_note=source_note)
