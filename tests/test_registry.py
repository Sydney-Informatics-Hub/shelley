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

    def test_preserves_earlier_local_tag_when_building_a_second_local_only_version(
        self, builder, tmp_path,
    ):
        """Regression: a second locally-curated build of the same tool must not
        clobber a tag added by an earlier local-only build — only fetch a fresh
        upstream base when no local file exists yet."""
        first_version = "1.10.1--0"
        second_version = "1.8.4--0"
        registry_yaml = tmp_path / URI / "container.yaml"

        with patch("shelley.builder.cvmfs_builder.subprocess.run",
                   return_value=_curl_success({"docker": URI, "tags": {}, "aliases": []})), \
             patch("shelley.builder.cvmfs_builder.extract_aliases", return_value=[]), \
             patch.object(builder, "_compute_sha256", return_value="firstsha"):
            builder._ensure_local_registry_entry(
                "samtools", first_version, str(tmp_path / f"samtools:{first_version}"), URI,
                local_registry=str(tmp_path), in_upstream=False,
            )

        with patch("shelley.builder.cvmfs_builder.subprocess.run") as mock_run, \
             patch("shelley.builder.cvmfs_builder.extract_aliases", return_value=[]), \
             patch.object(builder, "_compute_sha256", return_value="secondsha"):
            builder._ensure_local_registry_entry(
                "samtools", second_version, str(tmp_path / f"samtools:{second_version}"), URI,
                local_registry=str(tmp_path), in_upstream=False,
            )
            curl_calls = [c for c in mock_run.call_args_list if "curl" in c.args[0]]
            assert not curl_calls, "must not re-fetch upstream when a local file already exists"

        saved = yaml.safe_load(registry_yaml.read_text())
        assert saved["tags"][first_version] == "sha256:firstsha"
        assert saved["tags"][second_version] == "sha256:secondsha"

    def test_per_version_alias_snapshots_do_not_clobber_each_other(self, builder, tmp_path):
        """Regression for the star-fusion case: config["aliases"] is one shared field,
        so a second not-upstream build overwrites it with that version's own aliases.
        Each version's own aliases.yaml snapshot must still be recoverable afterward."""
        old_version, new_version = "1.0.0--0", "1.9.1--0"
        old_aliases = [{"name": "STAR", "command": "STAR"}]
        new_aliases = [{"name": "STAR", "command": "STAR"}, {"name": "salmon", "command": "salmon"}]

        with patch("shelley.builder.cvmfs_builder.subprocess.run",
                   return_value=_curl_success({"docker": URI, "tags": {}, "aliases": []})), \
             patch("shelley.builder.cvmfs_builder.extract_aliases", return_value=old_aliases), \
             patch.object(builder, "_compute_sha256", return_value="oldsha"):
            builder._ensure_local_registry_entry(
                "samtools", old_version, str(tmp_path / f"samtools:{old_version}"), URI,
                local_registry=str(tmp_path), in_upstream=False,
            )

        with patch("shelley.builder.cvmfs_builder.subprocess.run"), \
             patch("shelley.builder.cvmfs_builder.extract_aliases", return_value=new_aliases), \
             patch.object(builder, "_compute_sha256", return_value="newsha"):
            builder._ensure_local_registry_entry(
                "samtools", new_version, str(tmp_path / f"samtools:{new_version}"), URI,
                local_registry=str(tmp_path), in_upstream=False,
            )

        # The shared page now only shows the newer build's aliases...
        saved = yaml.safe_load((tmp_path / URI / "container.yaml").read_text())
        assert saved["aliases"] == new_aliases

        # ...but each version's own snapshot is still intact and distinct.
        old_snapshot = yaml.safe_load((tmp_path / URI / old_version / "aliases.yaml").read_text())
        new_snapshot = yaml.safe_load((tmp_path / URI / new_version / "aliases.yaml").read_text())
        assert old_snapshot == {"version": old_version, "aliases": old_aliases, "in_upstream": False}
        assert new_snapshot == {"version": new_version, "aliases": new_aliases, "in_upstream": False}

    def test_creates_marker_directory_only_when_not_in_upstream(self, builder, tmp_path):
        version = "1.21--h96c455f_1"

        with patch("shelley.builder.cvmfs_builder.subprocess.run",
                   return_value=_curl_success({"docker": URI, "tags": {}, "aliases": []})), \
             patch.object(builder, "_compute_sha256", return_value="deadbeef"):
            builder._ensure_local_registry_entry(
                "samtools", version, str(tmp_path / f"samtools:{version}"), URI,
                local_registry=str(tmp_path), in_upstream=True,
            )

        assert not (tmp_path / URI / version).exists()

        with patch("shelley.builder.cvmfs_builder.subprocess.run",
                   return_value=_curl_success({"docker": URI, "tags": {}, "aliases": []})), \
             patch("shelley.builder.cvmfs_builder.extract_aliases",
                   return_value=[{"name": "samtools", "command": "samtools"}]), \
             patch.object(builder, "_compute_sha256", return_value="deadbeef"):
            builder._ensure_local_registry_entry(
                "samtools", "9.9--local", str(tmp_path / "samtools:9.9--local"), URI,
                local_registry=str(tmp_path), in_upstream=False,
            )

        marker_dir = tmp_path / URI / "9.9--local"
        assert marker_dir.is_dir()
        snapshot = yaml.safe_load((marker_dir / "aliases.yaml").read_text())
        assert snapshot == {
            "version": "9.9--local",
            "aliases": [{"name": "samtools", "command": "samtools"}],
            "in_upstream": False,
        }

    def test_creates_marker_when_interactively_edited_even_if_in_upstream(self, builder, tmp_path):
        """Regression: --interactive on a version that IS upstream must still be
        versioned/markable, or shelley clean can never find or prune it and the
        curated aliases can be silently clobbered by a later build of another
        version (config["aliases"] is one field shared across every tag)."""
        version = "1.21--h96c455f_1"

        with patch("shelley.builder.cvmfs_builder.subprocess.run",
                   return_value=_curl_success({"docker": URI, "tags": {}, "aliases": []})), \
             patch("shelley.builder.cvmfs_builder.edit_aliases_interactive",
                   return_value=[{"name": "samtools", "command": "samtools"}]), \
             patch.object(builder, "_compute_sha256", return_value="deadbeef"):
            builder._ensure_local_registry_entry(
                "samtools", version, str(tmp_path / f"samtools:{version}"), URI,
                local_registry=str(tmp_path), in_upstream=True, interactive=True,
            )

        marker_dir = tmp_path / URI / version
        assert marker_dir.is_dir(), (
            "interactive edit of an in-upstream version must still be versioned"
        )
        snapshot = yaml.safe_load((marker_dir / "aliases.yaml").read_text())
        assert snapshot["in_upstream"] is True
