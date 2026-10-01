"""Check whether a newer shelley is available on the main branch.

shelley is installed exclusively from git (see docs/how-to/install.md), so
"a newer version" means: the ``__version__`` declared in ``shelley/__init__.py``
on the *main* branch is ahead of the version we are currently running.

This module fetches that value over the network, caches the result for a day,
and fails silently on any error so it can never break or slow a real command.
Networking uses only the standard library (mirrors shelley/scripts/build_rsec_meta.py).

Developers: the repo/branch this points at is the DEVELOPER CONFIG block below.
The notice tells users to run ``shelley update`` (shelley/commands/update.py),
which performs the upgrade for them.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from pathlib import Path

from .. import __version__

# --- DEVELOPER CONFIG -------------------------------------------------------
# The GitHub repo and branch the update check reads __version__ from. If the
# canonical repo or default branch ever changes, change it here.
REPO = "Sydney-Informatics-Hub/shelley"
BRANCH = "main"
MAIN_INIT_URL = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/shelley/__init__.py"
# The rendered docs page the upgrade command lives on (clickable in the notice).
DOCS_URL = (
    f"https://github.com/{REPO}/blob/{BRANCH}/docs/how-to/install.md"
    "#install-a-newer-version-for-yourself-per-user"
)
# ---------------------------------------------------------------------------

# Opt-out: set this to any non-empty value to skip the check entirely
# (CI, offline/airgapped nodes, or users who simply don't want it).
OPT_OUT_ENV = "SHELLEY_NO_UPDATE_CHECK"

_FETCH_TIMEOUT = 2.0  # seconds; keep short so an unreachable network never hangs
_CACHE_TTL = 24 * 60 * 60  # re-check at most once per day
_VERSION_RE = re.compile(r"""__version__\s*=\s*['"]([^'"]+)['"]""")


def _cache_path() -> Path:
    """Location of the daily update-check cache (~/.cache/shelley/)."""
    base = os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache")
    return Path(base) / "shelley" / "update_check.json"


def _read_cache() -> str | None:
    """Return the cached 'latest' version if the cache is fresh, else None."""
    try:
        data = json.loads(_cache_path().read_text())
        if time.time() - float(data["checked_epoch"]) < _CACHE_TTL:
            return data.get("latest")
    except Exception:
        pass
    return None


def _write_cache(latest: str | None) -> None:
    try:
        path = _cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"checked_epoch": time.time(), "latest": latest}))
    except Exception:
        pass


def fetch_main_version() -> str | None:
    """Fetch and parse __version__ from shelley/__init__.py on the main branch.

    Returns the version string, or None on any network/parse error.
    """
    try:
        req = urllib.request.Request(MAIN_INIT_URL, headers={"User-Agent": "shelley"})
        with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
            text = resp.read().decode("utf-8", errors="replace")
        match = _VERSION_RE.search(text)
        return match.group(1) if match else None
    except Exception:
        return None


def _is_newer(latest: str, installed: str) -> bool:
    """True if `latest` is a newer version than `installed`.

    Uses PEP 440 comparison via `packaging` when available (handles dev/pre
    releases correctly); falls back to plain string inequality otherwise.
    """
    try:
        from packaging.version import Version

        return Version(latest) > Version(installed)
    except Exception:
        return latest != installed


def check_for_update() -> str | None:
    """Return the newer version string if main is ahead, else None.

    Cached for a day and silent on any failure, so callers can invoke it
    unconditionally on user-facing screens without risk.
    """
    if os.environ.get(OPT_OUT_ENV):
        return None

    latest = _read_cache()
    if latest is None:
        latest = fetch_main_version()
        _write_cache(latest)  # cache misses too, to avoid re-hammering the network

    if latest and _is_newer(latest, __version__):
        return latest
    return None


def format_update_notice(latest: str) -> str:
    """Rich-markup body telling the user a newer shelley exists and how to get it.

    Returns the panel *body* only; the caller (``style.print_update_notice``)
    wraps it in a titled Panel. Kept as a plain string so this module stays free
    of any ``rich`` import.
    """
    return (
        f"[status.warning]A newer shelley is available:[/status.warning] "
        f"[version]{__version__}[/version] [muted]→[/muted] [version]{latest}[/version]\n\n"
        f"[header]To upgrade, run:[/header] [command]shelley update[/command]\n\n"
        f"[muted]More info: [link={DOCS_URL}]install guide[/link]   •   "
        f"silence this message with [command]export {OPT_OUT_ENV}=1[/command][/muted]"
    )
