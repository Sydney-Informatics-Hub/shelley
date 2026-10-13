"""RegistryClient and LocalRegistry"""

import pytest
import yaml

from shelley.errors import NetworkUnavailable
from shelley.galaxy.registry import (
    LOCAL_TAG_VALUE,
    LocalRegistry,
    Marker,
    RegistryClient,
    merged_with_upstream,
)

URI = "quay.io/biocontainers/samtools"
UPSTREAM = {
    "docker": URI,
    "latest": {"1.21--h50ea8bc_3": "sha256:aaa"},
    "tags": {"1.21--h50ea8bc_3": "sha256:aaa", "1.10--h2e538c0_3": "sha256:bbb"},
    "maintainer": "@vsoch",
    "description": "samtools",
    "aliases": {"samtools": "/usr/local/bin/samtools"},
}


# ------------------------------------------------------------------ RegistryClient
def test_fetch_returns_the_upstream_entry():
    client = RegistryClient(fetch=lambda url: yaml.dump(UPSTREAM))
    assert client.fetch(URI)["tags"] == UPSTREAM["tags"]


def test_fetch_returns_none_when_not_upstream():
    assert RegistryClient(fetch=lambda url: None).fetch(URI) is None


def test_fetch_builds_the_raw_url():
    seen = []
    RegistryClient(fetch=lambda url: seen.append(url)).fetch(URI)
    assert seen == [
        "https://raw.githubusercontent.com/singularityhub/shpc-registry/main/"
        "quay.io/biocontainers/samtools/container.yaml"
    ]


def test_fetch_propagates_network_failure():
    def down(url):
        raise NetworkUnavailable(
            "raw.githubusercontent.com", "the request timed out after 10 s"
        )

    with pytest.raises(NetworkUnavailable):
        RegistryClient(fetch=down).fetch(URI)


# ------------------------------------------------------------------ LocalRegistry
def test_write_then_read_round_trip():
    reg = LocalRegistry()
    entry = merged_with_upstream({"tags": {"1.19--h1": LOCAL_TAG_VALUE}}, UPSTREAM)
    reg.write(
        URI, entry, Marker("1.19--h1", [{"name": "samtools", "command": "samtools"}])
    )
    assert reg.read(URI)["tags"]["1.19--h1"] == LOCAL_TAG_VALUE
    marker = reg.markers(URI)["1.19--h1"]
    assert marker.aliases == [{"name": "samtools", "command": "samtools"}]
    assert marker.in_upstream is False
    on_disk = (reg.entry_dir(URI) / "1.19--h1" / "aliases.yaml").stat().st_mode & 0o777
    assert on_disk == 0o644


def test_read_missing_entry():
    assert LocalRegistry().read(URI) is None
    assert LocalRegistry().markers(URI) == {}


def test_merge_adds_upstream_tags_and_keeps_local_ones():
    local = {
        "tags": {"1.19--h1": LOCAL_TAG_VALUE, "1.21--h50ea8bc_3": LOCAL_TAG_VALUE},
        "aliases": [],
    }
    merged = merged_with_upstream(local, UPSTREAM)
    assert merged["tags"] == {
        "1.21--h50ea8bc_3": LOCAL_TAG_VALUE,  # local wins where both have it
        "1.10--h2e538c0_3": "sha256:bbb",  # newer upstream tags no longer hidden
        "1.19--h1": LOCAL_TAG_VALUE,
    }
    assert merged["aliases"] == []  # curated aliases untouched
    assert local["tags"] == {
        "1.19--h1": LOCAL_TAG_VALUE,
        "1.21--h50ea8bc_3": LOCAL_TAG_VALUE,
    }


def test_merge_with_nothing_upstream():
    local = {"tags": {"1.19--h1": LOCAL_TAG_VALUE}}
    assert merged_with_upstream(local, None)["tags"] == {"1.19--h1": LOCAL_TAG_VALUE}


def test_legacy_entry_like_star_fusion_on_the_dev_vm():
    """An upstream-looking entry, no markers, nothing linked: a <=0.4.0 artefact."""
    reg = LocalRegistry()
    reg.write(URI, {"tags": {"1.0.0--pl5": "sha256:x"}, "maintainer": "@vsoch"})
    assert reg.is_legacy(URI, linked_tags=[])


def test_entry_with_a_marker_is_not_legacy():
    reg = LocalRegistry()
    reg.write(URI, {"tags": {"1.19--h1": LOCAL_TAG_VALUE}}, Marker("1.19--h1"))
    assert not reg.is_legacy(URI, linked_tags=[])


def test_entry_in_use_is_not_legacy():
    reg = LocalRegistry()
    reg.write(URI, {"tags": {"1.0.0--pl5": "sha256:x"}})
    assert not reg.is_legacy(URI, linked_tags=["1.0.0--pl5"])


def test_missing_entry_is_not_legacy():
    assert not LocalRegistry().is_legacy(URI, linked_tags=[])


# ------------------------------------------------------------------ live upstream
# The regression tool matrix (docs/reference/data-sources.md): which canonical tags the
# upstream shpc-registry has, and so which builds need a local entry.
REGRESSION_MATRIX = [
    ("fastqc", "0.12.1--hdfd78af_0", True),
    ("multiqc", "1.19--pyhdfd78af_0", True),
    ("salmon", "1.10.1--h7e5ed60_0", True),
    ("bcftools", "1.23.1--hb2cee57_0", True),
    ("bwa-mem2", "2.2.1--he70b90d_8", True),
    ("star", "2.7.11a--h0033a41_0", True),
    ("fastp", "0.20.0--hdbcaa40_0", False),
    ("sambamba", "0.8.1--hadffe2f_1", False),
    ("samblaster", "0.1.24--hc9558a2_3", False),
    ("samtools", "1.19--h50ea8bc_0", False),
    ("blast", "2.5.0--hc0b0e79_3", False),
    ("star-fusion", "1.0.0--pl5.22.0_0", False),
]


@pytest.mark.network
@pytest.mark.parametrize("tool, tag, in_upstream", REGRESSION_MATRIX)
def test_regression_matrix_matches_the_live_upstream_registry(tool, tag, in_upstream):
    entry = RegistryClient().fetch(f"quay.io/biocontainers/{tool}") or {}
    assert (tag in entry.get("tags", {})) is in_upstream
