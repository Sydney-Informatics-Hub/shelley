"""Batch 0 spike: can a build's `apply` be undone *exactly*, around the real shpc?

For each scenario and each injected failure point, this script:
  1. builds a baseline in fresh scratch build roots using the real shelley 0.4.0 code;
  2. hashes the whole scratch tree (paths, types, modes, symlink targets, file bytes);
  3. runs a prototype `apply` (move-aside, entry, shpc install, harden, link), raising
     after step k;
  4. undoes the steps with one of two strategies;
  5. re-hashes and diffs, and for the rebuild scenario checks the module still loads
     and runs.

Undo strategies:
  U1 "command undo" - the ADR 0005 sketch: each step records an inverse action (move
     back, remove the entry, `shpc uninstall --force`, unlink). Harden has no undo.
  U2 "pre-image"    - before apply, record every path under the tool's 5 subtrees
     (shpc modules/wrappers/containers, local registry entry, Lmod dir), with mode,
     symlink target and bytes; undo deletes what is new and restores what changed.

Scenarios (tool seqtk, Galaxy SIFs on CVMFS; both tags are in the upstream registry):
  A  fresh install of r93--0 into empty roots
  B  install of r93--0 when r82--1 of the same tool is already installed
  C  rebuild of an installed r93--0 (existing install moved aside first)

Read-only for shelley; never touches /apps. Run from the shelley repo root:
    .venv/bin/python tmp/design/spikes/spike_transaction.py <scratch-dir>
"""

import hashlib
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import yaml

TOOL = "seqtk"
URI = f"quay.io/biocontainers/{TOOL}"
SIF = "/cvmfs/singularity.galaxyproject.org/all/{tool}:{tag}"
STEPS = ["move_aside", "entry", "install", "harden", "link"]
LMOD_INIT = "/usr/share/lmod/lmod/init/bash"


class Injected(Exception):
    pass


# ---------------------------------------------------------------- scratch layout
def use_roots(base: Path) -> None:
    os.environ["SHELLEY_SHPC_BASE"] = str(base / "shpc")
    os.environ["SHELLEY_LOCAL_REGISTRY"] = str(base / "local")
    os.environ["SHELLEY_LMOD_MODULES_PATH"] = str(base / "modulefiles")


def subtrees(base: Path, tag: str) -> list[Path]:
    """The paths a build of TOOL:tag may create or modify."""
    s = base / "shpc"
    return [
        s / "modules" / URI,
        s / "wrappers" / URI,
        s / "containers" / URI,
        base / "local" / URI,
        base / "modulefiles" / TOOL,
    ]


def snapshot(base: Path) -> dict:
    """Exact tree state: relpath -> (type, mode, target-or-sha256)."""
    out = {}
    for root, dirs, files in os.walk(base, followlinks=False):
        for name in dirs + files:
            p = Path(root) / name
            st = p.lstat()
            rel = str(p.relative_to(base))
            if stat.S_ISLNK(st.st_mode):
                out[rel] = ("link", None, os.readlink(p))
            elif stat.S_ISDIR(st.st_mode):
                out[rel] = ("dir", stat.S_IMODE(st.st_mode), None)
            else:
                out[rel] = ("file", stat.S_IMODE(st.st_mode), hashlib.sha256(p.read_bytes()).hexdigest())
    return out


def diff(before: dict, after: dict) -> list[str]:
    lines = []
    for k in sorted(set(before) | set(after)):
        b, a = before.get(k), after.get(k)
        if b == a:
            continue
        if b is None:
            lines.append(f"  + {k}")
        elif a is None:
            lines.append(f"  - {k}")
        else:
            what = "mode" if b[0] == a[0] and b[2] == a[2] else "content"
            lines.append(f"  ~ {k} ({what}: {b[1] and oct(b[1])} -> {a[1] and oct(a[1])})")
    return lines


