"""Alias discovery for SIFs that have no upstream registry entry.

Same method as ``builder.guts_integration.extract_aliases`` (diff the SIF against base
OS manifests from shpc-guts), but failures are not swallowed: if shpc-guts cannot be
cloned, ``NetworkUnavailable`` is raised, so a build stops before writing anything
instead of producing a module with no tool command. Any other failure of the
analysis itself still yields ``[]``, with a warning to curate aliases by hand, as before.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from container_guts.main import ManifestGenerator

from ..builder.guts_integration import (
    BASE_IMAGE_NAMESPACES,
    SHPC_GUTS_DB_URL,
    _alias_names,
    _merge_supplementary_db,
)
from ..errors import NetworkUnavailable

_NETWORK_HINTS = {
    "could not resolve host": "the name could not be resolved (no DNS or no network)",
    "failed to connect": "the connection failed",
    "connection timed out": "the request timed out",
    "operation timed out": "the request timed out",
    "proxy": "the proxy refused the connection",
    "unable to access": "the connection failed",
}


def discover_aliases(sif: Path, keep: str | None = None) -> list[dict]:
    """Aliases (``[{"name", "command"}]``) for executables unique to ``sif``.

    ``keep`` (the tool name) is pulled back out of the basename-shadowed set, so a tool
    named like a base binary (``sort``, ``time``) still gets its alias.
    """
    tmpdir = tempfile.mkdtemp(prefix="shelley-guts-")
    try:
        _clone_base_manifests(tmpdir)
        _merge_supplementary_db(tmpdir)
        try:
            result = ManifestGenerator(tech="singularity").diff(
                str(sif), database=tmpdir
            )
        except (Exception, SystemExit):
            return []
        if not result:
            return []
        diff = next(iter(result.values()), {}).get("diff", {})
        candidates = list(diff.get("unique_paths", []))
        if keep:
            candidates += [
                p for p in diff.get("shadowed_paths", []) if os.path.basename(p) == keep
            ]
        return [{"name": n, "command": n} for n in _alias_names(candidates)]
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _clone_base_manifests(tmpdir: str) -> None:
    """Shallow sparse clone of the base OS manifests; network failures are named."""
    for argv in (
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--filter=blob:none",
            "--sparse",
            SHPC_GUTS_DB_URL,
            tmpdir,
        ],
        ["git", "-C", tmpdir, "sparse-checkout", "set", *BASE_IMAGE_NAMESPACES],
    ):
        r = subprocess.run(argv, capture_output=True, text=True)
        if r.returncode:
            raise NetworkUnavailable("github.com", _reason(r.stderr))


def _reason(stderr: str) -> str:
    lower = stderr.lower()
    for hint, reason in _NETWORK_HINTS.items():
        if hint in lower:
            return reason
    last = stderr.strip().splitlines()[-1] if stderr.strip() else "git clone failed"
    return last.removeprefix("fatal: ")
