#!/usr/bin/env python3
"""
What remains of the 0.4.0 module builder: ``uninstall_module``, used by the old
``shelley clean`` until find, search and clean move to the build core (batch 4.5).

Building is done by ``services.build`` (``GalaxyCatalogue`` and ``ShpcExposer``).
"""

import logging
import shutil
import subprocess
from pathlib import Path

import yaml

from shelley.utils import globals as gl
from shelley.utils.globals import CVMFS_GALAXY_SINGULARITY_PATH
from shelley.utils.perms import share_file

log = logging.getLogger(__name__)


def _shpc_bin() -> str:
    """Resolve the shpc executable at call time.

    Resolved lazily rather than at import so it picks up an shpc that only appears on
    PATH after the build path loads the shpc module (see load_build_modules). Falls
    back to the known install location when shpc is not on PATH.
    """
    return shutil.which("shpc") or "/opt/shpc/bin/shpc"


def _shpc_cmd(*args: str) -> list[str]:
    """Build an shpc argv with shelley's shared settings file pinned.

    Without this, shpc falls back to its own defaults — which put every install base
    under $HOME, so a build under `sudo -E` lands in the invoking user's home where no
    other user can read it. See shelley.builder.shpc_settings.

    The flag is omitted when the file does not exist, because shpc hard-exits on a
    missing --settings-file. That keeps read-only callers working on a machine that has
    never been built on; the build path calls ensure_shared_shpc_settings() first, so it
    always gets the flag.
    """
    settings = gl.shpc_settings_file()
    prefix = [_shpc_bin()]
    if settings.is_file():
        prefix += ["--settings-file", str(settings)]
    return prefix + list(args)


