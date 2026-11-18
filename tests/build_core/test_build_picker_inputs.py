"""What `shelley build -i` hands the alias picker, and what the picker starts with."""

import pytest
from textual.widgets import Button, DataTable

from shelley.builder import alias_editor as sh_alias_editor
from shelley.galaxy import exposer as sh_exposer
from shelley.tags import Tag
from shelley.utils.style import TICK_OFF

from . import fakes

REGISTRY = {
    "quay.io/biocontainers/bcftools": {
        "tags": {"1.23.1--hb2cee57_0": "sha256:a"},
        "aliases": {
            "bcftools": "/usr/local/bin/bcftools",
            "tabix": "/usr/local/bin/tabix",
        },
    },
}
GUTS = [
    {"name": "bcftools", "command": "bcftools"},
    {"name": "kinit", "command": "kinit"},  # guts noise reaches the picker unticked
]


@pytest.fixture
def sif(tmp_path):
    path = tmp_path / "bcftools.sif"
    path.touch()
    return path


def make_exposer():
    return sh_exposer.ShpcExposer(
        registry=fakes.FakeRegistry(REGISTRY),
        shpc=fakes.FakeShpc(),
        discover=lambda sif, keep=None: list(GUTS),
    )


def recording_curate(seen):
    def curate(aliases):
        seen.append(aliases)
        return aliases

    return curate


# ------------------------------------------------------------------ picker input
@pytest.mark.parametrize(
    ("tag", "expect"),
    [
        (
            "1.23.1--hb2cee57_0",  # registry hit
            [
                {"name": "bcftools", "command": "/usr/local/bin/bcftools"},
                {"name": "tabix", "command": "/usr/local/bin/tabix"},
            ],
        ),
        (
            "1.6--1",  # registry miss → guts
            [
                {"name": "bcftools", "command": "bcftools"},
                {"name": "kinit", "command": "kinit"},
            ],
        ),
    ],
)
def test_plan_curate_receives_aliases(sif, tag, expect):
    got = []
    make_exposer().plan("bcftools", Tag(tag), sif, curate=recording_curate(got))
    assert got == [expect]


@pytest.mark.parametrize("tag", ["1.23.1--hb2cee57_0", "1.6--1"])
def test_plan_uses_curated_aliases(sif, tag):
    expect = [{"name": "bcf", "command": "bcftools"}]
    plan = make_exposer().plan("bcftools", Tag(tag), sif, curate=lambda a: expect)
    got = plan.aliases
    assert got == expect


# ------------------------------------------------------------------ picker start state
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("aliases", "expect"),
    [
        (REGISTRY["quay.io/biocontainers/bcftools"]["aliases"], [TICK_OFF, TICK_OFF]),
        (GUTS, [TICK_OFF, TICK_OFF]),
    ],
)
async def test_alias_editor_starts_unticked(aliases, expect):
    app = sh_alias_editor.AliasEditorApp(aliases, tool="bcftools")
    async with app.run_test():
        got = [str(t) for t in app.query_one(DataTable).get_column(app.tick)]
    assert got == expect


@pytest.mark.asyncio
async def test_not_alias_editor_confirm_enabled_on_start():
    app = sh_alias_editor.AliasEditorApp(GUTS, tool="bcftools")
    async with app.run_test():
        got = app.query_one("#confirm", Button).disabled
    assert got is True
