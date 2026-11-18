"""Registry hit vs miss for `shelley build`: when guts runs, and what a miss writes."""

import pytest

from shelley.galaxy import exposer as sh_exposer
from shelley.galaxy import registry as sh_registry
from shelley.tags import Tag

from . import fakes

REGISTRY = {
    "quay.io/biocontainers/bcftools": {
        "tags": {"1.23.1--hb2cee57_0": "sha256:a"},
        "aliases": {"bcftools": "/usr/local/bin/bcftools"},
    },
}

# What the stubbed guts diff finds in each SIF.
GUTS = {
    "bcftools": [{"name": "bcftools", "command": "bcftools"}],
    "blast": [
        {"name": "blastn", "command": "blastn"},
        {"name": "blastp", "command": "blastp"},
    ],
}


@pytest.fixture
def sif(tmp_path):
    path = tmp_path / "tool.sif"
    path.touch()
    return path


def make_exposer(calls):
    def discover(sif, keep=None):
        calls.append(keep)
        return list(GUTS.get(keep, []))

    return sh_exposer.ShpcExposer(
        registry=fakes.FakeRegistry(REGISTRY), shpc=fakes.FakeShpc(), discover=discover
    )


def test_not_plan_registry_hit_runs_guts(sif):
    got = []
    make_exposer(got).plan("bcftools", Tag("1.23.1--hb2cee57_0"), sif)
    assert got == []


def test_apply_registry_miss_writes_guts_aliases(sif):
    exposer = make_exposer([])
    exposer.apply(exposer.plan("blast", Tag("2.5.0--hc0b0e79_3"), sif))
    got = sh_registry.LocalRegistry().read("quay.io/biocontainers/blast")["aliases"]
    expect = [
        {"name": "blastn", "command": "blastn"},
        {"name": "blastp", "command": "blastp"},
    ]
    assert got == expect
