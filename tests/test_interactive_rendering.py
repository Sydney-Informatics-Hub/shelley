#!/usr/bin/env python3
"""Test script to verify interactive mode rendering improvements."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from shelley.utils.style import ShelleyStyle, console, print_banner, print_rule


def test_interactive_rendering():
    """Test the interactive mode rendering without MCP server."""
    console.clear()
    print_banner()
    print_rule("Interactive Mode", "accent")

    # Create help table
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
            "command": "list [limit]",
            "description": "List available tools",
            "example": "list 20",
        },
        {
            "command": r"build <tool\[/ver]>",
            "description": "Build Lmod module for tool",
            "example": "build samtools/1.21",
        },
        {
            "command": "cvmfs-list <tool>",
            "description": "List CVMFS versions",
            "example": "cvmfs-list blast",
        },
        {"command": "help", "description": "Show detailed help", "example": "help"},
        {"command": "exit", "description": "Exit interactive mode", "example": "exit"},
    ]

    help_table = ShelleyStyle.create_help_table(commands)
    console.print(help_table)
    print_rule()

    console.print("\n[prompt]shelley>[/prompt] ")


if __name__ == "__main__":
    test_interactive_rendering()
