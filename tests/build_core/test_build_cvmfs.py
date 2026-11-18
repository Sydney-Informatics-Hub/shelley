"""Real `shelley build` runs against the Galaxy CVMFS mount (the manual regression cases).

Resolution needs only the mount. Plans and builds also need shpc, Singularity, Lmod and
GitHub (the shpc registry and shpc-guts); they skip without them. Builds go into the tmp
build roots (see tests/conftest.py).
"""

import functools
import shutil
import subprocess
from pathlib import Path

import pytest

from shelley import errors as sh_errors
from shelley import services as sh_services
from shelley.galaxy import catalogue as sh_catalogue
from shelley.galaxy import exposer as sh_exposer
from shelley.tags import Tag
from shelley.tools import lmod as sh_lmod
from shelley.tools import net as sh_net
from shelley.utils import globals as gl

pytestmark = pytest.mark.cvmfs

MOUNT = Path("/cvmfs/singularity.galaxyproject.org/all")
LMOD_INIT = Path("/usr/share/lmod/lmod/init/bash")
REGISTRY_README = (
    "https://raw.githubusercontent.com/singularityhub/shpc-registry/main/README.md"
)


@pytest.fixture
def catalogue():
    return sh_catalogue.GalaxyCatalogue(mount=MOUNT)


@pytest.fixture
def real_env():
    """Skip unless shpc, Singularity, Lmod and GitHub are all available."""
    if not LMOD_INIT.exists():
        pytest.skip("Lmod not installed")
    sh_lmod.Lmod().load_build_modules()
    if not (shutil.which("shpc") or Path("/opt/shpc/bin/shpc").exists()):
        pytest.skip("shpc not installed")
    if shutil.which("singularity") is None:
        pytest.skip("singularity not on PATH")
    if not sh_net.diagnose(REGISTRY_README).ok:
        pytest.skip("GitHub not reachable")


@functools.cache
def planned_aliases(tool, tag):
    """Alias names a real plan picks (plans write nothing, so caching is safe)."""
    sif = MOUNT / f"{tool}:{tag}"
    plan = sh_exposer.ShpcExposer().plan(tool, Tag(tag), sif)
    return {a["name"] for a in plan.aliases}


def build(tool, tag):
    sif = MOUNT / f"{tool}:{tag}"
    exposer = sh_exposer.ShpcExposer()
    exposer.apply(exposer.plan(tool, Tag(tag), sif))


def run_in_module(tool, tag, command):
    """Load the built module and run ``command``; returns stdout and stderr together."""
    script = (
        f"source {LMOD_INIT} && module use {gl.lmod_modules()} "
        f"&& module load singularity && module load {tool}/{tag} && {command}"
    )
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    return out.stdout + out.stderr


# ------------------------------------------------------------------ resolution
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
        ("bcftools", "1.24--h487d631_1"),  # moves when the snapshot is refreshed
    ],
)
def test_resolve_bare_name_is_latest(catalogue, spec, expect):
    got = sh_services.resolve(spec, catalogue).tag.raw
    assert got == expect


@pytest.mark.parametrize("spec", ["plink2/2.00a5.12", "bwa-mem2/2.2.1"])
def test_resolve_multi_build_raises(catalogue, spec):
    with pytest.raises(sh_errors.AmbiguousTag):
        sh_services.resolve(spec, catalogue)


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


# ------------------------------------------------------------------ plans
@pytest.mark.parametrize(
    ("spec", "in_cvmfs", "in_registry", "newly_created"),
    [
        ("fastqc:0.12.1--hdfd78af_0", True, True, False),
        ("multiqc:1.19--pyhdfd78af_0", True, True, False),
        ("salmon:1.10.1--h7e5ed60_0", True, True, False),
        ("bcftools:1.23.1--hb2cee57_0", True, True, False),
        ("bwa-mem2:2.2.1--he70b90d_8", True, True, False),
        ("fastp:0.20.0--hdbcaa40_0", True, False, True),
        ("sambamba:0.8.1--hadffe2f_1", True, False, True),
        ("samblaster:0.1.24--hc9558a2_3", True, False, True),
        ("samtools:1.19--h50ea8bc_0", True, False, True),  # registry has only 0.1.19
        ("blast:2.5.0--hc0b0e79_3", True, False, True),
        ("star:2.7.11a--h0033a41_0", True, True, False),
        ("star-fusion:1.0.0--pl5.22.0_0", True, False, True),  # registry has ≥1.9.1
    ],
)
def test_plan_writes_local_entry_only_on_registry_miss(
    real_env, catalogue, spec, in_cvmfs, in_registry, newly_created
):
    item = sh_services.resolve(spec, catalogue)
    plan = sh_exposer.ShpcExposer().plan(item.tool, item.tag, item.sif)
    got = plan.local_entry is not None
    assert got is newly_created


@pytest.mark.parametrize("name", ["bcftools", "bgzip", "tabix", "htsfile"])
def test_plan_registry_hit_aliases_bcftools(real_env, name):
    got = planned_aliases("bcftools", "1.23.1--hb2cee57_0")
    assert name in got


@pytest.mark.parametrize("name", ["vcf-merge", "vcf-stats", "vcf-subset", "vcf-isec"])
def test_plan_guts_aliases_vcftools(real_env, name):
    got = planned_aliases("vcftools", "0.1.12b--pl5262h2e03b76_2")
    assert name in got


@pytest.mark.parametrize("name", ["blastn", "blastp"])
def test_plan_guts_aliases_blast(real_env, name):
    got = planned_aliases("blast", "2.5.0--hc0b0e79_3")
    assert name in got


# ------------------------------------------------------------------ builds
@pytest.mark.parametrize(
    ("tool", "tag", "command", "expect"),
    [
        ("star", "2.7.11a--h0033a41_0", "STAR --version", "2.7.11a"),  # issue #9
        ("bcftools", "1.6--1", "bcftools --version", "bcftools 1.6"),  # guts build
    ],
)
def test_build_alias_runs_through_wrapper(real_env, tool, tag, command, expect):
    build(tool, tag)
    got = run_in_module(tool, tag, command)
    assert expect in got
