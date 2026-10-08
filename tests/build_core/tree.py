"""Exact tree snapshots for "nothing changed" assertions"""

import hashlib
import os
import stat
from pathlib import Path

IGNORED = {".locks"}  # BuildTransaction's lock files: persistent bookkeeping


def snapshot(*roots: Path) -> dict:
    """path -> (type, mode, symlink target or sha256) for every path under ``roots``."""
    out = {}
    for root in roots:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames[:] = [d for d in dirnames if d not in IGNORED]
            for name in dirnames + filenames:
                p = Path(dirpath) / name
                st = p.lstat()
                key = str(p)
                if stat.S_ISLNK(st.st_mode):
                    out[key] = ("link", None, os.readlink(p))
                elif stat.S_ISDIR(st.st_mode):
                    out[key] = ("dir", stat.S_IMODE(st.st_mode), None)
                else:
                    digest = hashlib.sha256(p.read_bytes()).hexdigest()
                    out[key] = ("file", stat.S_IMODE(st.st_mode), digest)
    return out


def changes(before: dict, after: dict) -> list[str]:
    return [
        k for k in sorted(set(before) | set(after)) if before.get(k) != after.get(k)
    ]
