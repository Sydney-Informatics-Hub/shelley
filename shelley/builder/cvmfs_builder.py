#!/usr/bin/env python3
"""
CVMFS Module Builder

Builds Lmod module files for tools available in CVMFS.
"""

import hashlib
import logging
import shutil
import subprocess
import yaml
from pathlib import Path
from typing import List, Optional, Tuple
import re
import questionary
from datetime import datetime
from shelley.utils import globals as gl
from shelley.utils.globals import CVMFS_GALAXY_SINGULARITY_PATH
from shelley.utils import console, ShelleyStyle
from shelley.utils.perms import (
    ensure_shared_dir, ensure_traversable, harden_tree, share_file,
)
from shelley.builder.shpc_settings import ensure_shared_shpc_settings
from shelley.builder.guts_integration import (
    edit_aliases_interactive, extract_aliases, normalize_aliases,
)

log = logging.getLogger(__name__)

# Where shpc lays out modules, wrappers and containers beneath each base: the
# registry URI followed by the version tag.
_SHPC_URI_PREFIX = ("quay.io", "biocontainers")

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

def _load_registry_config(uri: str, local_yaml: Path, force_upstream: bool = False) -> dict:
    """Return the shpc registry config dict for uri.

    Loads from local_yaml if it exists (unless force_upstream=True).  Otherwise
    fetches the upstream shpc-registry container.yaml and saves it to local_yaml
    (best-effort; silently skips the write on OSError so read-only callers still get a
    result; also skipped when force_upstream=True to avoid polluting the local cache
    with a forced read).  Returns an empty dict if neither source is reachable.
    """
    if not force_upstream and local_yaml.exists():
        with open(local_yaml) as f:
            return yaml.safe_load(f) or {}

    remote_url = (
        f"https://raw.githubusercontent.com/singularityhub/shpc-registry/main/{uri}/container.yaml"
    )
    try:
        result = subprocess.run(
            ["curl", "-fsSL", "--max-time", "10", remote_url],
            capture_output=True, text=True,
        )
    except Exception:
        return {}

    if result.returncode != 0:
        return {}

    config = yaml.safe_load(result.stdout) or {}

    if not force_upstream:
        # Best-effort: this also runs on the read path (get_registry_tags) as an
        # unprivileged user, where the registry is root-owned and both the write and
        # the chmod are expected to fail.
        try:
            ensure_shared_dir(local_yaml.parent)
            with open(local_yaml, "w") as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            share_file(local_yaml)
        except OSError:
            pass

    return config


def get_registry_tags(tool_name: str, local_registry: str | None = None,
                      upstream_only: bool = False) -> set:
    """Return the set of version tags known to shpc for tool_name.

    When upstream_only=True, always fetches fresh from the upstream shpc-registry,
    ignoring any locally-cached container.yaml.  Use this to check whether a
    specific version exists in the upstream registry before deciding to create a
    local entry.

    ``local_registry`` defaults to the shared local registry, resolved at call time so
    the SHELLEY_LOCAL_REGISTRY override applies (a module-level default would bind at
    import and ignore it).
    """
    uri = f"quay.io/biocontainers/{tool_name}"
    local_yaml = Path(local_registry or gl.local_registry()) / uri / "container.yaml"
    config = _load_registry_config(uri, local_yaml, force_upstream=upstream_only)
    return set(config.get("tags", {}).keys())


