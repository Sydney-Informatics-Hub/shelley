import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from container_guts.main import ManifestGenerator

from ..builder.alias_editor import AliasEditorApp

_SUPPLEMENTARY_DB = Path(__file__).parent.parent / "data" / "guts_db"


def _merge_supplementary_db(tmpdir: str) -> None:
    """Copy bundled extra manifests (e.g. miniconda3) into the guts tmpdir."""
    if _SUPPLEMENTARY_DB.exists():
        shutil.copytree(str(_SUPPLEMENTARY_DB), tmpdir, dirs_exist_ok=True)


def _sparse_clone_base_manifests(db_url: str, namespaces: list[str]) -> str:
    """
    Shallow sparse-clone only the base OS image directories from db_url.
    Returns the tmpdir path; caller is responsible for cleanup.

    dbs = shpc guts have general json manifests to diff against
    """
    tmpdir = tempfile.mkdtemp(prefix="shelley-guts-")
    subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--filter=blob:none",
            "--sparse",
            db_url,
            tmpdir,
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", tmpdir, "sparse-checkout", "set"] + namespaces,
        check=True,
        capture_output=True,
    )
    return tmpdir


SHPC_GUTS_DB_URL = "https://github.com/singularityhub/shpc-guts"

# Only the families that actually contribute names to the subtraction. debian,
# centos and fedora are also in shpc-guts, and were measured and dropped: with
# basename matching in the guts diff, ubuntu + busybox + the conda manifests
# already cover every name they added, for a third of the clone size.
BASE_IMAGE_NAMESPACES = [
    "docker.io/library/ubuntu",
    "docker.io/library/alpine",
    "docker.io/library/busybox",
    "docker.io/library/rockylinux",
]


_BIN_RE = re.compile(r"/(s?bin)/")


def _alias_names(paths) -> list[str]:
    """Executable names to expose as aliases, from a list of container paths.

    Keeps only what lives in a bin/sbin directory, and dedupes: the same
    executable often sits in two PATH dirs (/usr/bin and /usr/local/bin), which
    would otherwise produce two identical aliases.
    """
    names = []
    for path in sorted(paths):
        name = os.path.basename(path)
        if _BIN_RE.search(path) and name and name not in names:
            names.append(name)
    return names


def extract_aliases(cvmfs_path: str, keep: str | None = None) -> list[dict]:
    """
    Use guts to find executables unique to this container vs base OS images.

    Sparse-clones the base OS manifests listed in BASE_IMAGE_NAMESPACES from the
    shpc-guts database (no image pulling; CVMFS SIF must already be on disk).
    Returns shpc alias dicts: [{"name": "bwa", "command": "bwa"}, ...].
    Returns [] silently if guts is unavailable or analysis fails.

    guts drops executables whose *basename* belongs to a base image, since base
    images relocate the same binary (busybox applets land in /bin, /sbin and
    /usr/sbin depending on the image), and reports them under "shadowed_paths".
    That is stricter than the tool wants in one case: a tool legitimately named
    like a base binary - "sort", "time", "join" - would disappear. Pass ``keep``
    (the tool name) to pull it back out of the shadowed set.

    Replicates https://github.com/singularityhub/guts/blob/main/.github/workflows/generate.yaml#L64
    """
    tmpdir = None
    try:
        tmpdir = _sparse_clone_base_manifests(SHPC_GUTS_DB_URL, BASE_IMAGE_NAMESPACES)
        _merge_supplementary_db(tmpdir)
        # Use the Sydney-Informatics-Hub/guts implementation for singularity support
        gen = ManifestGenerator(tech="singularity")
        result = gen.diff(cvmfs_path, database=tmpdir)
        if not result:
            return []
        diff_data = next(iter(result.values()), {}).get("diff", {})
        candidates = list(diff_data.get("unique_paths", []))
        if keep:
            candidates += [
                p
                for p in diff_data.get("shadowed_paths", [])
                if os.path.basename(p) == keep
            ]
        return [{"name": n, "command": n} for n in _alias_names(candidates)]
    except (Exception, SystemExit):
        return []
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)

def edit_aliases_interactive(aliases: list[dict]) -> list[dict]:
    """Interactively deselect, rename, and add module aliases.

    Runs three questionary steps in sequence — a pre-checked deselect checkbox,
    an optional rename pass (invocation name only), and an optional add loop —
    and returns the resulting canonical ``[{"name", "command"}]`` list.

    Raises:
        ValueError: If the user cancels any step.
    """
    app = AliasEditorApp(aliases)
    edited = app.run(inline=True)
    print(f"{edited}")
    return edited