class CVMFSModuleBuilder:
    """Removes modules built by shelley (the old ``clean`` path)."""

    def __init__(
        self,
        cvmfs_singularity: str = CVMFS_GALAXY_SINGULARITY_PATH,
        lmod_modules: str | None = None,
    ):
        # Kept side-effect-free on purpose: loading the shpc/singularity Lmod modules
        # is done by the caller (shelley.utils.modules.load_build_modules).
        self.cvmfs_singularity = cvmfs_singularity
        # Resolved here rather than as a default argument so the SHELLEY_LMOD_MODULES_PATH
        # override applies (a default would bind at import time).
        self.lmod_modules = (
            lmod_modules if lmod_modules is not None else str(gl.lmod_modules())
        )
        self.cvmfs_singularity_path = Path(self.cvmfs_singularity)
        self.lmod_modules_path = Path(self.lmod_modules)

    def _run_shpc_uninstall(self, uri_tag: str) -> tuple[int, str]:
        """Run `shpc uninstall --force <uri_tag>`. Returns (returncode, combined output)."""
        result = subprocess.run(
            _shpc_cmd("uninstall", "--force", uri_tag),
            capture_output=True,
            text=True,
        )
        return result.returncode, result.stdout + result.stderr

    def uninstall_module(self, tool_name: str, version: str) -> dict:
        """
        Uninstall a specific tool@version: the inverse of `shelley build`.

        Runs `shpc uninstall --force` for the shpc-managed module/wrapper/container
        artifacts, and removes the Lmod modulefile symlink shelley creates directly
        (shpc has no knowledge of it) — pruning its parent tool directory too, if
        that was the last version installed for this tool.

        local_registry()/<uri>/container.yaml is not exclusively "owned" by one
        installed version the way the modulefile symlink is: 0.4.0 also wrote it as
        a cache of the *entire* upstream shpc-registry. While other versions of this
        tool are still installed, its tags dict is only safe to prune when the build
        left a registry_dir/<version>/ marker directory
        (holding that version's own aliases.yaml snapshot) *and* that snapshot's
        in_upstream flag is False, proving the tag was a genuine local addition
        (absent upstream) rather than an interactive edit of a tag that's still
        legitimately upstream — in that case the one tag is removed and the whole
        marker directory (aliases snapshot included) is deleted with it. When the
        marker's snapshot says in_upstream was True, or the marker predates that
        field (missing snapshot, or no in_upstream key at all), the tag entry is
        left alone: only the marker directory itself is removed. Without a marker
        at all, container.yaml is left completely untouched.

        Once this was the *last* installed version of the tool (tool_dir under
        lmod_modules() ends up empty — the same check that decides whether to prune
        it), the whole registry_dir is deleted outright instead: container.yaml,
        however many tags it still has cached, and any marker directories. Nothing
        shelley manages references that URI anymore at that point, so the marker/
        tag bookkeeping above is moot — any upstream tags lost this way are simply
        re-fetched fresh the next time the tool is looked up or built.

        Does not raise if `shpc uninstall` fails (e.g. shpc's own tracking already
        lost the entry) — shelley's own state is independent and still gets cleaned
        up. Returns a report describing exactly what was removed, for the caller to
        render:

            {
                "uri_tag": str,
                "shpc_removed": bool,
                "shpc_output": str,
                "modulefile_removed": bool,
                "registry_tag_removed": bool,
                "registry_entry_deleted": bool,
            }
        """
        uri = f"quay.io/biocontainers/{tool_name}"
        uri_tag = f"{uri}:{version}"

        returncode, output = self._run_shpc_uninstall(uri_tag)
        shpc_removed = returncode == 0
        if not shpc_removed:
            log.warning(
                "shpc uninstall reported rc=%s for %s: %s",
                returncode,
                uri_tag,
                output.strip(),
            )

        tool_dir = self.lmod_modules_path / tool_name
        dest = tool_dir / f"{version}.lua"
        modulefile_removed = False
        if dest.is_symlink() or dest.exists():
            dest.unlink()
            modulefile_removed = True

        # "No versions left installed" must be detected even when this call's own
        # modulefile was already missing (e.g. a previous partial clean) — so this
        # is attempted whenever tool_dir exists, not only when dest did. A
        # nonexistent tool_dir is deliberately NOT treated as "fully removed": by
        # the time uninstall_module runs, clean_module has already resolved this
        # version via _resolve_installed_version, which requires tool_dir to exist
        # in the first place, so its absence here would only mean inconsistent
        # state, not a confident "nothing left installed" signal.
        tool_fully_removed = False
        if tool_dir.is_dir():
            try:
                tool_dir.rmdir()  # only succeeds if truly empty
                tool_fully_removed = True
            except OSError:
                pass  # other versions of this tool are still installed

        registry_tag_removed = False
        registry_entry_deleted = False
        registry_dir = gl.local_registry() / uri

        if tool_fully_removed:
            # Delete the whole entry rather than running the per-tag logic below
            # just to immediately discard its result — see docstring above.
            if registry_dir.is_dir():
                shutil.rmtree(registry_dir)
                registry_entry_deleted = True
        else:
            marker_dir = registry_dir / version
            if marker_dir.is_dir():
                snapshot_path = marker_dir / "aliases.yaml"
                marker_in_upstream = False
                if snapshot_path.is_file():
                    with open(snapshot_path) as f:
                        marker_in_upstream = bool(
                            (yaml.safe_load(f) or {}).get("in_upstream", False)
                        )

                if not marker_in_upstream:
                    registry_yaml = registry_dir / "container.yaml"
                    if registry_yaml.is_file():
                        with open(registry_yaml) as f:
                            config = yaml.safe_load(f) or {}
                        tags = config.get("tags", {}) or {}
                        if version in tags:
                            del tags[version]
                            config["tags"] = tags
                            with open(registry_yaml, "w") as f:
                                yaml.dump(
                                    config, f, default_flow_style=False, sort_keys=False
                                )
                            share_file(registry_yaml)
                            registry_tag_removed = True
                shutil.rmtree(marker_dir, ignore_errors=True)

        return {
            "uri_tag": uri_tag,
            "shpc_removed": shpc_removed,
            "shpc_output": output,
            "modulefile_removed": modulefile_removed,
            "registry_tag_removed": registry_tag_removed,
            "registry_entry_deleted": registry_entry_deleted,
        }