class CVMFSModuleBuilder:
    """Builds Lmod modules for CVMFS tools."""
    
    def __init__(
        self,
        cvmfs_singularity: str = CVMFS_GALAXY_SINGULARITY_PATH,
        lmod_modules: str | None = None,
    ):
        # Kept side-effect-free on purpose: read-only callers (e.g.
        # list_cvmfs_versions, find) construct this builder without needing shpc or
        # singularity. Loading the shpc/singularity Lmod modules is done separately on
        # the build path (shelley.utils.modules.load_build_modules) so shelley stays
        # uvx-able for read-only commands on non-BioShell systems.
        self.cvmfs_singularity = cvmfs_singularity
        # Resolved here rather than as a default argument so the SHELLEY_LMOD_MODULES_PATH
        # override applies (a default would bind at import time).
        self.lmod_modules = lmod_modules if lmod_modules is not None else str(gl.lmod_modules())
        self.cvmfs_singularity_path = Path(self.cvmfs_singularity)
        self.lmod_modules_path = Path(self.lmod_modules)

    def _is_cvmfs_available(self) -> bool:
        """Check if CVMFS is mounted and accessible."""
        return self.cvmfs_singularity_path.exists() and self.cvmfs_singularity_path.is_dir()
    
    def _parse_version(self, version_str: str) -> Tuple[int, ...]:
        """
        Parse version string for semantic sorting.
        
        Args:
            version_str: Version string like "1.21" or "1.22--hdfd78af_0"
            
        Returns:
            Tuple of version numbers for sorting
        """
        # Extract the main version number before any build suffix
        version_part = version_str.split("--")[0]
        
        # Split on dots and convert to integers where possible
        parts = []
        for part in version_part.split("."):
            # Try to extract numbers from the part
            numbers = re.findall(r'\d+', part)
            if numbers:
                parts.extend(int(num) for num in numbers)
            else:
                # For non-numeric parts, use ASCII value of first char
                parts.append(ord(part[0]) if part else 0)
        
        return tuple(parts)
    
    def _sort_versions(self, versions: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """Sort versions by semantic versioning, newest first."""
        return sorted(versions, key=lambda x: self._parse_version(x[1]), reverse=True)
    
    def _get_available_tools(self, tool_name: str) -> List[Tuple[str, str]]:
        """
        Get available versions of a tool from CVMFS.
        
        Args:
            tool_name: Name of the tool to search for
            
        Returns:
            List of (tool_name, version) tuples
        """
        if not self._is_cvmfs_available():
            raise RuntimeError(f"CVMFS not available at {self.cvmfs_singularity}")

        try:
            containers = []
            for item in self.cvmfs_singularity_path.iterdir():
                if item.is_file() or item.is_symlink():
                    # Container names are like "samtools:1.22" 
                    name = item.name
                    if ":" in name:
                        container_tool, version = name.split(":", 1)
                        if container_tool.lower() == tool_name.lower():
                            containers.append((container_tool, version))
            
            return containers
        except (OSError, PermissionError) as e:
            raise RuntimeError(f"Failed to read CVMFS directory: {e}")
    
    def _get_latest_version(self, versions: List[Tuple[str, str]]) -> Tuple[str, str]:
        """
        Get the latest version from a list of versions.
        
        Args:
            versions: List of (tool_name, version) tuples
            
        Returns:
            The (tool_name, version) tuple with the latest version
        """
        if not versions:
            raise ValueError("No versions provided")
        
        # Sort by version, latest first
        sorted_versions = self._sort_versions(versions)
        return sorted_versions[0]

    def _compute_sha256(self, path: str) -> str:
        """Compute the SHA-256 digest of a file (e.g. a SIF container)."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def _is_registry_miss(self, output: str) -> bool:
        """Return True if shpc output indicates the tag is absent from the registry."""
        lower = output.lower()
        return any(p in lower for p in [
            "not found", "not in registry", "does not exist",
            "is not a known identifier", "no container", "unknown tag",
        ])

    def _run_shpc_install(self, uri_tag: str, container_path: str) -> Tuple[int, str]:
        """
        Run: shpc install <uri_tag> <container_path> --keep-path

        Example:
            shpc install \
                quay.io/biocontainers/plink:1.90b7.7--h18e278d_1 \
                /cvmfs/singularity.galaxyproject.org/all/plink:1.90b7.7--h18e278d_1 \
                --keep-path

        Returns:
            (returncode, combined stdout+stderr)
        """
        msg = f"Running shpc install {uri_tag} {container_path} --keep-path"
        log.info(msg)
        
        result = subprocess.run(
            _shpc_cmd("install", uri_tag, container_path, "--keep-path"),
            capture_output=True, text=True,
        )
        return result.returncode, result.stdout + result.stderr

    def _register_local_registry(self, local_registry: str) -> None:
        """Ensure local_registry is in shpc's registry search path (best-effort).

        Rewrites shelley's own settings file rather than shelling out to
        `shpc config add registry`, which would call shpc's save() and expand our small
        override file into a frozen snapshot of every site default.
        """
        try:
            ensure_shared_dir(Path(local_registry))
            ensure_shared_shpc_settings()
            log.info("Local registry is in shpc's search path: %s", local_registry)
        except Exception as e:
            log.warning("Could not register local registry with shpc: %s", e)

    def _ensure_local_registry_entry(
        self, tool_name: str, version: str, container_path: str, uri: str,
        local_registry: str | None = None, interactive: bool = False,
        in_upstream: bool = False, status=None,
    ) -> list[dict]:
        """
        Create or update a local shpc registry entry, returning the aliases written.

        Merges into the existing local container.yaml when one is already present —
        only downloads a fresh upstream copy as the base when no local file exists
        yet, so tags added by earlier local-only builds of this same tool survive
        (a fresh copy can't restore them, since they don't exist upstream). Aliases
        come from the upstream entry (when ``in_upstream``) or from a guts diff of
        the SIF otherwise; when ``interactive`` is set they are curated
        interactively first.

        Whenever the version is absent upstream, or its aliases were interactively
        curated, also creates a marker directory at registry_dir/<version>/
        containing an aliases.yaml snapshot of exactly this version's own aliases
        plus the ``in_upstream`` flag. This is invisible to shpc — its filesystem
        registry provider only ever looks for a file literally named container.yaml,
        never a per-version subdirectory — but lets uninstall_module later tell
        whether this specific tag was a genuine local addition (safe to delete from
        the shared container.yaml) or an interactive edit of a tag that's still
        legitimately upstream (marker removed, but the tag entry itself left alone).
        The snapshot also matters because config["aliases"] is one shared field
        across every tag in this file: building a second locally-curated version
        overwrites it with that version's own aliases, which can genuinely differ a
        lot from an older one's (e.g. star-fusion:1.0.0 only aliases STAR; newer
        builds also alias salmon). Without the snapshot, an earlier version's
        aliases would be unrecoverable the moment a later one is built.
        """
        registry_dir = Path(local_registry or gl.local_registry()) / uri
        registry_yaml = registry_dir / "container.yaml"
        ensure_shared_dir(registry_dir)

        if not registry_yaml.exists():
            # Download upstream entry as a base (best-effort; tool may not be in
            # upstream at all). Skipped when a local file already exists so this
            # doesn't clobber tags added by earlier local-only builds of this tool.
            remote_url = (
                f"https://raw.githubusercontent.com/singularityhub/shpc-registry/main/{uri}/container.yaml"
            )
            subprocess.run(
                ["curl", "-fsSL", remote_url, "-o", str(registry_yaml)],
                capture_output=True, text=True,
            )

        config = _load_registry_config(uri, registry_yaml)
        if not config:
            config = {"docker": uri, "tags": {}, "filter": [version]}

        # Source aliases: upstream's curated set, or a guts diff of this SIF.
        if in_upstream:
            aliases = normalize_aliases(config.get("aliases") or [])
        else:
            # keep=tool so a tool sharing a name with a base binary survives
            # the basename subtraction in the guts diff.
            aliases = extract_aliases(container_path, keep=tool_name)
            if not aliases:
                log.warning("No aliases extracted for %s; module will have no wrapper scripts", container_path)

        if interactive:
            # Suspend the status spinner so the interactive prompt owns the terminal.
            if status is not None:
                status.stop()
            try:
                aliases = edit_aliases_interactive(aliases)
            finally:
                if status is not None:
                    status.start()

        config["aliases"] = aliases

        sha256 = self._compute_sha256(container_path)
        config.setdefault("tags", {})[version] = f"sha256:{sha256}"

        ensure_shared_dir(registry_yaml.parent)
        with open(registry_yaml, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        # curl wrote this file above under the ambient umask; make it readable
        # unconditionally so every user's `shelley find` can consult the entry.
        share_file(registry_yaml)

        if not in_upstream or interactive:
            marker_dir = registry_dir / version
            ensure_shared_dir(marker_dir)
            aliases_snapshot = marker_dir / "aliases.yaml"
            with open(aliases_snapshot, "w") as f:
                yaml.dump({"version": version, "aliases": aliases, "in_upstream": in_upstream}, f,
                          default_flow_style=False, sort_keys=False)
            share_file(aliases_snapshot)

        return aliases

    def _run_shpc_uninstall(self, uri_tag: str) -> Tuple[int, str]:
        """Run `shpc uninstall --force <uri_tag>`. Returns (returncode, combined output)."""
        result = subprocess.run(
            _shpc_cmd("uninstall", "--force", uri_tag), capture_output=True, text=True,
        )
        return result.returncode, result.stdout + result.stderr

    def _shpc_uninstall(self, uri_tag: str) -> None:
        """Uninstall an existing shpc entry (best-effort; ignores errors)."""
        self._run_shpc_uninstall(uri_tag)

    def _shpc_module_base(self) -> Path:
        """Ask shpc where it installed the module.

        Queried rather than assumed so that an operator edit to the settings file is
        honoured, but falls back to the shared default: an empty or failed query must not
        become an unhandled exception after a successful install.
        """
        result = subprocess.run(
            _shpc_cmd("config", "get", "module_base"),
            capture_output=True, text=True,
        )
        reported = result.stdout.strip() if result.returncode == 0 else ""
        if not reported:
            log.warning(
                "Could not read module_base from shpc (rc=%s); assuming %s",
                result.returncode, gl.shpc_module_base(),
            )
            return gl.shpc_module_base()
        return Path(reported)

    def _share_build_artifacts(self, module_base: Path, tool_name: str, uri: str) -> None:
        """Make this tool's artifacts readable and executable by every user.

        Scoped to this tool's subtrees rather than walking the whole shpc base, which
        would cost more on every build as modules accumulate.

        Hardening stops at the tool directory, not the version directory: shpc writes a
        `.version` file alongside the versions to tell Lmod which is the default, and an
        unreadable one breaks a bare `module load <tool>` for everyone else.
        """
        subtrees = [
            module_base.joinpath(*_SHPC_URI_PREFIX, tool_name),
            gl.shpc_wrapper_base().joinpath(*_SHPC_URI_PREFIX, tool_name),
            gl.shpc_container_base().joinpath(*_SHPC_URI_PREFIX, tool_name),
            gl.local_registry() / uri,
        ]
        for subtree in subtrees:
            # ensure_traversable covers the intermediate quay.io/biocontainers/<tool>
            # levels, which shpc created with a bare makedirs under whatever umask was
            # in force. One non-traversable component hides everything below it.
            ensure_traversable(subtree)
            harden_tree(subtree)

    def shpc_install(self, tool_name: str, version: str,
                     interactive: bool = False, status=None) -> Path:
        """
        Install a CVMFS container as a functional Lmod module using shpc.

        Two paths:
        - Version in upstream shpc-registry: call shpc install directly; upstream
          aliases are used as-is.  Retry once (uninstall + reinstall) on path-exists
          conflict.
        - Version absent from upstream: uninstall any stale install, create a local
          registry entry with guts-extracted aliases, then call shpc install once.

        When ``interactive`` is set, the aliases (upstream or guts-extracted) are
        curated interactively and written to a local registry entry that shadows any
        upstream one — so curation works for both build paths.  ``status`` is the
        active rich spinner, suspended while the prompt is shown.

        Returns:
            Path to the symlinked .lua file (the user-facing module path).
        """
        uri = f"quay.io/biocontainers/{tool_name}"
        uri_tag = f"{uri}:{version}"
        container_path = str(self.cvmfs_singularity_path / f"{tool_name}:{version}")

        local_registry = gl.local_registry()

        # One upstream fetch gives us both the tag check and the upstream aliases
        # (used for the empty-alias warning below without a second request).
        upstream_local_yaml = local_registry / uri / "container.yaml"
        upstream_config = _load_registry_config(uri, upstream_local_yaml, force_upstream=True)
        in_upstream = version in upstream_config.get("tags", {})

        # Edited builds always route through a local entry so edits persist and shadow
        # upstream; unedited upstream builds install directly from the upstream registry.
        create_local = (not in_upstream) or interactive

        final_aliases: list[dict]
        if create_local:
            self._shpc_uninstall(uri_tag)
            final_aliases = self._ensure_local_registry_entry(
                tool_name, version, container_path, uri,
                interactive=interactive, in_upstream=in_upstream, status=status,
            )
            self._register_local_registry(str(local_registry))
            if not in_upstream:
                console.print(ShelleyStyle.create_warning_panel(
                    "Tag not in registry",
                    f"{uri}:{version} is not in the upstream shpc-registry. "
                    f"A local entry has been created in {local_registry}.",
                ))
        else:
            final_aliases = normalize_aliases(upstream_config.get("aliases") or [])

        returncode, output = self._run_shpc_install(uri_tag, container_path)

        if returncode and not create_local:
            # Path-exists conflict on a pure upstream install — uninstall and retry once.
            self._shpc_uninstall(uri_tag)
            returncode, output = self._run_shpc_install(uri_tag, container_path)

        if returncode:
            raise RuntimeError(
                f"shpc install failed for {uri_tag}:\n{output.strip()}"
            )

        module_base = self._shpc_module_base()

        # Artifacts are created by root (the build path re-execs under sudo) but every
        # user on the machine has to be able to read the module and run its wrappers.
        # This deliberately replaces an older `chown -R $SUDO_USER` — handing the tree
        # to one account is what made builds single-user in the first place.
        self._share_build_artifacts(module_base, tool_name, uri)

        src = module_base.joinpath(*_SHPC_URI_PREFIX, tool_name, version, "module.lua")
        dest_dir = self.lmod_modules_path / tool_name
        dest = dest_dir / f"{version}.lua"
        ensure_shared_dir(dest_dir)
        if dest.is_symlink() or dest.exists():
            dest.unlink()
        dest.symlink_to(src)

        if not interactive and not final_aliases:
            console.print(ShelleyStyle.create_warning_panel(
                "No aliases",
                f"{uri_tag} exposes no command aliases, so the module has no "
                f"wrapper scripts. Rebuild with -i/--interactive to add some:\n\n"
                f"shelley build {tool_name}/{version} --interactive",
            ))

        return dest

    def uninstall_module(self, tool_name: str, version: str) -> dict:
        """
        Uninstall a specific tool@version: the inverse of shpc_install.

        Runs `shpc uninstall --force` for the shpc-managed module/wrapper/container
        artifacts, and removes the Lmod modulefile symlink shelley creates directly
        (shpc has no knowledge of it) — pruning its parent tool directory too, if
        that was the last version installed for this tool.

        local_registry()/<uri>/container.yaml is not exclusively "owned" by one
        installed version the way the modulefile symlink is: _load_registry_config
        also writes it as a cache of the *entire* upstream shpc-registry the first
        time anything calls get_registry_tags (e.g. `shelley find`, or version
        resolution during `shelley build`). While other versions of this tool are
        still installed, its tags dict is only safe to prune when
        _ensure_local_registry_entry left a registry_dir/<version>/ marker directory
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
            log.warning("shpc uninstall reported rc=%s for %s: %s", returncode, uri_tag, output.strip())

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
                        marker_in_upstream = bool((yaml.safe_load(f) or {}).get("in_upstream", False))

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
                                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
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

    def list_versions(self, tool_name: str) -> List[str]:
        """
        List available versions of a tool without creating a module.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            List of version strings
        """
        versions = self._get_available_tools(tool_name)
        if not versions:
            return []
        
        # Sort versions newest first
        sorted_versions = self._sort_versions(versions)
        return [version for _, version in sorted_versions]

    def list_versions_with_paths(self, tool_name: str) -> List[Tuple[str, str]]:
        """
        List available versions of a tool with their full CVMFS paths.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            List of (version, full_path) tuples
        """
        sorted_versions = self.list_versions(tool_name)
        return [(version, str(self.cvmfs_singularity_path / f"{tool_name}:{version}"))
                for version in sorted_versions]

    def _select_version_interactively(
        self,
        tool_name: str,
        matches: List[Tuple[str, str]],
        labels: Optional[List[str]] = None,
    ) -> Tuple[str, str]:
        """
        Prompt the user to pick one build when multiple exist for the same short version.

        Args:
            tool_name: Name of the tool (used only for display).
            matches: ``(tool, full_version)`` tuples, sorted newest-first.
            labels: Optional pre-built display strings (one per match).
                    Falls back to the raw version string when omitted.
        """
        if labels is None:
            labels = [ver for _, ver in matches]

        choices = [
            questionary.Choice(title=label, value=match)
            for label, match in zip(labels, matches)
        ]

        selected = questionary.select(
            f"Multiple builds found for {tool_name}. Select one to install:",
            choices=choices,
        ).ask()

        if selected is None:
            raise ValueError("Version selection cancelled.")

        return selected
    
    def search_tool_version(self, tool_name: str, requested_version: Optional[str] = None) -> Tuple[str, str]:
        """
        Searches for a tool name to the requested version or the latest version if not provided.
        Also handles the case of multiple matching versions.

        Args:
            tool_name: Name of the tool to search in CVMFS.
            requested_version: Optional full or short version string to match.

        Returns:
            A ``(tool_name, version)`` tuple for the selected tool version.
            These are the exact inputs required for self.shpc_install.

        Raises:
            ValueError: If no matching version exists or the request is ambiguous.
        """
        # Get available versions as (tool, full_version) tuples
        available_versions = self._get_available_tools(tool_name)

        if not available_versions:
            raise ValueError(
                f"'{tool_name}' not found in CVMFS at {self.cvmfs_singularity}. "
                "Check the tool name and that CVMFS is mounted."
            )

        if requested_version is None:
            # If no version was specified, return the latest version
            final_tool, final_version = self._get_latest_version(available_versions)
            return final_tool, final_version

        # If a version was provided, match against both full versions ("1.21--h50ea8bc_3") and short ones ("1.21")
        matches = [
            (tool, ver)
            for tool, ver in available_versions
            if ver == requested_version or ver.split("--", 1)[0] == requested_version
        ]

        if not matches:
            short_versions = sorted({ver.split("--", 1)[0] for _, ver in available_versions})
            raise ValueError(
                f"Version '{requested_version}' not found for '{tool_name}'. "
                f"Available versions: {', '.join(short_versions)}"
            )
        
        if len(matches) > 1:
            def _mtime(ver: str) -> float:
                try:
                    return (self.cvmfs_singularity_path / f"{tool_name}:{ver}").stat().st_mtime
                except OSError:
                    return 0.0

            matches_sorted = sorted(matches, key=lambda x: _mtime(x[1]), reverse=True)

            labels = []
            for _, ver in matches_sorted:
                path = self.cvmfs_singularity_path / f"{tool_name}:{ver}"
                try:
                    stat = path.stat()
                    size_mb = stat.st_size / (1024 ** 2)
                    modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d")
                    labels.append(f"{ver}  ({size_mb:.1f} MB, modified {modified})")
                except OSError:
                    labels.append(ver)

            return self._select_version_interactively(tool_name, matches_sorted, labels)
            
        return matches[0]