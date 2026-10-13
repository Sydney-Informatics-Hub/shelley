"""Alias discovery from a SIF (``guts_integration.extract_aliases``) and the shpc it needs.

Kept from the 0.4.0 builder tests: the build core discovers aliases with the same method
(``galaxy/aliases.py``).
"""

import shutil
import subprocess
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Environment pre-flight
# ---------------------------------------------------------------------------


@pytest.mark.cvmfs
def test_shpc_is_executable():
    """Fallback path /opt/shpc/bin/shpc is present and executable even without module load."""
    result = subprocess.run(
        ["/opt/shpc/bin/shpc", "--version"], capture_output=True, text=True
    )
    assert result.returncode == 0, f"shpc --version failed: {result.stderr}"


@pytest.mark.cvmfs
def test_shpc_on_path():
    """shpc must be on PATH for all build operations. Fix: module load shpc"""
    assert shutil.which("shpc") is not None, (
        "shpc not found on PATH, run 'module load shpc' before using shelley build "
        "or running the CVMFS integration tests."
    )


def test_extract_aliases_returns_empty_on_failure():
    """extract_aliases degrades gracefully when the sparse clone or diff fails."""
    from shelley.builder.guts_integration import extract_aliases

    with patch(
        "shelley.builder.guts_integration._sparse_clone_base_manifests",
        side_effect=subprocess.CalledProcessError(1, "git"),
    ):
        result = extract_aliases("/cvmfs/foo/bar:1.0")
    assert result == []


@contextmanager
def _scripted_guts_diff(diff_data):
    """Patch guts so extract_aliases sees ``diff_data`` as the diff result.

    Stubs the clone and the supplementary-db merge too, so nothing touches the
    network or the filesystem.
    """
    gen = MagicMock()
    gen.diff.return_value = {"docker.io/x:1.0": {"diff": diff_data}}
    with (
        patch(
            "shelley.builder.guts_integration._sparse_clone_base_manifests",
            return_value="/tmp/does-not-matter",
        ),
        patch("shelley.builder.guts_integration._merge_supplementary_db"),
        patch("shelley.builder.guts_integration.shutil.rmtree"),
        patch("shelley.builder.guts_integration.ManifestGenerator", return_value=gen),
    ):
        yield


def test_extract_aliases_ignores_paths_outside_bin_dirs():
    """Only executables in a bin/sbin directory become aliases."""
    from shelley.builder.guts_integration import extract_aliases

    with _scripted_guts_diff(
        {"unique_paths": ["/usr/local/bin/samtools", "/opt/data/reference.fa"]}
    ):
        assert extract_aliases("/cvmfs/x") == [
            {"name": "samtools", "command": "samtools"}
        ]


def test_extract_aliases_dedupes_the_same_executable_in_two_path_dirs():
    """A binary present in two PATH dirs yields one alias, not two identical ones."""
    from shelley.builder.guts_integration import extract_aliases

    with _scripted_guts_diff({"unique_paths": ["/usr/bin/bwa", "/usr/local/bin/bwa"]}):
        assert extract_aliases("/cvmfs/x") == [{"name": "bwa", "command": "bwa"}]


def test_extract_aliases_drops_shadowed_paths_by_default():
    """Base binaries guts shadowed must not come back as aliases."""
    from shelley.builder.guts_integration import extract_aliases

    with _scripted_guts_diff(
        {
            "unique_paths": ["/usr/local/bin/samtools"],
            "shadowed_paths": ["/sbin/devmem", "/usr/bin/tput"],
        }
    ):
        assert extract_aliases("/cvmfs/x") == [
            {"name": "samtools", "command": "samtools"}
        ]


def test_extract_aliases_keep_readmits_a_tool_named_like_a_base_binary():
    """A tool really called `sort` is shadowed by coreutils; keep= rescues it."""
    from shelley.builder.guts_integration import extract_aliases

    diff = {
        "unique_paths": [],
        "shadowed_paths": ["/usr/local/bin/sort", "/sbin/devmem"],
    }
    with _scripted_guts_diff(diff):
        assert extract_aliases("/cvmfs/x", keep="sort") == [
            {"name": "sort", "command": "sort"}
        ]


def test_extract_aliases_tolerates_a_diff_without_shadowed_paths():
    """Guards against an older container-guts that predates the new key."""
    from shelley.builder.guts_integration import extract_aliases

    with _scripted_guts_diff({"unique_paths": ["/usr/local/bin/fastp"]}):
        assert extract_aliases("/cvmfs/x", keep="fastp") == [
            {"name": "fastp", "command": "fastp"}
        ]


# ---------------------------------------------------------------------------
# CVMFS regression: star-fusion 1.0.0 alias correctness
# ---------------------------------------------------------------------------


@pytest.mark.cvmfs
def test_extract_aliases_star_fusion_1_0_0():
    """star-fusion 1.0.0 must alias STAR but never salmon.

    Regression: salmon appeared because aliases were inherited from a newer
    build (which bundles salmon) rather than extracted from the 1.0.0 SIF.
    Requires Singularity on PATH (in addition to CVMFS).
    """
    if shutil.which("singularity") is None:
        pytest.skip("singularity not on PATH")
    from shelley.builder.guts_integration import extract_aliases

    sif = "/cvmfs/singularity.galaxyproject.org/all/star-fusion:1.0.0--pl5.22.0_0"
    aliases = extract_aliases(sif)
    alias_names = {a["name"] for a in aliases}
    assert "STAR" in alias_names, f"STAR should be aliased; got: {sorted(alias_names)}"
    assert "salmon" not in alias_names, (
        f"salmon must NOT be aliased; got: {sorted(alias_names)}"
    )
