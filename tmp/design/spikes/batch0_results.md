# Batch 0 spike: undoing a build around real shpc (2026-10-08)

**Script:** `spike_transaction.py` (this folder).

**Setup:**
- real shpc 0.1.33, SingularityCE and the Galaxy CVMFS mount;
- fresh scratch build roots per run, as an unprivileged user; `/apps` untouched; no shelley code modified;
- tool `seqtk`, tags `r93--0` and `r82--1` (both upstream);
- baselines built with the real shelley 0.4.0 `shpc_install`;
- run time 4 min 16 s for 28 runs, plus 2 permission edge-case runs.

**Method:** hash the whole scratch tree (paths, types, modes, symlink targets, file bytes); run a prototype `apply` (move-aside → registry entry → `shpc install` → harden → Lmod link); raise after each step; undo; re-hash and diff. For rebuilds, also `module load` the tag and run `seqtk`.

## Results

| Undo strategy | Scenario | Failure after | Tree identical after undo? | Module still loads and runs |
|---|---|---|---|---|
| **U2 pre-image** | A fresh install | entry, install, harden, link | **yes** (4/4) | n/a |
| **U2 pre-image** | B second tag of an installed tool | entry, install, harden, link | **yes** (4/4) | n/a |
| **U2 pre-image** | C rebuild of an installed tag | move-aside, entry, install, harden, link | **yes** (5/5) | **yes** (5/5) |
| **U2 pre-image** | B, with the tool dir at legacy mode `0700` | link | **yes** | n/a |
| U1 command undo | A | entry, install, harden, link | no: 2–3 empty dirs left (`local/quay.io/biocontainers`; `modulefiles/seqtk` after a link failure) | n/a |
| U1 command undo | B | entry, install, harden, link | no: 2 empty dirs left | n/a |
| U1 command undo | C | move-aside / others | yes / no (2 empty dirs) | **yes** (5/5) |
| U1 command undo | B, legacy mode `0700` | link | no: also leaves the tool dir at `0755` (harden has no inverse) | n/a |
| both | A, B, C | (no failure, committed) | n/a | **yes**; no `.aside` copies left |

## Risks from the migration plan, answered

| Risk | Finding |
|---|---|
| shpc's per-tool `.version` cannot be restored | **Not a problem.** `shpc uninstall` rewrote it to exactly its prior state in every U1 run, including B, where another tag shares it. Its content is a fixed placeholder (`please_specify_a_version_number`); what matters is whether it exists. U2 restores it regardless |
| `shpc uninstall` prunes parent directories | It prunes the directories shpc itself created, back to their prior state, in every run. It does not remove shelley-created intermediates (`local/…`, the Lmod tool dir); U1 would need explicit pruning for those |
| BioShell's `moduleDir` template patch breaks modules read through the symlink | **Low risk.** `module.lua` hard-codes absolute `wrapperDir` and `containerPath`; `moduleDir` is only a fallback when no wrapper base is set. Modules loaded and ran through the symlink in every check |

## Conclusion: **go** for ADR 0005, with a refined undo mechanism

- Plan-then-apply with move-aside on rebuild works around the real shpc, and a rolled-back rebuild leaves the previous module loadable.
- **Use the pre-image (U2) as `BuildTransaction`'s undo**, not per-command inverse actions:
  - it was exact in 14/14 failure cases, while U1 was exact in 1/14;
  - it does not depend on `shpc uninstall`'s pruning behaviour;
  - it also covers permission hardening and shelley-created directories.
- Cost: it reads the tool's five subtrees before `apply`. These are small text files and directories, because `--keep-path` keeps the SIF on CVMFS.
- Scope of the pre-image: shpc `modules/<uri>`, `wrappers/<uri>`, `containers/<uri>`, `local/<uri>`, and `modulefiles/<tool>`, plus new ancestors inside the build roots. The layout bootstrap and `settings.yml` stay outside the transaction (idempotent, written before `apply`).

## Not covered

- Two concurrent builds of the same tool (two users at once). The transaction needs a per-tool lock, e.g. `fcntl.flock` on `local/<uri>/.lock`. This was not tested.
- A failure *during* undo (e.g. a full disk). ADR 0005 already says undo failures are reported, not hidden.
- A real-root run under `sudo` on `/apps`. The spike ran unprivileged in scratch roots, which exercises the same code paths except the re-exec.
