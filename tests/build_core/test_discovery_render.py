"""What ``shelley find`` and ``shelley clean`` print (ported from the 0.4.0 command tests)."""

import re

from shelley import services
from shelley.client import discovery
from shelley.results import FindResult, ToolMeta, VersionRow
from shelley.tags import Tag
from shelley.utils.style import console

ARRIBA = ToolMeta(id="arriba", name="Arriba")


def capture(render, *args) -> str:
    with console.capture() as cap:
        render(*args)
    return cap.get()


def found(versions, latest):
    return FindResult(
        query="arriba",
        tool="arriba",
        meta=ARRIBA,
        versions=tuple(VersionRow(v, "2024-01-01", False) for v in versions),
        latest=latest,
    )


def test_install_panel_shows_latest_and_specific_commands():
    result = found(["2.4.0", "2.3.0"], Tag("2.4.0--h1"))
    out = capture(discovery._render_find, result, False)
    assert "To install the latest version of Arriba" in out
    assert re.search(r"shelley build arriba\s+│", out)  # bare: the latest
    assert "To install a specific version of Arriba" in out
    assert "shelley build arriba/2.4.0" in out


def test_install_panel_asks_for_a_tag_when_there_is_no_latest():
    """mulled containers have no version order, so there is no default to build."""
    result = found(["mulled-v2-abc"], None)
    out = capture(discovery._render_find, result, False)
    assert "To install the latest version" not in out
    assert "shelley build arriba:mulled-v2-abc" in out


def test_no_install_panel_for_a_tool_without_containers():
    result = FindResult(query="arriba", tool=None, meta=ARRIBA)
    out = capture(discovery._render_find, result, False)
    assert "shelley build" not in out


def test_not_installed_panel_lists_installed_versions():
    error = services.NotInstalled("samtools", "1.99", ["1.21--h50ea8bc_3"])
    out = capture(discovery._render_not_installed, error)
    assert "1.21--h50ea8bc_3" in out
    assert "shelley clean samtools:1.21--h50ea8bc_3" in out