# ---------------------------------------------------------------- pre-image (U2)
class PreImage:
    def __init__(self, paths: list[Path], base: Path):
        self.paths, self.base = paths, base
        self.entries = {}  # path -> (type, mode, payload)
        self.existed_roots = {p: p.exists() or p.is_symlink() for p in paths}
        for top in paths:
            # record each top and every ancestor up to the build root that exists
            for p in [top, *top.parents]:
                if p == base.parent:
                    break
                if p.exists() and not p.is_symlink():
                    self.entries.setdefault(p, ("dir", stat.S_IMODE(p.lstat().st_mode), None))
            if not top.exists():
                continue
            for root, dirs, files in os.walk(top, followlinks=False):
                for name in dirs + files:
                    p = Path(root) / name
                    st = p.lstat()
                    if stat.S_ISLNK(st.st_mode):
                        self.entries[p] = ("link", None, os.readlink(p))
                    elif stat.S_ISDIR(st.st_mode):
                        self.entries[p] = ("dir", stat.S_IMODE(st.st_mode), None)
                    else:
                        self.entries[p] = ("file", stat.S_IMODE(st.st_mode), p.read_bytes())

    def restore(self) -> None:
        # 1. delete anything new (deepest first), including move-aside copies
        for top in self.paths:
            parent = top.parent
            if not parent.exists():
                continue
            for root, dirs, files in os.walk(parent, topdown=False, followlinks=False):
                for name in files + dirs:
                    p = Path(root) / name
                    if not (p == top or top in p.parents or p.name.endswith(".aside")):
                        continue
                    if p not in self.entries:
                        if p.is_dir() and not p.is_symlink():
                            shutil.rmtree(p)
                        else:
                            p.unlink()
            if top not in self.entries and (top.exists() or top.is_symlink()):
                shutil.rmtree(top) if top.is_dir() and not top.is_symlink() else top.unlink()
        # 1b. remove new, now-empty ancestors (e.g. quay.io/biocontainers created by shpc)
        for top in self.paths:
            for p in [top, *top.parents]:
                if p == self.base:
                    break
                if p not in self.entries and p.is_dir() and not any(p.iterdir()):
                    p.rmdir()
        # 2. recreate anything missing or changed, parents first
        for p, (kind, mode, payload) in sorted(self.entries.items(), key=lambda kv: len(kv[0].parts)):
            if kind == "dir":
                p.mkdir(exist_ok=True)
            elif kind == "link":
                if p.is_symlink() and os.readlink(p) == payload:
                    continue
                if p.exists() or p.is_symlink():
                    p.unlink()
                p.symlink_to(payload)
            else:
                if not p.is_file() or p.read_bytes() != payload:
                    p.write_bytes(payload)
            if mode is not None:
                os.chmod(p, mode)


