#!/usr/bin/env python3
"""
Shelley Styling Module

Rich-based styling for Shelley following Australian BioCommons design guidelines.
Provides consistent colors, themes, and output formatting across the application.
"""

from rich.console import Console
from rich.theme import Theme
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.status import Status
from rich.rule import Rule
from rich.columns import Columns
from rich.align import Align
from rich.box import ROUNDED, DOUBLE, SIMPLE, HEAVY
from rich.style import Style
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

# Australian BioCommons Color Palette (Official Colors)
BIOCOMMONS_COLORS = {
    # Primary BioCommons brand colors
    "primary": "#2cb77c",        # PANTONE 2413 - Bright Green (primary brand)
    "secondary": "#205a86",      # PANTONE 2161 - Dark Blue
    "accent": "#f49f1d",         # PANTONE 7408 - Orange
    
    # BioCommons logo colors
    "magenta": "#ed087c",        # PANTONE 226 - Bright Pink/Magenta
    "teal": "#5ac3b1",           # PANTONE 7465 - Teal/Turquoise
    "purple": "#b21e8d",        # PANTONE 241 - Purple/Magenta
    "sage": "#8ea869",          # PANTONE 5777 - Sage Green
    
    # Status colors (adapted from BioCommons palette)
    "success": "#2cb77c",       # Bright Green
    "warning": "#f49f1d",       # Orange
    "error": "#ed087c",         # Bright Pink
    "info": "#5ac3b1",          # Teal
    
    # UI colors
    "muted": "#708090",         # Slate Gray - muted text
    "border": "#205a86",        # Dark Blue - borders/dividers
    "text": "#000000",          # Black - main text
    
    # Tool colors
    "tool": "#2cb77c",          # Bright Green - tool names
    "version": "#205a86",       # Dark Blue - version numbers
    "command": "#8ea869",       # Sage Green - commands
    "path": "#5ac3b1",          # Teal - file paths
}

# Rich Theme Definition
SHELLEY_THEME = Theme({
    # Basic styling
    "primary": BIOCOMMONS_COLORS["primary"],
    "secondary": BIOCOMMONS_COLORS["secondary"],
    "accent": BIOCOMMONS_COLORS["accent"],
    "success": BIOCOMMONS_COLORS["success"],
    "warning": BIOCOMMONS_COLORS["warning"],
    "error": BIOCOMMONS_COLORS["error"],
    "info": BIOCOMMONS_COLORS["info"],
    "muted": BIOCOMMONS_COLORS["muted"],
    
    # Semantic styling
    "tool": f"bold {BIOCOMMONS_COLORS['tool']}",
    "version": f"bold {BIOCOMMONS_COLORS['version']}",
    "command": f"bold {BIOCOMMONS_COLORS['command']}",
    "path": f"{BIOCOMMONS_COLORS['path']}",
    "directory": f"bold {BIOCOMMONS_COLORS['info']}",
    
    # Status styling  
    "status.success": f"bold {BIOCOMMONS_COLORS['success']}",
    "status.warning": f"bold {BIOCOMMONS_COLORS['warning']}",
    "status.error": f"bold {BIOCOMMONS_COLORS['error']}",
    "status.info": f"bold {BIOCOMMONS_COLORS['info']}",
    
    # UI elements
    "header": f"bold {BIOCOMMONS_COLORS['primary']}",
    "subheader": f"bold {BIOCOMMONS_COLORS['primary']}",
    "prompt": f"bold {BIOCOMMONS_COLORS['primary']}",
    "border": BIOCOMMONS_COLORS["primary"],
    "highlight": f"bold {BIOCOMMONS_COLORS['primary']}",
    
    # Table styling
    "table.header": f"bold {BIOCOMMONS_COLORS['primary']}",
    "table.border": BIOCOMMONS_COLORS["primary"],
    
    # Progress bars
    "progress.bar": BIOCOMMONS_COLORS["primary"],
    "progress.complete": BIOCOMMONS_COLORS["success"],
    "progress.remaining": BIOCOMMONS_COLORS["muted"],
})

# Global console instance with BioCommons theme
console = Console(theme=SHELLEY_THEME, width=120)

