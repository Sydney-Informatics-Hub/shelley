"""Registry hit vs miss for `shelley build`: where aliases come from, and when a local entry is written."""

import pytest

from shelley import services as sh_services
from shelley.galaxy import catalogue as sh_catalogue
from shelley.galaxy import exposer as sh_exposer
from shelley.galaxy import registry as sh_registry
from shelley.tags import Tag

from . import fakes

REGISTRY = {
    "quay.io/biocontainers/bcftools": {
        "tags": {"1.23.1--hb2cee57_0": "sha256:a"},
        "aliases": {
            "bcftools": "/usr/local/bin/bcftools",
            "bgzip": "/usr/local/bin/bgzip",
            "tabix": "/usr/local/bin/tabix",
        },
    },
    "quay.io/biocontainers/vcftools": {
        "tags": {"0.1.17--pl5321h077b44d_0": "sha256:b"},
        "aliases": {"vcftools": "/usr/local/bin/vcftools"},
    },
    "quay.io/biocontainers/star": {
        "tags": {"2.7.11a--h0033a41_0": "sha256:c"},
        "aliases": {"STAR": "/usr/local/bin/STAR"},
    },
}

# What the stubbed guts diff finds in each SIF.
GUTS = {
    "bcftools": [{"name": "bcftools", "command": "bcftools"}],
    "vcftools": [
        {"name": "vcf-merge", "command": "vcf-merge"},
        {"name": "vcftools", "command": "vcftools"},
    ],
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


def make_exposer(entries, calls):
    def discover(sif, keep=None):
        calls.append(keep)
        return list(GUTS.get(keep, []))

    return sh_exposer.ShpcExposer(
        registry=fakes.FakeRegistry(entries), shpc=fakes.FakeShpc(), discover=discover
    )


# ------------------------------------------------------------------ alias source
@pytest.mark.parametrize(
    ("tool", "tag", "expect"),
    [
        (
            "bcftools",
            "1.23.1--hb2cee57_0",
            [
                {"name": "bcftools", "command": "/usr/local/bin/bcftools"},
                {"name": "bgzip", "command": "/usr/local/bin/bgzip"},
                {"name": "tabix", "command": "/usr/local/bin/tabix"},
            ],
        ),
        (
            "vcftools",
            "0.1.17--pl5321h077b44d_0",
            [{"name": "vcftools", "command": "/usr/local/bin/vcftools"}],
        ),
        (
            "star",
            "2.7.11a--h0033a41_0",
            [{"name": "STAR", "command": "/usr/local/bin/STAR"}],
        ),
    ],
)
def test_plan_registry_hit_uses_registry_aliases(sif, tool, tag, expect):
    got = make_exposer(REGISTRY, []).plan(tool, Tag(tag), sif).aliases
    assert got == expect


@pytest.mark.parametrize(
    ("tool", "tag", "expect"),
    [
        ("bcftools", "1.6--1", [{"name": "bcftools", "command": "bcftools"}]),
        (
            "vcftools",
            "0.1.12b--pl5262h2e03b76_2",
            [
                {"name": "vcf-merge", "command": "vcf-merge"},
                {"name": "vcftools", "command": "vcftools"},
            ],
        ),
        (
            "blast",  # tool not in the registry at all
            "2.5.0--hc0b0e79_3",
            [
                {"name": "blastn", "command": "blastn"},
                {"name": "blastp", "command": "blastp"},
            ],
        ),
    ],
)
def test_plan_registry_miss_uses_guts_aliases(sif, tool, tag, expect):
    got = make_exposer(REGISTRY, []).plan(tool, Tag(tag), sif).aliases
    assert got == expect


def test_plan_registry_miss_runs_guts(sif):
    got = []
    make_exposer(REGISTRY, got).plan("bcftools", Tag("1.6--1"), sif)
    assert got == ["bcftools"]


def test_not_plan_registry_hit_runs_guts(sif):
    got = []
    make_exposer(REGISTRY, got).plan("bcftools", Tag("1.23.1--hb2cee57_0"), sif)
    assert got == []


def test_apply_registry_miss_writes_guts_aliases(sif):
    exposer = make_exposer(REGISTRY, [])
    exposer.apply(exposer.plan("blast", Tag("2.5.0--hc0b0e79_3"), sif))
    got = sh_registry.LocalRegistry().read("quay.io/biocontainers/blast")["aliases"]
    expect = [
        {"name": "blastn", "command": "blastn"},
        {"name": "blastp", "command": "blastp"},
    ]
    assert got == expect


# ------------------------------------------------------------------ CVMFS table
@pytest.mark.parametrize(
    ("spec", "in_cvmfs", "in_registry", "newly_created"),
    [
        ("fastqc:0.12.1--hdfd78af_0", True, True, False),
        ("multiqc:1.19--pyhdfd78af_0", True, True, False),
        ("salmon:1.10.1--h7e5ed60_0", True, True, False),
        ("bcftools", True, True, False),  # latest, pinned to 1.23.1 by the mount
        ("bwa-mem2:2.2.1--he70b90d_8", True, True, False),
        ("bwa-mem2:2.2.1--hd03093a_5", True, False, True),  # same version, other build
        ("fastp:0.20.0--hdbcaa40_0", True, False, True),
        ("sambamba:0.8.1--hadffe2f_1", True, False, True),
        ("samblaster:0.1.24--hc9558a2_3", True, False, True),
        ("samtools:1.19--h50ea8bc_0", True, False, True),
        ("blast:2.5.0--hc0b0e79_3", True, False, True),
        ("star:2.7.11a--h0033a41_0", True, True, False),
        ("star-fusion:1.0.0--pl5.22.0_0", True, False, True),
    ],
)
def test_plan_writes_local_entry_only_on_registry_miss(
    galaxy_mount, galaxy_snapshot, sif, spec, in_cvmfs, in_registry, newly_created
):
    """`in_registry` False: the registry lists the tool, but only another tag."""
    tool, version = sh_services.parse_spec(spec)
    entries = (
        [(tool, version)]
        if version
        else [(tool, "1.6--1"), (tool, "1.23.1--hb2cee57_0")]
    )
    mount = galaxy_mount(entries if in_cvmfs else [])
    catalogue = sh_catalogue.GalaxyCatalogue(
        snapshot=galaxy_snapshot(entries), mount=mount
    )
    item = sh_services.resolve(spec, catalogue)
    tag = item.tag.raw if in_registry else "0.0.1--h0"
    registry = {
        f"quay.io/biocontainers/{tool}": {
            "tags": {tag: "sha256:x"},
            "aliases": {tool: f"/usr/local/bin/{tool}"},
        }
    }
    plan = make_exposer(registry, []).plan(item.tool, item.tag, item.sif)
    got = plan.local_entry is not None
    assert got is newly_created
