"""Tests for the interactive alias editor used by `build -i/--interactive`."""

from unittest.mock import MagicMock, patch

import pytest

from shelley.builder.guts_integration import (
    edit_aliases_interactive,
    normalize_aliases,
    select_aliases,
)


def _scripted_questionary(*, checkbox=None, confirm=None, text=None):
    """A questionary stub whose checkbox/confirm/text .ask() pop scripted answers.

    Each keyword is a list consumed in call order. ``Choice`` is passed through
    to the real questionary so the code under test can still build choices.
    """
    from shelley.builder.guts_integration import questionary as real_q

    stub = MagicMock()
    stub.Choice = real_q.Choice
    queues = {
        "checkbox": list(checkbox or []),
        "confirm": list(confirm or []),
        "text": list(text or []),
    }

    def make(kind):
        def _call(*_a, **_k):
            resp = MagicMock()
            resp.ask.return_value = queues[kind].pop(0)
            return resp

        return _call

    stub.checkbox.side_effect = make("checkbox")
    stub.confirm.side_effect = make("confirm")
    stub.text.side_effect = make("text")
    return stub


# ---------------------------------------------------------------------------
# normalize_aliases
# ---------------------------------------------------------------------------


def test_normalize_aliases_dict_form():
    assert normalize_aliases({"STAR": "/usr/local/bin/STAR"}) == [
        {"name": "STAR", "command": "/usr/local/bin/STAR"}
    ]


def test_normalize_aliases_list_form():
    aliases = [{"name": "bwa", "command": "bwa"}]
    assert normalize_aliases(aliases) == aliases


def test_normalize_aliases_empty():
    assert normalize_aliases(None) == []
    assert normalize_aliases([]) == []
    assert normalize_aliases({}) == []


# ---------------------------------------------------------------------------
# select_aliases (the deselect step)
# ---------------------------------------------------------------------------


def test_select_aliases_empty_returns_empty_without_prompt():
    with patch("shelley.builder.guts_integration.questionary") as mock_q:
        assert select_aliases([]) == []
        mock_q.checkbox.assert_not_called()


def test_select_aliases_returns_chosen_subset():
    aliases = [
        {"name": "vcftools", "command": "vcftools"},
        {"name": "telnet", "command": "telnet"},
    ]
    chosen = [aliases[0]]
    with patch(
        "shelley.builder.guts_integration.questionary",
        _scripted_questionary(checkbox=[chosen]),
    ):
        assert select_aliases(aliases) == chosen


def test_select_aliases_cancel_raises():
    aliases = [{"name": "vcftools", "command": "vcftools"}]
    with patch(
        "shelley.builder.guts_integration.questionary",
        _scripted_questionary(checkbox=[None]),
    ):
        with pytest.raises(ValueError):
            select_aliases(aliases)


def test_select_aliases_choices_start_unchecked():
    """Regression: choices must NOT be pre-checked.

    With ``use_search_filter``, the filter only hides rows — it never unchecks
    them — so pre-checking everything returns the whole list regardless of what
    the user filtered to. Starting unchecked is what makes "filter → check the
    one you want → enter" return just that one.
    """
    aliases = [
        {"name": "plassembler.py", "command": "/usr/local/bin/plassembler.py"},
        {"name": "log.py", "command": "/usr/local/bin/log.py"},
    ]
    stub = _scripted_questionary(checkbox=[[aliases[0]]])
    with patch("shelley.builder.guts_integration.questionary", stub):
        select_aliases(aliases)

    passed_choices = stub.checkbox.call_args.kwargs["choices"]
    assert [c.checked for c in passed_choices] == [False, False]


# ---------------------------------------------------------------------------
# edit_aliases_interactive (deselect -> rename -> add)
# ---------------------------------------------------------------------------


def test_edit_deselect_only():
    """Deselect one; decline rename and add."""
    aliases = [
        {"name": "vcftools", "command": "vcftools"},
        {"name": "devmem", "command": "devmem"},
    ]
    kept = [aliases[0]]
    stub = _scripted_questionary(
        checkbox=[kept],  # deselect step keeps vcftools
        confirm=[False, False],  # rename? no; add? no
    )
    with patch("shelley.builder.guts_integration.questionary", stub):
        assert edit_aliases_interactive(aliases) == kept


def test_edit_rename_name_only_preserves_command():
    """Rename STAR -> star; command is untouched. Flow order: deselect, add, rename."""
    aliases = [{"name": "STAR", "command": "/usr/local/bin/STAR"}]
    stub = _scripted_questionary(
        checkbox=[aliases, aliases],  # deselect keeps all; rename picks STAR
        confirm=[False, True],  # add? no; rename? yes
        text=["star"],  # new name
    )
    with patch("shelley.builder.guts_integration.questionary", stub):
        result = edit_aliases_interactive(aliases)
    assert result == [{"name": "star", "command": "/usr/local/bin/STAR"}]


def test_edit_add_new_alias():
    """Empty source (e.g. bandage): no confirm gate, drop straight into the add loop."""
    stub = _scripted_questionary(
        confirm=[False],  # only "Add another?" (no "Add new aliases?" gate)
        text=["bandage", "Bandage"],  # name, command
    )
    with patch("shelley.builder.guts_integration.questionary", stub):
        result = edit_aliases_interactive([])
    assert result == [{"name": "bandage", "command": "Bandage"}]
    # the empty case tells the user before prompting
    stub.print.assert_called_once()


def test_edit_add_command_defaults_to_name():
    """Blank command falls back to the alias name."""
    stub = _scripted_questionary(
        confirm=[False],  # only "Add another?"
        text=["bandage", ""],  # name, blank command -> defaults to name
    )
    with patch("shelley.builder.guts_integration.questionary", stub):
        result = edit_aliases_interactive([])
    assert result == [{"name": "bandage", "command": "bandage"}]


def test_edit_plassembler_flow_keeps_only_selected_with_real_binary():
    """The plassembler failing case: from a large upstream alias set, keep only
    plassembler.py and rename it to plassembler.

    The result must be a single alias whose command is the real in-container
    binary (``/usr/local/bin/plassembler.py``) — not the bare module name
    ``plassembler`` (which does not exist in the container and made the built
    module fail to run), and none of the other candidates leak through.
    """
    source = {
        "plassembler.py": "/usr/local/bin/plassembler.py",
        "log.py": "/usr/local/bin/log.py",
        "capnpc-c++": "/usr/local/bin/capnpc-c++",
    }
    plassembler = {"name": "plassembler.py", "command": "/usr/local/bin/plassembler.py"}
    stub = _scripted_questionary(
        checkbox=[
            [plassembler],
            [plassembler],
        ],  # select keeps only plassembler.py; rename picks it
        confirm=[False, True],  # add? no; rename? yes
        text=["plassembler"],  # new invocation name
    )
    with patch("shelley.builder.guts_integration.questionary", stub):
        result = edit_aliases_interactive(source)
    assert result == [
        {"name": "plassembler", "command": "/usr/local/bin/plassembler.py"}
    ]


def test_edit_cancel_raises():
    """Cancelling the deselect step aborts the whole edit."""
    aliases = [{"name": "bwa", "command": "bwa"}]
    stub = _scripted_questionary(checkbox=[None])
    with patch("shelley.builder.guts_integration.questionary", stub):
        with pytest.raises(ValueError):
            edit_aliases_interactive(aliases)
