"""Spike: reproduce two inferred build defects against real shpc + CVMFS, in a scratch layout.

Usage (from the shelley repo root, as an unprivileged user):
    .venv/bin/python tmp/design/spikes/spike_partial_failures.py cancel  <scratch-dir>
    .venv/bin/python tmp/design/spikes/spike_partial_failures.py offline <scratch-dir>

cancel  -> build seqtk:r93--0 normally, then rebuild with interactive=True and simulate
           the user cancelling the alias prompt. Expect (inferred): Lmod symlink left
           dangling because shpc uninstall ran before the prompt.
offline -> build seqtk:r93--0 with every HTTP(S) request routed to a dead proxy.
           Expect (inferred): "not in upstream" assumed, guts fails, module has no
           wrappers, and nothing says the network is down.

All build roots are redirected via SHELLEY_* env vars; /apps is never touched.
Does not modify shelley; monkeypatches one function in-process for the cancel case.
"""

import os
import sys
from pathlib import Path

TOOL, TAG = "seqtk", "r93--0"
URI = f"quay.io/biocontainers/{TOOL}"


def setup(scratch: Path) -> None:
    os.environ["SHELLEY_SHPC_BASE"] = str(scratch / "shpc")
    os.environ["SHELLEY_LOCAL_REGISTRY"] = str(scratch / "local")
    os.environ["SHELLEY_LMOD_MODULES_PATH"] = str(scratch / "modulefiles")


def state(label: str, scratch: Path) -> None:
    link = scratch / "modulefiles" / TOOL / f"{TAG}.lua"
    module = scratch / "shpc/modules" / URI / TAG / "module.lua"
    wrappers = scratch / "shpc/wrappers" / URI / TAG / "bin"
    reg = scratch / "local" / URI
    print(f"--- state: {label}")
    print(f"  lmod symlink exists={link.is_symlink()} resolves={link.is_file()}")
    print(f"  shpc module.lua exists={module.exists()}")
    print(f"  wrappers={sorted(p.name for p in wrappers.iterdir()) if wrappers.is_dir() else 'none'}")
    print(f"  local registry files={sorted(str(p.relative_to(reg)) for p in reg.rglob('*')) if reg.is_dir() else 'none'}")


def main() -> None:
    scenario, scratch = sys.argv[1], Path(sys.argv[2]).resolve()
    setup(scratch)

    from shelley.builder import cvmfs_builder as cb
    from shelley.builder.shpc_settings import ensure_shared_shpc_settings
    from shelley.utils.modules import load_build_modules
    from shelley.utils.perms import apply_build_umask, ensure_shared_layout

    apply_build_umask()
    load_build_modules()
    ensure_shared_layout()
    ensure_shared_shpc_settings()
    b = cb.CVMFSModuleBuilder()

    if scenario == "cancel":
        b.shpc_install(TOOL, TAG)
        state("after normal build", scratch)

        def cancelled(_aliases):
            raise ValueError("Alias selection cancelled.")  # what questionary cancel raises

        cb.edit_aliases_interactive = cancelled
        try:
            b.shpc_install(TOOL, TAG, interactive=True)
        except Exception as e:
            print(f"  rebuild -i raised: {type(e).__name__}: {e}")
        state("after rebuild -i, prompt cancelled", scratch)

    elif scenario == "offline":
        dead = "http://127.0.0.1:9"  # nothing listens on the discard port
        for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "all_proxy"):
            os.environ[k] = dead
        os.environ.pop("NO_PROXY", None)
        os.environ.pop("no_proxy", None)
        cfg = cb._load_registry_config(URI, scratch / "probe.yaml", force_upstream=True)
        print(f"  upstream lookup while offline returned: {cfg!r} -> in_upstream={TAG in cfg.get('tags', {})}")
        try:
            path = b.shpc_install(TOOL, TAG)
            print(f"  build returned normally: {path}")
        except Exception as e:
            print(f"  build raised: {type(e).__name__}: {str(e)[:400]}")
        state("after offline build", scratch)
    else:
        sys.exit(f"unknown scenario {scenario}")


if __name__ == "__main__":
    main()
