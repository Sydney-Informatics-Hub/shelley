"""What `shelley build -i` hands the alias picker, and what it builds from the answer."""

import pytest

from shelley.galaxy import exposer as sh_exposer
from shelley.tags import Tag

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


def test_plan_uses_curated_aliases_on_registry_miss(sif):
    expect = [{"name": "bcf", "command": "bcftools"}]
    plan = make_exposer().plan("bcftools", Tag("1.6--1"), sif, curate=lambda a: expect)
    got = plan.aliases
    assert got == expect
