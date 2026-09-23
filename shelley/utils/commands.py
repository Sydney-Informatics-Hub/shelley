"""Shared command metadata for the CLI usage and interactive help tables.

Single source of truth so the two help tables can't drift. ``example`` is the
bare invocation (no ``shelley`` prefix); the CLI prepends it, the interactive
REPL uses it as-is.
"""

# Commands available in both the CLI and the interactive REPL.
CORE_COMMANDS = [
    {"command": "find <tool> [-v]",
     "description": "Find a tool; -v adds CVMFS container paths",
     "example": "find fastqc"},
    {"command": "search <description>",
     "description": "Search for tools by function",
     "example": "search quality control"},
    {"command": r"build <tool\[/version]> [-i]",
     "description": "Build Lmod module for tool; -i/--interactive to curate aliases",
     "example": "build samtools/1.21"},
    {"command": r"clean <tool>:<version> [-y]",
     "description": "Uninstall a specific tool version; -y skips the confirmation prompt",
     "example": "clean samtools:1.21"},
]
