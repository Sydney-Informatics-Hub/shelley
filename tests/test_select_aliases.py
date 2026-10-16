"""Tests for the interactive alias editor used by `build -i/--interactive`."""

import pytest
from textual.widgets import Button, DataTable

from shelley.builder.alias_editor import AliasEditorApp, normalize_aliases


@pytest.fixture
def input_aliases() -> list[dict]:
    return [
        {"STAR": "/usr/local/bin/STAR"},
        {
            "plassembler.py": "/usr/local/bin/plassembler.py",
            "log.py": "/usr/local/bin/log.py",
            "capnpc-c++": "/usr/local/bin/capnpc-c++",
        },
    ]


# ---------------------------------------------------------------------------
# normalize_aliases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "index, expected",
    [
        (0, [{"name": "STAR", "command": "/usr/local/bin/STAR"}]),
        (
            1,
            [
                {"name": "plassembler.py", "command": "/usr/local/bin/plassembler.py"},
                {"name": "log.py", "command": "/usr/local/bin/log.py"},
                {"name": "capnpc-c++", "command": "/usr/local/bin/capnpc-c++"},
            ],
        ),
    ],
    ids=["single-entry", "multi-entry"],
)
def test_normalize_aliases_dict_form(input_aliases, index, expected):
    result = normalize_aliases(input_aliases[index])
    assert result == expected


@pytest.mark.parametrize("empty", [None, [], {}])
def test_normalize_aliases_empty(empty):
    result = normalize_aliases(empty)
    assert result == []


# ---------------------------------------------------------------------------
# alias_editor textual App
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "index, expected_aliases, expected_rows",
    [
        (
            0,
            [{"name": "STAR", "command": "/usr/local/bin/STAR"}],
            [(" ", "STAR", "/usr/local/bin/STAR")],
        ),
        (
            1,
            [
                {"name": "plassembler.py", "command": "/usr/local/bin/plassembler.py"},
                {"name": "log.py", "command": "/usr/local/bin/log.py"},
                {"name": "capnpc-c++", "command": "/usr/local/bin/capnpc-c++"},
            ],
            [
                (" ", "plassembler.py", "/usr/local/bin/plassembler.py"),
                (" ", "log.py", "/usr/local/bin/log.py"),
                (" ", "capnpc-c++", "/usr/local/bin/capnpc-c++"),
            ],
        ),
    ],
    ids=["single-entry", "multi-entry"],
)
def test_init_app(input_aliases, index, expected_aliases, expected_rows):
    app = AliasEditorApp(input_aliases[index])

    assert app.aliases == expected_aliases
    assert app.rows == expected_rows
    assert app.edited == []


@pytest.mark.asyncio
@pytest.mark.parametrize("index, nrows", [(0, 1), (1, 3)])
async def test_nrows_on_mount(input_aliases, index, nrows):
    app = AliasEditorApp(input_aliases[index])

    async with app.run_test():
        # simulate the app starting with asyncio
        table = app.query_one(DataTable)
        buttons = app.query(Button)

        assert table.row_count == nrows
        assert len(buttons) == 2
