"""Spec parsing and resolution for `shelley build`, against a synthetic Galaxy mount."""

import pytest

from shelley import errors as sh_errors
from shelley import services as sh_services
from shelley.galaxy import catalogue as sh_catalogue

ENTRIES = [
    ("samtools", "1.22.1--h96c455f_0"),
    ("samtools", "1.21--h50ea8bc_3"),
    ("star", "2.7.11a--h0033a41_0"),
    ("star", "2.7.11b--h5ca1c30_8"),
    ("plink2", "2.00a5.12--h4ac6f70_0"),
    ("plink2", "2.00a5.12--h9948957_1"),
    ("r-seurat", "3.0.2--r36h0357c0b_1"),
]


@pytest.fixture
def catalogue(galaxy_mount, galaxy_snapshot):
    return sh_catalogue.GalaxyCatalogue(
        snapshot=galaxy_snapshot(ENTRIES), mount=galaxy_mount(ENTRIES)
    )


def recording_chooser(seen):
    def choose(err):
        seen.append(err.matches)
        return err.matches[0]

    return choose


@pytest.mark.parametrize("sep", [":", "/"])
@pytest.mark.parametrize("version", ["1.22.1--h96c455f_0", "1.22.1"])
def test_resolve_spec_variants_reach_one_tag(catalogue, sep, version):
    got = sh_services.resolve(f"samtools{sep}{version}", catalogue).tag.raw
    expect = "1.22.1--h96c455f_0"
    assert got == expect


@pytest.mark.parametrize("spec", ["star/2.7.11a", "star:2.7.11a--h0033a41_0"])
def test_not_resolve_versioned_spec_is_defaulted(catalogue, spec):
    got = sh_services.resolve(spec, catalogue).defaulted
    assert got is False


@pytest.mark.parametrize(
    "spec",
    [
        "samtools/1.22.1",  # one build of this version
        "plink2:2.00a5.12--h4ac6f70_0",  # several builds, but the full tag is given
    ],
)
def test_not_resolve_prompts_for_single_build(catalogue, spec):
    got = []
    sh_services.resolve(spec, catalogue, recording_chooser(got))
    assert got == []


@pytest.mark.parametrize(
    "spec",
    [
        "parabricks",
        "seurat",  # on CVMFS only as r-seurat
    ],
)
def test_resolve_missing_tool_raises(catalogue, spec):
    with pytest.raises(sh_errors.TagNotFound, match="not found in Galaxy CVMFS"):
        sh_services.resolve(spec, catalogue)


def test_resolve_r_seurat_spelling(catalogue):
    got = sh_services.resolve("r-seurat", catalogue).tag.raw
    expect = "3.0.2--r36h0357c0b_1"
    assert got == expect
