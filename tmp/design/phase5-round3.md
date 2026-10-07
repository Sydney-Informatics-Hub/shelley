# Phase 5, round 3: closing Option C

Fred (2026-10-07): "shelley and BioShell shouldn't produce orphaned tags in the first place." `shelley-registry-cleanup` is omitted. The `star-fusion` entry is an artefact of the Tier 0 bugs.

## Diff summary since round 2

| # | Change | Replaces |
|---|---|---|
| R3-1 | **No orphan handling in `clean`.** `TagState` = `AVAILABLE`, `LINKED`, `DANGLING`. `DANGLING` stays, because a link target can be deleted outside shelley; that is what today's `clean` already handles (`find.py:33-43`) | R2-6 (`ORPHANED` and `clean` accepting it) |
| R3-2 | **The guarantee moves to the build.** `BuildTransaction` (K3) and plan-then-apply (K2) are the only defence against orphans. Phase 8 adds a failure-injection test at every `apply` step, asserting that `/apps` is byte-identical to before | the cleanup command as a safety net |
| R3-3 | **`shelley-registry-cleanup` removed.** The content-based classification (R2-3) is dropped with it | R2-2, R2-3 |
| R3-4 | **Legacy local entries** (written by ≤ 0.4.0 under the Tier 0 bugs, e.g. `star-fusion`) are not preserved or migrated. `plan` still detects a local entry that shadows an upstream tag (R2-4, backed by `[code]`), because otherwise shpc fails with "is not a known identifier", which is opaque. Its message names the file. How a VM gets rid of these entries is open (R3-Q2) | R2-4's "ask an admin to run …" |
| R3-5 | The traceability rows "K8 registry migration" and the `ADM` column are removed; nothing else changes. All in-scope drivers are still served | round 2 matrix |

## R3-Q1 (elaborated): how the root child learns which tag to build

`build` runs as **two processes**. The parent runs as the user. When `/apps` is not writable, it re-runs shelley under `sudo` as a **root child**, and the child does the installing (`build.py:93-124`).

**Today:**
- The parent passes the raw user text (`samtools/1.21`) to the child.
- The child re-parses it and re-resolves it by listing the 125k-entry mount again.

That causes three problems:
1. Bad input is only caught *after* the sudo password prompt (`clean` already resolves first, `clean.py:83-117`; `build` does not).
2. The resolution work is done again, as root.
3. In principle, the child can pick a different tag from the one the parent would have shown, e.g. if the mount changes between the two.

In Option C, the parent resolves the tag first, as the user, using the catalogue. The question is how to hand the result to the root child.

| | **A. Hidden flag (recommended)** | B. Plan file |
|---|---|---|
| What is passed | `sudo … python -m shelley build samtools --resolved-tag 1.21--h50ea8bc_3` | The parent writes a `BuildPlan` JSON file (tag, aliases, upstream entry) and passes its path |
| What the child does | Re-checks only that this exact SIF exists (one `stat`), then plans (network, aliases, `-i` prompt) and applies | Reads the file, then applies |
| Security | Nothing is trusted beyond a tag string that is validated against the mount. A user crafting the flag gains nothing: a user who can sudo can already build any tag | Root acts on a file the user's process wrote. The file must be created safely and validated field by field, or a tampered plan (e.g. altered aliases or paths) is executed as root |
| New state on disk | None | A temp file per build, which needs cleanup on every exit path |
| Help text | The flag is accepted but not listed in `--help` | none |
| When B would win | — | If the network and prompt work moved to the parent, so that the child needs the whole plan. Not proposed: the child already owns the TTY for `-i` prompts today |

Recommendation: **A**. Its single cost is a hidden flag in the command table.

## Open questions

| # | Question | Recommendation |
|---|---|---|
| R3-Q1 | Hidden flag (A) or plan file (B)? | A |
| R3-Q2 | Legacy local entries on deployed VMs (≤ 0.4.0 Tier 0 artefacts): should `plan` (i) stop with a message naming the file to delete, (ii) delete the entry itself inside the transaction when it is not referenced by any `LINKED` tag, or (iii) neither, since BioShell images are rebuilt every six months and existing VMs are short-lived? | (ii) keeps "no admin step" and fixes the VM in place; (iii) is cheapest if few VMs carry such entries |

## Convergence check

All criteria hold as in round 2, with the cleanup tool and the orphan state removed. Outstanding: R3-Q1, R3-Q2 and Fred's sign-off.

## Decisions (Fred, 2026-10-07): design done

- **R3-Q1:** hidden `--resolved-tag` flag (A).
- **R3-Q2:** option (ii), refined while writing `target-state.md`. Removing an unused entry is not enough, because a legitimate `-i` entry also shadows upstream for *every* tag of its tool (shpc matches by name first). So on each build of a tool with a local entry, `plan` merges the fresh upstream tags into it. An entry that no `LINKED` tag uses and that has no marker is removed instead. T6 artefacts still in use are fixed by `clean` and a rebuild.
- **Batch:** in the target design, all specs are resolved first and the build elevates once (a single sudo prompt). Unresolvable specs still fail individually while the others build, as today.
- The final design is in `docs/reference/architecture/target-state.md`.
