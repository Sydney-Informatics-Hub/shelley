"""Environment (Lmod) module loading for the build path.

BioShell provides shpc and singularity as Lmod modules that must be loaded before
use. This helper loads them into the current process environment so subsequent
subprocess calls (shpc, and singularity via container-guts) inherit an environment
where those tools are on PATH.

It is called ONLY from the build path (shelley.commands.build.build_module) so that
read-only commands (find, search, versions) remain uvx-able on non-BioShell systems
and never touch the module system. On hosts without Lmod, or if the load fails, it
warns and continues, relying on whatever shpc/singularity are already on PATH.
"""

import os
import shutil
import subprocess
from collections.abc import Sequence

from ..utils.globals import BUILD_MODULES
from ..utils.style import print_info, print_warning

# Load (and warn) at most once per process, so batch builds don't repeat themselves.
_LOADED = False


def _lmod_cmd() -> str | None:
    """Return the Lmod driver binary, or None if no module system is present."""
    return os.environ.get("LMOD_CMD") or shutil.which("lmod")


def load_build_modules(names: Sequence[str] = BUILD_MODULES) -> bool:
    """Load the given Lmod modules into os.environ (idempotent, warn-once).

    Returns True if the modules were loaded, False if the module system is absent
    or the load failed (in which case a warning is printed and the caller should
    continue, relying on tools already on PATH).
    """
    global _LOADED
    if _LOADED:
        return True

    lmod_cmd = _lmod_cmd()
    if not lmod_cmd:
        print_info(
            "Module system (Lmod) not detected; assuming "
            f"{', '.join(names)} are already on PATH"
        )
        _LOADED = True
        return False

    result = subprocess.run(
        [lmod_cmd, "python", "load", *names],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print_warning(
            f"Failed to load modules {', '.join(names)}: {result.stderr.strip()}"
        )
        _LOADED = True
        return False

    # Lmod's `python` output is Python code that mutates os.environ.
    exec(result.stdout, {"os": os})
    _LOADED = True
    return True
