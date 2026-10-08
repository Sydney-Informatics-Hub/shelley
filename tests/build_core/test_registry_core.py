"""RegistryClient and LocalRegistry (ADR 0004, ADR 0006)."""

import pytest
import yaml

from shelley.builder.cvmfs_builder import CVMFSModuleBuilder
from shelley.errors import NetworkUnavailable
from shelley.galaxy.registry import (
    LOCAL_TAG_VALUE,
    LocalRegistry,
    Marker,
    RegistryClient,
    merged_with_upstream,
)
from shelley.utils.globals import lmod_modules

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


def test_old_clean_still_understands_entries_written_here(monkeypatch):
    """Parallel change: 0.4.0's uninstall_module must work on the new format."""
    reg = LocalRegistry()
    entry = merged_with_upstream({"tags": {"1.19--h1": LOCAL_TAG_VALUE}}, UPSTREAM)
    reg.write(URI, entry, Marker("1.19--h1", in_upstream=False))
    tool_dir = lmod_modules() / "samtools"
    tool_dir.mkdir(parents=True)
    for tag in ("1.19--h1", "1.21--h50ea8bc_3"):  # another version stays installed
        (tool_dir / f"{tag}.lua").symlink_to("/nonexistent/module.lua")
    monkeypatch.setattr(
        CVMFSModuleBuilder, "_run_shpc_uninstall", lambda self, uri_tag: (0, "")
    )

    report = CVMFSModuleBuilder().uninstall_module("samtools", "1.19--h1")

    assert report["registry_tag_removed"] is True
    assert "1.19--h1" not in reg.read(URI)["tags"]
    assert "1.21--h50ea8bc_3" in reg.read(URI)["tags"]
    assert "1.19--h1" not in reg.markers(URI)