# ---------------------------------------------------------------- prototype apply
def apply(base, tag, cb, gl, perms, upstream_entry, *, rebuild, fail_after, strategy):
    shpc_dir = base / "shpc"
    mods, wraps, conts = (shpc_dir / k / URI for k in ("modules", "wrappers", "containers"))
    reg = base / "local" / URI
    link = base / "modulefiles" / TOOL / f"{tag}.lua"
    undo = []
    pre = PreImage(subtrees(base, tag), base) if strategy == "U2" else None

    def step(name, fn):
        fn()
        if fail_after == name:
            raise Injected(name)

    def move_aside():
        if not rebuild:
            return
        for p in (mods / tag, wraps / tag, conts / tag, link):
            if p.exists() or p.is_symlink():
                aside = p.with_name(p.name + ".aside")
                p.rename(aside)
                undo.append(lambda p=p, aside=aside: aside.rename(p))

    def entry():
        yaml_path = reg / "container.yaml"
        created_dir = not reg.exists()
        previous = yaml_path.read_bytes() if yaml_path.exists() else None
        perms.ensure_shared_dir(reg / tag)
        cfg = dict(upstream_entry)
        cfg["tags"] = dict(cfg.get("tags", {}))
        cfg["tags"][tag] = "local:keep-path"
        yaml_path.write_text(yaml.safe_dump(cfg, sort_keys=False))
        (reg / tag / "aliases.yaml").write_text(yaml.safe_dump({"version": tag, "aliases": [], "in_upstream": True}))

        def _undo():
            if created_dir:
                shutil.rmtree(reg)
            else:
                shutil.rmtree(reg / tag, ignore_errors=True)
                if previous is None:
                    yaml_path.unlink(missing_ok=True)
                else:
                    yaml_path.write_bytes(previous)
        undo.append(_undo)

    def install():
        r = subprocess.run(cb._shpc_cmd("install", f"{URI}:{tag}", SIF.format(tool=TOOL, tag=tag), "--keep-path"),
                           capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(r.stdout + r.stderr)
        undo.append(lambda: subprocess.run(cb._shpc_cmd("uninstall", "--force", f"{URI}:{tag}"), capture_output=True))

    def harden():
        cb.CVMFSModuleBuilder()._share_build_artifacts(shpc_dir / "modules", TOOL, URI)

    def do_link():
        perms.ensure_shared_dir(link.parent)
        link.symlink_to(mods / tag / "module.lua")
        undo.append(lambda: link.unlink(missing_ok=True))

    try:
        step("move_aside", move_aside)
        step("entry", entry)
        step("install", install)
        step("harden", harden)
        step("link", do_link)
    except Injected:
        if strategy == "U1":
            for u in reversed(undo):
                u()
        else:
            pre.restore()
        return "undone"
    # commit
    for p in (mods / tag, wraps / tag, conts / tag, link):
        aside = p.with_name(p.name + ".aside")
        if aside.is_dir() and not aside.is_symlink():
            shutil.rmtree(aside)
        elif aside.exists() or aside.is_symlink():
            aside.unlink()
    return "committed"


def loads_and_runs(base: Path, tag: str) -> str:
    """module load the tag from the scratch Lmod dir and run the tool's wrapper."""
    cmd = (f"source {LMOD_INIT} && module use {base}/modulefiles && module load singularity "
           f"&& module load {TOOL}/{tag} && seqtk 2>&1 | head -2")
    r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip().replace("\n", " | ")
    return "OK" if "Usage" in out else f"FAIL: {out[:160]}"


# ---------------------------------------------------------------- driver
def main() -> None:
    scratch = Path(sys.argv[1]).resolve()
    shutil.rmtree(scratch, ignore_errors=True)
    scratch.mkdir(parents=True)
    sys.path.insert(0, ".")

    from shelley.builder import cvmfs_builder as cb
    from shelley.utils import globals as gl
    from shelley.utils import perms
    from shelley.utils.modules import load_build_modules

    perms.apply_build_umask()
    load_build_modules()
    upstream_entry = cb._load_registry_config(URI, scratch / "upstream-probe.yaml", force_upstream=True)
    assert "r93--0" in upstream_entry.get("tags", {}) and "r82--1" in upstream_entry.get("tags", {}), "need both tags upstream"

    scenarios = {
        "A fresh": ([], "r93--0", False),
        "B second tag": (["r82--1"], "r93--0", False),
        "C rebuild": (["r93--0"], "r93--0", True),
    }
    results = []
    for strategy in ("U1", "U2"):
        for sname, (baseline_tags, tag, rebuild) in scenarios.items():
            for fail_after in STEPS + [None]:
                if fail_after == "move_aside" and not rebuild:
                    continue
                base = scratch / f"{strategy}-{sname[0]}-{fail_after or 'commit'}"
                base.mkdir()
                use_roots(base)
                from shelley.builder.shpc_settings import ensure_shared_shpc_settings
                perms.ensure_shared_layout()
                ensure_shared_shpc_settings()
                for t in baseline_tags:  # baseline with the real shelley 0.4.0 build
                    cb.CVMFSModuleBuilder().shpc_install(TOOL, t)
                before = snapshot(base)
                outcome = apply(base, tag, cb, gl, perms, upstream_entry, rebuild=rebuild,
                                fail_after=fail_after, strategy=strategy)
                after = snapshot(base)
                d = diff(before, after) if outcome == "undone" else []
                load = loads_and_runs(base, tag) if (rebuild or outcome == "committed") else "-"
                results.append((strategy, sname, fail_after or "(none)", outcome, len(d), load, d[:6]))
                print(f"{strategy} | {sname:12s} | fail after {fail_after or '(none)':10s} | {outcome:9s} | "
                      f"diffs {len(d):3d} | loads {load}", flush=True)
                for line in d[:6]:
                    print("      " + line)


if __name__ == "__main__":
    main()
