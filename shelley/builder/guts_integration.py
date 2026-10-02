import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import questionary
from container_guts.main import ManifestGenerator

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


def normalize_aliases(aliases) -> list[dict]:
    """Return aliases in the canonical ``[{"name", "command"}]`` list form.

    shpc registries store aliases either as a ``{name: command}`` dict (upstream
    shpc-registry ``container.yaml``) or as a list of ``{"name", "command"}``
    dicts (what shelley writes). Accept either and return the list form so the
    rest of the code has a single shape to work with.
    """
    if not aliases:
        return []
    if isinstance(aliases, dict):
        return [{"name": name, "command": command} for name, command in aliases.items()]
    return [{"name": a["name"], "command": a["command"]} for a in aliases]


def _cancelled(value) -> bool:
    """questionary returns None from .ask() when the user aborts (Ctrl-C/ESC)."""
    return value is None


def select_aliases(aliases: list[dict]) -> list[dict]:
    """Prompt the user to choose which binaries to keep as aliases.

    Presents an interactive checkbox of the candidates, all *unchecked* so the
    user checks only the binaries they want. Choices start unchecked because
    the search filter (``use_search_filter``) only hides rows from view — it
    never unchecks them — so pre-checking everything would return the whole list
    regardless of what the user filtered to. Returns the chosen subset (order
    preserved).

    Raises:
        ValueError: If the user cancels the selection.
    """
    if not aliases:
        return aliases

    choices = [
        questionary.Choice(title=a["name"], value=a, checked=False) for a in aliases
    ]
    selected = questionary.checkbox(
        "Select which binaries to expose as aliases (these can be renamed in the next step):",
        choices=choices,
        instruction="(↑↓ move · type to filter · space to check the ones you want · enter confirm)",
        use_search_filter=True,
        use_jk_keys=False,  # required: j/k conflict with the search filter
    ).ask()

    if _cancelled(selected):
        raise ValueError("Alias selection cancelled.")

    return selected


def _rename_aliases(aliases: list[dict]) -> list[dict]:
    """Optionally rename the invocation name of selected aliases (command kept)."""
    if not aliases:
        return aliases

    if not questionary.confirm(
        "Rename any aliases?",
        default=False,
        instruction="(y/n)",
    ).ask():
        return aliases

    to_rename = questionary.checkbox(
        "Select aliases to rename:",
        choices=[questionary.Choice(title=a["name"], value=a) for a in aliases],
        instruction="(↑↓ move · space toggle · enter confirm)",
    ).ask()
    if _cancelled(to_rename):
        raise ValueError("Alias rename cancelled.")

    for alias in to_rename:
        new_name = questionary.text(
            f"New name for '{alias['name']}':",
            default=alias["name"],
        ).ask()
        if _cancelled(new_name):
            raise ValueError("Alias rename cancelled.")
        new_name = new_name.strip()
        if new_name:
            alias["name"] = new_name

    return aliases


def _add_aliases(aliases: list[dict], require_confirm: bool = True) -> list[dict]:
    """Append new aliases the user types in by hand.

    When ``require_confirm`` is set, gate the whole step behind a yes/no prompt;
    callers that already know the user needs to add aliases (e.g. a container with
    none detected) pass ``False`` to drop straight into the add loop.
    """
    if (
        require_confirm
        and not questionary.confirm(
            "Add new aliases?",
            default=False,
            instruction="(y/n)",
        ).ask()
    ):
        return aliases

    while True:
        name = questionary.text(
            "Alias name:",
            instruction="(what you would type to run the tool e.g. fastqc)",
        ).ask()
        if _cancelled(name):
            raise ValueError("Alias add cancelled.")
        name = name.strip()
        if not name:
            break

        command = questionary.text(
            "Binary path:",
            default=name,
            instruction="(full path to the executable inside the container e.g. /usr/local/bin/<tool_name>)",
        ).ask()
        if _cancelled(command):
            raise ValueError("Alias add cancelled.")
        command = command.strip() or name

        aliases.append({"name": name, "command": command})

        if not questionary.confirm("Add another?", default=False).ask():
            break

    return aliases


def edit_aliases_interactive(aliases: list[dict]) -> list[dict]:
    """Interactively deselect, rename, and add module aliases.

    Runs three questionary steps in sequence — a pre-checked deselect checkbox,
    an optional rename pass (invocation name only), and an optional add loop —
    and returns the resulting canonical ``[{"name", "command"}]`` list.

    Raises:
        ValueError: If the user cancels any step.
    """
    aliases = normalize_aliases(aliases)
    if not aliases:
        # Nothing was detected — tell the user and go straight into adding.
        questionary.print(
            "No aliases were detected for this container. Add one or more so the "
            "module exposes a command to run.",
            style="bold fg:yellow",
        )
        aliases = _add_aliases(aliases, require_confirm=False)
        return aliases

    aliases = select_aliases(aliases)
    aliases = _add_aliases(aliases)
    aliases = _rename_aliases(aliases)
    return aliases
