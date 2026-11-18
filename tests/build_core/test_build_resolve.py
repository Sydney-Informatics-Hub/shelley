"""Spec parsing and resolution for `shelley build`, against a synthetic Galaxy mount."""

import pytest

from shelley import errors as sh_errors
from shelley import privilege as sh_privilege
from shelley import services as sh_services
from shelley.client import build as sh_build
from shelley.galaxy import catalogue as sh_catalogue

ENTRIES = [
    ("samtools", "1.22.1--h96c455f_0"),
    ("samtools", "1.21--h50ea8bc_3"),
    ("star", "2.7.11a--h0033a41_0"),
    ("star", "2.7.11b--h5ca1c30_8"),
    ("bcftools", "1.6--1"),
    ("bcftools", "1.23.1--hb2cee57_0"),
    ("plink2", "2.00a5.12--h4ac6f70_0"),
    ("plink2", "2.00a5.12--h9948957_1"),
    ("bwa-mem2", "2.2.1--hd03093a_5"),
    ("bwa-mem2", "2.2.1--he70b90d_7"),
    ("bwa-mem2", "2.2.1--he70b90d_8"),
    ("r-seurat", "3.0.2--r36h0357c0b_1"),
]


@pytest.fixture
def catalogue(galaxy_mount, galaxy_snapshot):
    return sh_catalogue.GalaxyCatalogue(
        snapshot=galaxy_snapshot(ENTRIES), mount=galaxy_mount(ENTRIES)
    )


@pytest.fixture
def sudo(catalogue, monkeypatch):
    """`build.run` sees the synthetic catalogue; re-execs are recorded, not run."""
    calls = []
    monkeypatch.setattr(sh_build, "GalaxyCatalogue", lambda: catalogue)
    monkeypatch.setattr(sh_privilege, "needs_root", lambda: True)
    monkeypatch.setattr(sh_privilege, "reexec", lambda args: calls.append(args) or 0)
    return calls


def recording_chooser(seen):
    def choose(err):
        seen.append(err.matches)
        return err.matches[0]

    return choose


# ------------------------------------------------------------------ spec variants
@pytest.mark.parametrize("sep", [":", "/"])
@pytest.mark.parametrize("version", ["1.22.1--h96c455f_0", "1.22.1"])
def test_resolve_spec_variants_reach_one_tag(catalogue, sep, version):
    got = sh_services.resolve(f"samtools{sep}{version}", catalogue).tag.raw
    expect = "1.22.1--h96c455f_0"
    assert got == expect


@pytest.mark.parametrize(
    ("spec", "expect"),
    [
        ("star", "2.7.11b--h5ca1c30_8"),
        ("bcftools", "1.23.1--hb2cee57_0"),
    ],
)
def test_resolve_bare_name_is_latest(catalogue, spec, expect):
    got = sh_services.resolve(spec, catalogue).tag.raw
    assert got == expect


def test_resolve_bare_name_is_defaulted(catalogue):
    got = sh_services.resolve("star", catalogue).defaulted
    assert got is True


@pytest.mark.parametrize("spec", ["star/2.7.11a", "star:2.7.11a--h0033a41_0"])
def test_not_resolve_versioned_spec_is_defaulted(catalogue, spec):
    got = sh_services.resolve(spec, catalogue).defaulted
    assert got is False


# ------------------------------------------------------------------ multi-build prompt
@pytest.mark.parametrize(
    ("spec", "expect"),
    [
        ("plink2/2.00a5.12", [["2.00a5.12--h9948957_1", "2.00a5.12--h4ac6f70_0"]]),
        (
            "bwa-mem2/2.2.1",
            [["2.2.1--he70b90d_8", "2.2.1--he70b90d_7", "2.2.1--hd03093a_5"]],
        ),
    ],
)
def test_resolve_prompts_for_multi_build(catalogue, spec, expect):
    got = []
    sh_services.resolve(spec, catalogue, recording_chooser(got))
    assert got == expect


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


def test_resolve_multi_build_without_chooser_raises(catalogue):
    with pytest.raises(sh_errors.AmbiguousTag):
        sh_services.resolve("plink2/2.00a5.12", catalogue)


# ------------------------------------------------------------------ missing from CVMFS
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


@pytest.mark.parametrize("spec", ["parabricks", "seurat"])
def test_build_run_missing_tool_exits_1(sudo, spec):
    got = sh_build.run([spec])
    assert got == 1


@pytest.mark.parametrize("spec", ["parabricks", "seurat"])
def test_build_run_missing_tool_never_elevates(sudo, spec):
    sh_build.run([spec])
    assert sudo == []
