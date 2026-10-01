"""Self-upgrade: run the correct ``uv tool upgrade`` for this install.

shelley is installed exclusively from git via ``uv tool`` (see
docs/how-to/install.md), and the exact upgrade command differs by install mode:

- **system-wide** — installed under ``/opt/uv/tools`` for every user on the VM;
  upgrading needs ``sudo``, the ``UV_TOOL_DIR``/``UV_TOOL_BIN_DIR`` overrides, and
  uv's absolute path (``sudo`` resets ``PATH``).
- **per-user** — installed under ``~/.local``; a plain ``uv tool upgrade`` works.

``shelley update`` detects which one applies from where this package lives, then
runs ``uv tool upgrade shelley`` (uv re-resolves the recorded ``git+…@branch``
source). Output streams straight through so uv's progress — and any ``sudo``
password prompt — is visible to the user.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from ..utils.style import (
    ShelleyStyle,
    console,
    print_command,
    print_error,
    print_info,
    print_success,
)

# Fixed layout of a system-wide install (docs/how-to/install.md). uv places the
# tool env at ``/opt/uv/tools/shelley`` and links the executable to
# ``/usr/local/bin``. ``SYSTEM_UV`` is the BioShell convention for uv's location
# — a fallback used only when uv isn't found on PATH (see ``_find_uv``).
SYSTEM_TOOL_DIR = "/opt/uv/tools"
SYSTEM_BIN_DIR = "/usr/local/bin"
SYSTEM_UV = "/opt/uv/uv"

# Where to point users when the upgrade can't run automatically.
DOCS_URL = (
    "https://github.com/Sydney-Informatics-Hub/shelley/blob/main/docs/how-to/install.md"
)


def _is_system_install() -> bool:
    """True if this shelley is the system-wide install under ``/opt/uv/tools``.

    A system-wide install has its package files under ``/opt/uv/tools/shelley/``;
    a per-user install lives under ``~/.local``.
    """
    return str(Path(__file__).resolve()).startswith(SYSTEM_TOOL_DIR)


def _find_uv() -> Optional[str]:
    """Absolute path to the uv executable, or None if it can't be located.

    Prefers uv on PATH; falls back to the BioShell system location
    (``/opt/uv/uv``) only if that exists. An absolute path is required either
    way, because the system-install upgrade runs under ``sudo``, which resets
    PATH and so cannot see a bare ``uv``.
    """
    found = shutil.which("uv")
    if found:
        return found
    if Path(SYSTEM_UV).exists():
        return SYSTEM_UV
    return None


def _build_upgrade_cmd(uv: str) -> list[str]:
    """Return the argv for ``uv tool upgrade shelley`` for this install mode.

    ``uv`` must be an absolute path (see ``_find_uv``).
    """
    if _is_system_install():
        # sudo resets PATH, so call uv by absolute path and re-supply the tool
        # dir/bin overrides via ``env`` (mirrors docs/how-to/install.md).
        return [
            "sudo",
            "env",
            f"UV_TOOL_DIR={SYSTEM_TOOL_DIR}",
            f"UV_TOOL_BIN_DIR={SYSTEM_BIN_DIR}",
            uv,
            "tool",
            "upgrade",
            "shelley",
        ]
    return [uv, "tool", "upgrade", "shelley"]


def update_shelley() -> int:
    """Upgrade shelley in place via uv. Returns a process exit code.

    Runs the upgrade unconditionally — uv no-ops when already current — so this
    never depends on the (cached, possibly stale) daily update check.
    """
    from .. import __version__

    uv = _find_uv()
    if uv is None:
        print_error(f"Could not find the 'uv' executable on PATH or at {SYSTEM_UV}.")
        print_info(
            f"Install uv first — see the install guide: "
            f"[link={DOCS_URL}]{DOCS_URL}[/link]"
        )
        return 1

    cmd = _build_upgrade_cmd(uv)
    mode = "system-wide" if _is_system_install() else "per-user"

    console.print(ShelleyStyle.create_version_info())
    print_info(f"Detected [highlight]{mode}[/highlight] install. Running:")
    print_command(" ".join(cmd))
    console.print()

    try:
        result = subprocess.run(cmd)
    except FileNotFoundError as exc:
        # uv was resolved above, so this is a missing ``sudo`` (system install).
        print_error(f"Could not run the upgrade: [muted]{exc}[/muted]")
        print_info(f"See the install guide: [link={DOCS_URL}]{DOCS_URL}[/link]")
        return 1

    if result.returncode == 0:
        print_success(f"shelley is up to date (was [version]{__version__}[/version]).")
        print_info("Restart your shell for any new version to take effect.")
    else:
        print_error("Upgrade failed. See the output above for details.")
        print_info(f"Install guide: [link={DOCS_URL}]{DOCS_URL}[/link]")

    return result.returncode
