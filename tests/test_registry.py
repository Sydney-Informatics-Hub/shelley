#!/usr/bin/env python3
"""Unit tests for _load_registry_config, get_registry_tags, and _ensure_local_registry_entry."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
import yaml
import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from shelley.builder.cvmfs_builder import (
    _load_registry_config,
    get_registry_tags,
    CVMFSModuleBuilder,
)

URI = "quay.io/biocontainers/samtools"

REMOTE_CONFIG = {
    "docker": URI,
    "tags": {
        "1.21--h96c455f_1": "sha256:abc123",
        "1.20--h50ea8bc_0": "sha256:def456",
    },
    "aliases": [],
}

def _curl_success(config: dict):
    """Return a fake subprocess.run result that looks like a successful curl."""
    m = MagicMock()
    m.returncode = 0
    m.stdout = yaml.dump(config)
    return m


def _curl_failure():
    m = MagicMock()
    m.returncode = 1
    m.stdout = ""
    return m


@pytest.fixture
def builder(tmp_path):
    return CVMFSModuleBuilder(lmod_modules=str(tmp_path / "modulefiles"))


# ---------------------------------------------------------------------------
# _load_registry_config
# ---------------------------------------------------------------------------

class TestLoadRegistryConfig:
    def test_loads_local_file_without_curl(self, tmp_path):
        local_yaml = tmp_path / URI / "container.yaml"
        local_yaml.parent.mkdir(parents=True)
        local_yaml.write_text(yaml.dump(REMOTE_CONFIG))

        with patch("shelley.builder.cvmfs_builder.subprocess.run") as mock_run:
            config = _load_registry_config(URI, local_yaml)

        mock_run.assert_not_called()
        assert config["tags"] == REMOTE_CONFIG["tags"]

    def test_fetches_remote_when_no_local_file(self, tmp_path):
        local_yaml = tmp_path / URI / "container.yaml"

        with patch("shelley.builder.cvmfs_builder.subprocess.run",
                   return_value=_curl_success(REMOTE_CONFIG)):
            config = _load_registry_config(URI, local_yaml)

        assert config["tags"] == REMOTE_CONFIG["tags"]

    def test_saves_remote_config_to_disk(self, tmp_path):
        local_yaml = tmp_path / URI / "container.yaml"

        with patch("shelley.builder.cvmfs_builder.subprocess.run",
                   return_value=_curl_success(REMOTE_CONFIG)):
            _load_registry_config(URI, local_yaml)

        assert local_yaml.exists()
        saved = yaml.safe_load(local_yaml.read_text())
        assert saved["tags"] == REMOTE_CONFIG["tags"]

    def test_returns_empty_dict_when_remote_fails(self, tmp_path):
        local_yaml = tmp_path / URI / "container.yaml"

        with patch("shelley.builder.cvmfs_builder.subprocess.run",
                   return_value=_curl_failure()):
            config = _load_registry_config(URI, local_yaml)

        assert config == {}

    def test_returns_empty_dict_when_curl_raises(self, tmp_path):
        local_yaml = tmp_path / URI / "container.yaml"

        with patch("shelley.builder.cvmfs_builder.subprocess.run",
                   side_effect=OSError("curl not found")):
            config = _load_registry_config(URI, local_yaml)

        assert config == {}

    def test_returns_config_even_when_disk_write_forbidden(self, tmp_path):
        local_yaml = tmp_path / URI / "container.yaml"

        with patch("shelley.builder.cvmfs_builder.subprocess.run",
                   return_value=_curl_success(REMOTE_CONFIG)), \
             patch("builtins.open", side_effect=[PermissionError, mock_open()()]):
            # PermissionError on write should be swallowed; config still returned
            config = _load_registry_config(URI, local_yaml)

        assert config["tags"] == REMOTE_CONFIG["tags"]

    def test_force_upstream_ignores_local_file(self, tmp_path):
        """force_upstream=True bypasses the local cache and fetches from GitHub."""
        local_yaml = tmp_path / URI / "container.yaml"
        local_yaml.parent.mkdir(parents=True)
        stale_config = {"docker": URI, "tags": {"stale--tag_0": "sha256:000"}, "aliases": []}
        local_yaml.write_text(yaml.dump(stale_config))

        upstream_config = {**REMOTE_CONFIG}
        with patch("shelley.builder.cvmfs_builder.subprocess.run",
                   return_value=_curl_success(upstream_config)) as mock_run:
            config = _load_registry_config(URI, local_yaml, force_upstream=True)

        mock_run.assert_called_once()
        assert "stale--tag_0" not in config.get("tags", {})
        assert "1.21--h96c455f_1" in config["tags"]

    def test_force_upstream_does_not_write_to_disk(self, tmp_path):
        """force_upstream=True does not overwrite the local cache file."""
        local_yaml = tmp_path / URI / "container.yaml"

        with patch("shelley.builder.cvmfs_builder.subprocess.run",
                   return_value=_curl_success(REMOTE_CONFIG)):
            _load_registry_config(URI, local_yaml, force_upstream=True)

        assert not local_yaml.exists()


# ---------------------------------------------------------------------------
# get_registry_tags
# ---------------------------------------------------------------------------

class TestGetRegistryTags:
    def test_returns_tag_keys_from_local_file(self, tmp_path):
        local_yaml = tmp_path / "quay.io" / "biocontainers" / "samtools" / "container.yaml"
        local_yaml.parent.mkdir(parents=True)
        local_yaml.write_text(yaml.dump(REMOTE_CONFIG))

        tags = get_registry_tags("samtools", local_registry=str(tmp_path))

        assert tags == set(REMOTE_CONFIG["tags"].keys())

    def test_returns_tag_keys_from_remote(self, tmp_path):
        with patch("shelley.builder.cvmfs_builder.subprocess.run",
                   return_value=_curl_success(REMOTE_CONFIG)):
            tags = get_registry_tags("samtools", local_registry=str(tmp_path))

        assert "1.21--h96c455f_1" in tags
        assert "1.20--h50ea8bc_0" in tags

    def test_returns_empty_set_when_unreachable(self, tmp_path):
        with patch("shelley.builder.cvmfs_builder.subprocess.run",
                   return_value=_curl_failure()):
            tags = get_registry_tags("samtools", local_registry=str(tmp_path))

        assert tags == set()

    def test_upstream_only_skips_local_cache(self, tmp_path):
        """upstream_only=True ignores a locally-cached file and fetches from GitHub."""
        local_yaml = tmp_path / "quay.io" / "biocontainers" / "samtools" / "container.yaml"
        local_yaml.parent.mkdir(parents=True)
        stale_config = {"docker": URI, "tags": {"stale--tag_0": "sha256:000"}, "aliases": []}
        local_yaml.write_text(yaml.dump(stale_config))

        upstream_config = {**REMOTE_CONFIG}
        with patch("shelley.builder.cvmfs_builder.subprocess.run",
                   return_value=_curl_success(upstream_config)):
            tags = get_registry_tags("samtools", local_registry=str(tmp_path),
                                     upstream_only=True)

        assert "stale--tag_0" not in tags
        assert "1.21--h96c455f_1" in tags


# ---------------------------------------------------------------------------
# _ensure_local_registry_entry
# ---------------------------------------------------------------------------

class TestEnsureLocalRegistryEntry:
    def test_adds_tag_and_sha256_when_version_missing(self, builder, tmp_path):
        registry_yaml = tmp_path / URI / "container.yaml"
        version = "1.21--h96c455f_1"
        container_path = str(tmp_path / f"samtools:{version}")

        with patch("shelley.builder.cvmfs_builder.subprocess.run",
                   return_value=_curl_success({"docker": URI, "tags": {}, "aliases": []})), \
             patch.object(builder, "_compute_sha256", return_value="deadbeef"):
            builder._ensure_local_registry_entry(
                "samtools", version, container_path, URI,
                local_registry=str(tmp_path),
            )

        saved = yaml.safe_load(registry_yaml.read_text())
        assert version in saved["tags"]
        assert saved["tags"][version] == "sha256:deadbeef"

    def test_creates_minimal_config_when_remote_unavailable(self, builder, tmp_path):
        version = "1.99--newbuild_0"
        container_path = str(tmp_path / f"samtools:{version}")
        registry_yaml = tmp_path / URI / "container.yaml"

        with patch("shelley.builder.cvmfs_builder.subprocess.run",
                   return_value=_curl_failure()), \
             patch.object(builder, "_compute_sha256", return_value="cafebabe"):
            builder._ensure_local_registry_entry(
                "samtools", version, container_path, URI,
                local_registry=str(tmp_path),
            )

        saved = yaml.safe_load(registry_yaml.read_text())
        assert saved["docker"] == URI
        assert version in saved["tags"]
        assert saved["tags"][version] == "sha256:cafebabe"
        # shpc's schema requires these; without them `shpc install` crashes with
        # "'latest' is a required property" (see GitHub issue #22, the `last` tool).
        assert saved["latest"] == {version: "sha256:cafebabe"}
        assert saved["maintainer"]
        assert saved["description"]

    def test_heals_preexisting_incomplete_local_entry(self, builder, tmp_path):
        """Regression test: a container.yaml left behind by an earlier failed
        build (missing shpc's required latest/maintainer/description fields,
        as happened for `last` in GitHub issue #22) must be repaired on the
        next build, not just avoided for a brand-new entry.

        curl -f leaves an existing --output file untouched on an HTTP error
        (verified), so a stale incomplete local entry survives the upstream
        fetch attempt and is reloaded as-is unless the code heals it.
        """
        version = "1654--h5814d7d_0"
        container_path = str(tmp_path / f"last:{version}")
        registry_dir = tmp_path / "quay.io/biocontainers/last"
        registry_dir.mkdir(parents=True)
        registry_yaml = registry_dir / "container.yaml"
        registry_yaml.write_text(yaml.dump({
            "docker": "quay.io/biocontainers/last",
            "tags": {version: "sha256:186f57055d03ff51e8fb32fedb4a388d76aeea2691c56aac051de78671453fa6"},
            "filter": [version],
            "aliases": [{"name": "lastal", "command": "lastal"}],
        }))

        with patch("shelley.builder.cvmfs_builder.subprocess.run",
                   return_value=_curl_failure()), \
             patch.object(builder, "_compute_sha256",
                          return_value="186f57055d03ff51e8fb32fedb4a388d76aeea2691c56aac051de78671453fa6"):
            builder._ensure_local_registry_entry(
                "last", version, container_path, "quay.io/biocontainers/last",
                local_registry=str(tmp_path),
            )

        saved = yaml.safe_load(registry_yaml.read_text())
        assert saved["latest"]
        assert saved["maintainer"]
        assert saved["description"]
