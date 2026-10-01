"""Batch module building utilities."""

from pathlib import Path

from rich.box import ROUNDED
from rich.table import Table

from ..commands.build import build_module
from .style import (
    console,
    ShelleyStyle,
    print_info,
    print_rule,
)


def read_tools_file(path: Path) -> list[str]:
    """Read tool specs from a file, one per line.

    Strips inline comments (anything after ``#``), blank lines, and
    leading/trailing whitespace. Raises FileNotFoundError if path is missing.
    """
    tools = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            tools.append(line)
    return tools


def batch_build_modules(tools: list[str]) -> int:
    """Build Lmod modules for multiple tools in sequence.

    Args:
        tools: Tool names/specifications (e.g. ``["samtools", "fastqc/0.12.1"]``).

    Returns:
        0 if all builds succeed, 1 if any fail.

    Note: interactive alias curation (``-i``/``--interactive``) is not supported
    in batch mode; each tool builds non-interactively.
    """
    if not tools:
        console.print(
            ShelleyStyle.create_info_panel(
                "No tools specified",
                "Pass a file of tool specs to build in batch:\n\n"
                "[command]shelley build tools.txt[/command]",
            )
        )
        return 0

    console.clear()
    print_info(f"Building modules for {len(tools)} tools")

    tools_table = Table(
        title="[header]Tools to Build[/header]",
        box=ROUNDED,
        border_style="border",
        header_style="table.header",
    )
    tools_table.add_column("#", style="muted", width=4)
    tools_table.add_column("Tool", style="tool")
    tools_table.add_column("Status", style="muted")

    for i, tool in enumerate(tools, 1):
        tools_table.add_row(str(i), tool, "Pending")

    console.print(tools_table)
    print_rule()

    success_count = 0
    total_count = len(tools)
    results: list[tuple[str, bool, str]] = []

    for i, tool in enumerate(tools, 1):
        console.print(
            f"\n[header]Building {i}/{total_count}:[/header] [tool]{tool}[/tool]"
        )
        if build_module(tool):
            success_count += 1
            results.append((tool, True, "Success"))
        else:
            results.append((tool, False, "Failed"))

    print_rule("Build Results")
    results_table = Table(
        title="[header]Build Summary[/header]",
        box=ROUNDED,
        border_style="border",
        header_style="table.header",
    )
    results_table.add_column("Tool", style="tool")
    results_table.add_column("Status", justify="center")
    results_table.add_column("Result", style="muted")

    for tool, success, status in results:
        status_style = "status.success" if success else "status.error"
        icon = "✓" if success else "✗"
        results_table.add_row(tool, f"[{status_style}]{icon}[/{status_style}]", status)

    console.print(results_table)

    if success_count == total_count:
        console.print(
            ShelleyStyle.create_info_panel(
                "All Modules Built Successfully! 🎉",
                f"Successfully built {success_count}/{total_count} modules.\n\nNext steps:\n"
                "• [command]module avail[/command] - See available modules\n"
                "• [command]module load <tool>/<version>[/command] - Load a module",
            )
        )
        return 0

    console.print(
        ShelleyStyle.create_warning_panel(
            "Some Modules Failed",
            f"Successfully built {success_count}/{total_count} modules. "
            "Check errors above for failed builds.",
        )
    )
    return 1