# Banner artwork, shared with the BioShell login banner (/etc/update-motd.d).
# Every line is exactly BANNER_WIDTH cells wide; `{welcome}` is filled with the
# inner content (BANNER_WIDTH - 2 cells) by create_banner().
BANNER_WIDTH = 87
BANNER_ART = """\
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                       ☆                              ★  ☆           │
│                               ★                  ★                   ☆              │
│       ☆         ☆                                                                   │
│★           ★                                  ☆               ★                     │
│            ☆                    ★                                                   │
│                                                                    ★                │
│            ████  ▒▒▒                                                      ☆         │
│           ██████ ▒▘▒▒                          ★                                    │
│        ▒▒████████▒▒                                                                 │
│───────── ▒▒    ▒▒ ──────────────────────────────────────────────────────────────────│
│                                                                                     │
│{welcome}│
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘"""


class ShelleyStyle:
    """Styling utilities for Shelley."""
    
    @staticmethod
    def create_header(title: str, subtitle: str = "") -> Panel:
        """Create a styled header panel."""
        if subtitle:
            content = f"[header]{title}[/header]\n[muted]{subtitle}[/muted]"
        else:
            content = f"[header]{title}[/header]"
            
        return Panel(
            Align.center(content), 
            box=DOUBLE,
            border_style="primary",
            padding=(1, 2)
        )
    
    @staticmethod
    def create_banner() -> Text:
        """Create the main Shelley banner (shares the BioShell MOTD artwork).

        The artwork draws its own frame, so it is returned as plain Text rather
        than wrapped in a Panel. Keep it in sync with the login banner at
        build/ansible/roles/motd/files/99-bioshell in the BioShell repo.
        """
        from .. import __version__

        left = "   Hey there, I'm Shelley!"
        right = f"v{__version__}   "
        pad = " " * max(1, BANNER_WIDTH - 2 - len(left) - len(right))
        welcome = f"{left}{pad}{right}"

        return Text.from_markup(
            f"[bold {BIOCOMMONS_COLORS['teal']}]{BANNER_ART.format(welcome=welcome)}[/]"
        )


    @staticmethod
    def create_help_table(commands: List[Dict[str, str]]) -> Table:
        """Create a styled help table."""
        table = Table(
            title="[primary][bold]Available Commands[/bold][/primary]",
            box=ROUNDED,
            border_style="primary",
            header_style="table.header",
            show_lines=True
        )
        
        table.add_column("Command", style="primary", no_wrap=True)
        table.add_column("Description", style="muted")
        table.add_column("Example", style="primary")
        
        for cmd in commands:
            table.add_row(
                cmd["command"],
                cmd["description"], 
                cmd.get("example", "")
            )
        
        return table
    
    @staticmethod
    def create_versions_table(tool_name: str, versions: List[str]) -> Table:
        """Create a styled versions table."""
        table = Table(
            title=f"[primary][bold]Available Versions for[/bold][/primary] [primary][bold]{tool_name}[/bold][/primary]",
            box=ROUNDED,
            border_style="primary", 
            header_style="table.header",
            show_header=False
        )
        
        table.add_column("Version", style="primary")
        table.add_column("Status", style="success")
        
        for version in versions:
            table.add_row(version, "✓ Available")
        
        return table
    
    @staticmethod
    def create_versions_with_paths_table(tool_name: str, version_path_pairs: List[Tuple[str, str]]) -> Table:
        """Create a styled versions table with full CVMFS paths."""
        table = Table(
            title=f"[primary][bold]Available Versions for[/bold][/primary] [primary][bold]{tool_name}[/bold][/primary]",
            box=ROUNDED,
            border_style="primary", 
            header_style="table.header",
            show_header=False
        )
        
        table.add_column("Version", style="primary", no_wrap=True)
        table.add_column("Container Path", style="accent")
        
        for version, path in version_path_pairs:
            table.add_row(version, path)
        
        return table
    
    @staticmethod
    def create_tools_table(tools: List[Dict[str, Any]], limit: int = None) -> Table:
        """Create a styled tools list table."""
        display_count = len(tools)
        if limit and len(tools) > limit:
            tools = tools[:limit]
            
        table = Table(
            title=f"[header]Bioinformatics Tools[/header] [muted]({len(tools)} shown{f' of {display_count}' if limit else ''})[/muted]",
            box=ROUNDED,
            border_style="border",
            header_style="table.header"
        )
        
        table.add_column("Tool", style="tool", no_wrap=True)
        table.add_column("Description", style="muted", ratio=2)
        table.add_column("Category", style="info")
        
        for tool in tools:
            table.add_row(
                tool.get("name", "Unknown"),
                tool.get("description", "No description available")[:80] + "..." if tool.get("description", "") and len(tool.get("description", "")) > 80 else tool.get("description", "No description available"),
                tool.get("category", "General")
            )
        
        return table
    
    @staticmethod  
    def create_build_success(tool_name: str, version: str, module_path: Path) -> Panel:
        """Create a styled build success message."""
        content = f"""[status.success]✅ Module Built Successfully![/status.success]

[header]Tool:[/header] [tool]{tool_name}[/tool]
[header]Version:[/header] [version]{version}[/version]  
[header]Module Path:[/header] [path]{module_path}[/path]

[header]To load this module:[/header]
[command]module load {tool_name}/{version}[/command]

[header]To list all modules:[/header]
[command]module avail[/command]"""

        return Panel(
            content,
            title="[status.success]Build Complete[/status.success]",
            box=ROUNDED,
            border_style="success",
            padding=(1, 2)
        )

    @staticmethod
    def create_clean_success(tool_name: str, version: str, report: Dict[str, Any]) -> Panel:
        """Create a styled clean/uninstall success message."""
        removed = []
        if report.get("shpc_removed"):
            removed.append("shpc module, wrappers and container artifacts")
        if report.get("modulefile_removed"):
            removed.append("Lmod modulefile symlink")
        if report.get("registry_tag_removed"):
            removed.append("local registry tag (was added locally, not upstream)")
        if report.get("registry_entry_deleted"):
            removed.append(
                "local registry entry (last installed version — container.yaml and "
                "any cached upstream tags were removed too)"
            )
        removed_text = "\n".join(f"  [muted]• {item}[/muted]" for item in removed) or \
            "  [muted]• nothing further to remove[/muted]"

        content = f"""[status.success]✅ Module Removed[/status.success]

[header]Tool:[/header] [tool]{tool_name}[/tool]
[header]Version:[/header] [version]{version}[/version]

[header]Removed:[/header]
{removed_text}"""

        return Panel(
            content,
            title="[status.success]Clean Complete[/status.success]",
            box=ROUNDED,
            border_style="success",
            padding=(1, 2)
        )

    @staticmethod
    def create_build_info(tool_name: str, version: str, available_versions: List[str]) -> Panel:
        """Create build information panel for version selection."""
        versions_text = "\n".join([f"  [version]• {v}[/version]" for v in available_versions[:10]])
        if len(available_versions) > 10:
            versions_text += f"\n  [muted]... and {len(available_versions) - 10} more[/muted]"
            
        content = f"""[status.info]ℹ️  Version Selection[/status.info]

[header]Available versions for[/header] [tool]{tool_name}[/tool]:
{versions_text}

[status.warning]⚠️  No version specified[/status.warning]
[header]Building latest version:[/header] [version]{version}[/version]

[header]To specify a version:[/header]
[command]shelley build {tool_name}/{version}[/command]"""

        return Panel(
            content,
            title="[status.info]Version Information[/status.info]",
            box=ROUNDED,
            border_style="info",
            padding=(1, 2)
        )
    
    @staticmethod
    def create_error_panel(title: str, message: str, suggestion: str = "") -> Panel:
        """Create a styled error panel."""
        content = f"[status.error]❌ {message}[/status.error]"
        if suggestion:
            content += f"\n\n[header]Suggestion:[/header]\n[info]{suggestion}[/info]"
            
        return Panel(
            content,
            title=f"[status.error]{title}[/status.error]",
            box=ROUNDED,
            border_style="error",
            padding=(1, 2)
        )
    
    @staticmethod
    def create_warning_panel(title: str, message: str) -> Panel:
        """Create a styled warning panel."""
        return Panel(
            f"[status.warning]⚠️  {message}[/status.warning]",
            title=f"[status.warning]{title}[/status.warning]",
            box=ROUNDED,
            border_style="warning",
            padding=(1, 2)
        )
    
    @staticmethod
    def create_info_panel(title: str, message: str) -> Panel:
        """Create a styled info panel."""
        return Panel(
            f"[status.info]ℹ️  {message}[/status.info]",
            title=f"[status.info]{title}[/status.info]",
            box=ROUNDED,
            border_style="info",
            padding=(1, 2)
        )
    
    @staticmethod
    def format_command_examples() -> Table:
        """Create a table of command examples."""
        table = Table(
            title="[header]Command Examples[/header]",
            box=SIMPLE,
            border_style="border",
            header_style="table.header"
        )
        
        table.add_column("Use Case", style="muted", ratio=1)
        table.add_column("Command", style="command", ratio=2)
        
        examples = [
            ("Find a specific tool", "shelley find fastqc"),
            ("List available versions", "shelley find fastqc -v"),
            ("Search by functionality", "shelley search 'quality control'"),  
            ("Search for RNA-seq tools", "shelley search 'RNA sequencing'"),
            ("Build latest version", "shelley build samtools"),
            ("Build specific version", "shelley build samtools/1.21"),
            ("Uninstall a tool version", "shelley clean samtools:1.21"),
            ("Uninstall without confirming", "shelley clean samtools:1.21 -y"),
            ("Interactive mode", "shelley interactive")
        ]
        
        for use_case, command in examples:
            table.add_row(use_case, command)
            
        return table
    
    @staticmethod
    def create_about_panel() -> Panel:
        """Create an about panel with version and credits."""
        content = f"""[header]Shelley[/header] - [accent]BioCommons Edition[/accent]

[muted]A comprehensive bioinformatics tool finder and module builder[/muted]

[header]Features:[/header]
• [info]Find tools by name or functionality[/info]
• [info]Build Lmod modules from CVMFS containers[/info]  
• [info]Batch processing for multiple tools[/info]
• [info]Interactive command mode[/info]

[header]Powered by:[/header]
• [muted]Australian BioCommons[/muted]
• [muted]CVMFS Singularity Containers[/muted]
• [muted]Model Context Protocol (MCP)[/muted]
"""
        
        return Panel(
            content,
            title=f"[primary][bold]{title}[/bold][/primary]",
            box=ROUNDED,
            border_style="primary",
            padding=(1, 2)
        )
    
    @staticmethod
    def create_version_info() -> str:
        """Get version information for display."""
        # Single source of truth: shelley/__init__.py:__version__ (pyproject
        # derives the package version from it). Reading it directly is correct
        # whether shelley is pip-installed or run from a source checkout.
        from .. import __version__

        return f"[header]Shelley[/header] [version]{__version__}[/version]"
    
    @staticmethod
    def create_progress_bar(description: str) -> Progress:
        """Create a styled progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None, style="progress.bar", complete_style="progress.complete"),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console
        )
    
    @staticmethod
    def create_status_summary(success: int, total: int, operation: str = "operation") -> Panel:
        """Create a standardized status summary panel."""
        if success == total:
            title = f"[status.success]All {operation}s Completed Successfully![/status.success]"
            style = "success"
            icon = "🎉"
        elif success > 0:
            title = f"[status.warning]Partial Success[/status.warning]"
            style = "warning"
            icon = "⚠️"
        else:
            title = f"[status.error]All {operation}s Failed[/status.error]"
            style = "error"
            icon = "❌"
            
        content = f"{icon} [header]Successfully completed:[/header] [highlight]{success}/{total}[/highlight] {operation}s"
        
        return Panel(
            content,
            title=title,
            box=ROUNDED,
            border_style=style,
            padding=(1, 2)
        )
    
    @staticmethod
    def create_status(message: str) -> Status:
        """Create a styled status indicator."""
        return Status(
            message,
            spinner="dots",
            spinner_style="primary",
            console=console
        )


# Convenience functions for common operations
def print_banner():
    """Print the main Shelley banner."""
    console.print(ShelleyStyle.create_banner())

def print_header(title: str, subtitle: str = ""):
    """Print a styled header."""
    console.print(ShelleyStyle.create_header(title, subtitle))

def print_success(message: str):
    """Print a success message."""
    console.print(f"[status.success]✓ {message}[/status.success]")

def print_warning(message: str):
    """Print a warning message."""
    console.print(f"[status.warning]⚠️  {message}[/status.warning]")

def print_error(message: str):
    """Print an error message."""
    console.print(f"[status.error]❌ {message}[/status.error]")

def print_info(message: str):
    """Print an info message."""
    console.print(f"[status.info]ℹ️  {message}[/status.info]")

def print_rule(title: str = "", style: str = "primary"):
    """Print a styled horizontal rule."""
    console.rule(title, style=style)

def print_command(command: str):
    """Print a command in the styled format."""
    console.print(f"[command]{command}[/command]")

def print_version():
    """Print version information, plus an upgrade notice if main is ahead."""
    console.print(ShelleyStyle.create_version_info())
    print_update_notice()

def print_update_notice():
    """Print a notice if a newer shelley is available on main (silent otherwise)."""
    from .update_check import check_for_update, format_update_notice

    latest = check_for_update()
    if latest:
        console.print(Panel(
            format_update_notice(latest),
            title="[status.warning]⬆️  Update available[/status.warning]",
            box=ROUNDED,
            border_style="warning",
            padding=(1, 2),
        ))

def print_about():
    """Print about information."""
    console.print(ShelleyStyle.create_about_panel())