# Watch list (design work, not docs)

Items Fred asked to monitor. Each entry: what was seen, when, and what would turn it into a change.

## Orphaned shpc artefacts on the dev VM

Fred (2026-10-07): leftovers from testing; monitor in case `shelley clean` needs updating.

| Time (UTC) | `/apps/shpc/modules` | `/apps/shpc/wrappers` | `/apps/local` entries | Lmod symlinks under `/apps/Modules/modulefiles` |
|---|---|---|---|---|
| 2026-10-07 ~04:40 | 9 `module.lua` across 7 tools (fastqc had a version dir + `.version` but no `module.lua`) | not checked | `last`, `star-fusion` | none |
| 2026-10-07 05:04 | tree below `quay.io/biocontainers/` gone | `last`, `ngsfetch`, `samtools`, `seqtk`, `star`, `star-fusion` (version dirs with `99-shpc.sh` + `bin/`) | `last`, `star-fusion` | none |
| 2026-10-07 10:38 | none | unchanged: `last`, `ngsfetch`, `samtools`, `seqtk`, `star`, `star-fusion` | `last`, `star-fusion` | none |
| 2026-10-08 04:54 (after the opt-in smoke run) | 12 regression tools built by the new path, all linked | orphans left: `last` (3 tags), `ngsfetch`, `samtools/1.24--h9dcdb79_1`, `seqtk` (2 tags). The `star` and `star-fusion` orphans were absorbed by real builds of the same tags | legacy `star-fusion` entry replaced by an authored one; `last` legacy entry still present | 12 tools |
| 2026-10-13 (status review) | empty | `wrappers/` dir absent: all orphans gone (`last`, `ngsfetch`, `samtools`, `seqtk`) | empty (legacy `last` entry gone) | no shpc tools; only site modules. Residue: empty-looking `containers/quay.io/biocontainers/fastqc/` dir (pre-dates redesign, Sep 24) | 
| 2026-10-13 00:55 (3a check: default `build seqtk` then new `clean`) | `seqtk/r93--0` only (built 00:36 by Fred) | `seqtk/r93--0` only | empty | `seqtk/r93--0.lua`. No 1.5 residue after a real `clean` |

Something removed the modules tree between the two snapshots (not shelley's design work; likely manual testing).

**Would require a `clean` change if:** after a `shelley clean <tool>:<tag>` (not a manual `rm`), any of these remain for that tag:
- `wrappers/quay.io/biocontainers/<tool>/<tag>/`
- `modules/quay.io/biocontainers/<tool>/<tag>/` or an orphan `.version`
- a local registry entry/marker for a tag no longer installed

Relevant code: `CVMFSModuleBuilder.uninstall_module` relies on `shpc uninstall --force` for modules/wrappers/containers and only checks Lmod symlinks itself (`shelley/builder/cvmfs_builder.py:592-721`). A tool whose Lmod symlink is already gone cannot be targeted by `clean` at all, because `_resolve_installed_version` lists only Lmod modulefiles (`shelley/commands/clean.py:27-50`).

**Design outcome (2026-10-07):** Fred ruled that orphans must not be produced in the first place, so `clean` will not target them (ADR 0005). These dev-VM leftovers stay as Tier 0 bug artefacts; remove them by hand when convenient. The `star-fusion` local entry will be removed by the next build of that tool under the target design (legacy-entry rule, ADR 0006).
