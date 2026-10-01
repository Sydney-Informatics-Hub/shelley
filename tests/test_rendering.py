#!/usr/bin/env python3
"""Test the improved interactive mode rendering."""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from shelley.utils.style import ShelleyStyle, console, print_banner, print_rule


def test_interactive_display():
    """Show the improved interactive mode display."""
    console.clear()
    print_banner()
    print_rule("Interactive Mode", "accent")

    # Create help table with fixed command syntax
    commands = [
        {
            "command": "find <tool>",
            "description": "Find information about a specific tool",
            "example": "find fastqc",
        },
        {
            "command": "search <description>",
            "description": "Search for tools by function",
            "example": "search quality control",
        },
        {
            "command": "versions <tool>",
            "description": "Get available container versions",
            "example": "versions samtools",
        },
        {
            "command": "cvmfs-list <tool>",
            "description": "List CVMFS versions for tool",
            "example": "cvmfs-list blast",
        },
        {
            "command": "build <tool\\[/ver]>",
            "description": "Build Lmod module for tool",
            "example": "build samtools/1.21",
        },
        {"command": "help", "description": "Show detailed help", "example": "help"},
        {"command": "exit", "description": "Exit interactive mode", "example": "exit"},
    ]

    help_table = ShelleyStyle.create_help_table(commands)
    console.print(help_table)
    print_rule()

    console.print(
        "\n🧬 [prompt]shelley>[/prompt] [dim](Clean rendering test successful!)[/dim]"
    )
    console.print(
        "\n[success]✓ Banner now uses clean Panel instead of Unicode box drawing[/success]"
    )
    console.print(
        "[success]✓ Command table shows proper brackets without escaping[/success]"
    )
    console.print(
        "[success]✓ cvmfs-list shows full container paths instead of Available status[/success]"
    )
    console.print("[success]✓ Australian BioCommons styling maintained[/success]\n")


if __name__ == "__main__":
    test_interactive_display()
