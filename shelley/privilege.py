"""When and how a build re-runs itself as root.

Shared modules live in root-owned ``/apps``. When this process cannot write there, the
build re-runs the *same* shelley under ``sudo``, after resolving the request as the user,
and passes only the resolved tags (``--resolved-tag tool:tag``). So bad input is reported
before any password prompt, and root acts only on validated values.

Copied from ``commands/build.py`` for the parallel change.
"""

import importlib.util
import os
import shutil
import subprocess
import sys

from .utils.globals import build_roots


def needs_root() -> bool:
    """True if any build root is missing or not writable by this process."""
    if os.geteuid() == 0:
        return False
    return any(not r.exists() or not os.access(r, os.W_OK) for r in build_roots())


def sudo_env_args() -> list[str]:
    """``PATH`` and every ``SHELLEY_*`` variable, passed explicitly through ``sudo env``.

    This includes ``SHELLEY_LEGACY_BUILD``, so the root child takes the same build path.
    """
    args = [f"PATH={os.environ['PATH']}"]
    args += [
        f"{k}={v}" for k, v in sorted(os.environ.items()) if k.startswith("SHELLEY_")
    ]
    return args


def launcher() -> list[str] | None:
    """argv that re-runs *this* shelley: the running interpreter, else PATH."""
    if importlib.util.find_spec("shelley") is not None:
        return [sys.executable, "-m", "shelley"]
    found = shutil.which("shelley")
    return [found] if found else None


def reexec(args: list[str]) -> int:
    """Run ``shelley <args>`` as root; return its exit code (130 if interrupted)."""
    prefix = launcher()
    if prefix is None:
        raise RuntimeError("Could not locate the 'shelley' executable on PATH")
    try:
        return subprocess.run(
            ["sudo", "-E", "env", *sudo_env_args(), *prefix, *args], check=False
        ).returncode
    except KeyboardInterrupt:
        return 130
