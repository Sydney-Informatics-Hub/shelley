"""Tests for shelley/commands/interactive.py — interactive REPL loop."""

from unittest.mock import MagicMock, call, patch

import pytest

from shelley.commands.interactive import interactive_mode

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MODULE = "shelley.commands.interactive"


def _run(inputs: list, *, side_effect=None):
    """Run interactive_mode() with canned console.input responses.

    Pass side_effect to raise an exception instead of (or after) returning
    values, e.g. side_effect=KeyboardInterrupt.
    """
    if side_effect is not None:
        input_mock = MagicMock(side_effect=side_effect)
    else:
        input_mock = MagicMock(side_effect=inputs)

    with patch(f"{_MODULE}.console") as mock_console, \
         patch(f"{_MODULE}.print_banner"), \
         patch(f"{_MODULE}.print_rule"), \
         patch(f"{_MODULE}.print_info") as mock_info, \
         patch(f"{_MODULE}.print_success") as mock_success, \
         patch(f"{_MODULE}.print_warning") as mock_warning, \
         patch(f"{_MODULE}.find_tool_sync") as mock_find, \
         patch(f"{_MODULE}.search_tools") as mock_search, \
         patch(f"{_MODULE}.build_module") as mock_build, \
         patch(f"{_MODULE}.clean_module") as mock_clean:

        mock_console.input = input_mock

        interactive_mode()

        return {
            "console": mock_console,
            "find": mock_find,
            "search": mock_search,
            "build": mock_build,
            "clean": mock_clean,
            "warning": mock_warning,
            "success": mock_success,
            "info": mock_info,
        }


# ---------------------------------------------------------------------------
# Exit conditions
# ---------------------------------------------------------------------------

def test_exit():
    mocks = _run(["exit"])
    mocks["success"].assert_called_once()


def test_quit():
    mocks = _run(["quit"])
    mocks["success"].assert_called_once()


def test_q():
    mocks = _run(["q"])
    mocks["success"].assert_called_once()


def test_keyboard_interrupt_exits_cleanly():
    mocks = _run([], side_effect=KeyboardInterrupt)
    mocks["info"].assert_called_once()
    mocks["success"].assert_not_called()


def test_eof_exits_cleanly():
    mocks = _run([], side_effect=EOFError)
    mocks["info"].assert_called_once()
    mocks["success"].assert_not_called()


# ---------------------------------------------------------------------------
# Empty / whitespace input
# ---------------------------------------------------------------------------

def test_empty_input_skipped():
    """Blank lines are ignored — no command dispatched."""
    mocks = _run(["", "exit"])
    mocks["find"].assert_not_called()
    mocks["search"].assert_not_called()
    mocks["build"].assert_not_called()
    mocks["warning"].assert_not_called()


# ---------------------------------------------------------------------------
# help
# ---------------------------------------------------------------------------

def test_help_shows_table():
    """help command calls console.print without raising."""
    mocks = _run(["help", "exit"])
    assert mocks["console"].print.called


# ---------------------------------------------------------------------------
# find
# ---------------------------------------------------------------------------

def test_find_dispatches():
    mocks = _run(["find samtools", "exit"])
    mocks["find"].assert_called_once_with("samtools", verbose=False)


def test_find_verbose_flag_dispatches():
    mocks = _run(["find samtools -v", "exit"])
    mocks["find"].assert_called_once_with("samtools", verbose=True)


def test_find_verbose_long_flag_dispatches():
    mocks = _run(["find --verbose samtools", "exit"])
    mocks["find"].assert_called_once_with("samtools", verbose=True)


def test_find_double_verbose_flag_dispatches():
    mocks = _run(["find samtools -vv", "exit"])
    mocks["find"].assert_called_once_with("samtools", verbose=True)


def test_find_stacked_verbose_flags_dispatch():
    mocks = _run(["find samtools -v -v", "exit"])
    mocks["find"].assert_called_once_with("samtools", verbose=True)


def test_find_missing_arg_warns():
    mocks = _run(["find", "exit"])
    mocks["find"].assert_not_called()
    mocks["warning"].assert_called()


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

def test_search_dispatches():
    mocks = _run(["search alignment", "exit"])
    mocks["search"].assert_called_once_with("alignment")


def test_search_multi_word():
    mocks = _run(["search quality control", "exit"])
    mocks["search"].assert_called_once_with("quality control")


def test_search_missing_arg_warns():
    mocks = _run(["search", "exit"])
    mocks["search"].assert_not_called()
    mocks["warning"].assert_called()


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def test_build_dispatches():
    mocks = _run(["build samtools", "exit"])
    mocks["build"].assert_called_once_with("samtools", interactive=False)


def test_build_interactive_flag():
    mocks = _run(["build samtools -i", "exit"])
    mocks["build"].assert_called_once_with("samtools", interactive=True)


def test_build_missing_arg_warns():
    mocks = _run(["build", "exit"])
    mocks["build"].assert_not_called()
    mocks["warning"].assert_called()


# ---------------------------------------------------------------------------
# clean
# ---------------------------------------------------------------------------

def test_clean_dispatches():
    mocks = _run(["clean samtools:1.21", "exit"])
    mocks["clean"].assert_called_once_with("samtools:1.21", force=False)


def test_clean_force_flag_dispatches():
    mocks = _run(["clean samtools:1.21 -y", "exit"])
    mocks["clean"].assert_called_once_with("samtools:1.21", force=True)


def test_clean_missing_arg_warns():
    mocks = _run(["clean", "exit"])
    mocks["clean"].assert_not_called()
    mocks["warning"].assert_called()


# ---------------------------------------------------------------------------
# unknown command
# ---------------------------------------------------------------------------

def test_unknown_command_warns():
    mocks = _run(["blah", "exit"])
    mocks["warning"].assert_called()
    mocks["find"].assert_not_called()


# ---------------------------------------------------------------------------
# Markup safety — regression for MarkupError on [/ver] in build command string
# ---------------------------------------------------------------------------

def test_command_table_renders_without_markup_error():
    """_COMMANDS must not contain unescaped Rich markup (e.g. [/ver] as a closing tag)."""
    from shelley.commands.interactive import _COMMANDS
    from shelley.utils.style import ShelleyStyle, console

    table = ShelleyStyle.create_help_table(_COMMANDS)
    with console.capture():
        console.print(table)  # raises rich.errors.MarkupError if any cell is invalid
