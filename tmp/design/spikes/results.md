# Spike results: partial-failure defects (2026-10-07)

Script: `spike_partial_failures.py` (this folder). Run as an unprivileged user against the real shpc 0.1.33, SingularityCE and the Galaxy CVMFS mount, with every build root redirected to a scratch directory. `/apps` was not touched and shelley code was not modified. Tool: `seqtk:r93--0` (3.5 MB, a tag that is in the upstream shpc-registry).

## A. Cancelling `build -i` on an installed tag destroys the module (reproduced)

| Step | Lmod symlink | resolves | shpc `module.lua` | wrappers | local registry |
|---|---|---|---|---|---|
| normal build | yes | yes | yes | `seqtk` + 6 shpc helpers | none |
| rebuild `-i`, alias prompt cancelled (`ValueError`) | yes | **no** | **removed** | **none** | `container.yaml` (upstream copy) left behind |

Cause: `shpc_install` runs `shpc uninstall --force` (`cvmfs_builder.py:532`) before `_ensure_local_registry_entry` reaches the prompt (`:370-378`). On a shared VM, one user's cancelled prompt makes the module unloadable for everyone.

## B. With the network down, a build "succeeds" with no tool command (reproduced, and persists)

All HTTP(S) was routed to a dead proxy (`127.0.0.1:9`), which simulates no egress.

1. The upstream lookup returned `{}`, so `in_upstream=False` for a tag that *is* upstream (`cvmfs_builder.py:93-97`, `:521-524`).
2. Alias discovery failed silently, because the shpc-guts `git clone` failed and `extract_aliases` returns `[]` (`guts_integration.py:118-119`).
3. The user saw "Tag not in registry … is not in the upstream shpc-registry" (false) and "No aliases" (true, but the cause was not stated). There was no mention of the network.
4. The build returned success. The module loads but has **no `seqtk` wrapper**, only the shpc helper wrappers.
5. A local entry (`aliases: []`) and a marker (`in_upstream: false`) were written.
6. **Persistence:** after the network was restored, rebuilding the same tag *still* produced no `seqtk` wrapper. The local registry is first in shpc's search path, so the bad entry shadows upstream. The recovery is `shelley clean`, which deletes the tag because the marker says it was not upstream.

Fred's requirement (2026-10-07): a build must be robust to the network being down, and must say that the network is down.

## Not reproduced / not attempted

- A failure between `shpc install` and the symlink (ShpcInst → Orphan). The code path is clear and orphans exist on the dev VM, but they came from testing. Not forced.
