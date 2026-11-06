"""Tests for normalize_aliases, the canonical alias shape used by `build`."""

import pytest

from shelley.builder.guts_integration import normalize_aliases


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
