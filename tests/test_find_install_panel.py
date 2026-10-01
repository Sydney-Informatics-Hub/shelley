"""Tests for the find command's Install panel rendering."""

from shelley.commands.find import _render_find_tool
from shelley.utils.style import console


def _capture(payload) -> str:
    with console.capture() as cap:
        _render_find_tool(payload)
    return cap.get()


def _payload(versions):
    return {
        "query": "arriba",
        "found": True,
        "suggestions": [],
        "tool": {
            "id": "arriba",
            "name": "Arriba",
            "description": "",
            "homepage": "",
            "operations": [],
            "inputs": [],
            "outputs": [],
        },
        "containers": {
            "available": True,
            "all_versions": [{"version": v, "date": "2024-01-01"} for v in versions],
            "total_versions": len(versions),
            "builds": None,
        },
    }


def test_install_panel_shows_latest_and_specific_commands():
    out = _capture(_payload(["2.4.0", "2.3.0"]))
    assert "To install the latest version of Arriba" in out
    assert "shelley build arriba" in out
    assert "To install a specific version of Arriba" in out
    assert "shelley build arriba/2.4.0" in out


def test_install_panel_omits_specific_command_when_no_versions():
    out = _capture(_payload([]))
    assert "To install the latest version of Arriba" in out
    assert "To install a specific version" not in out
