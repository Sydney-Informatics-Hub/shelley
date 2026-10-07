# Watch list (design work, not docs)

Items Fred asked to monitor. Each entry: what was seen, when, and what would turn it into a change.

## Orphaned shpc artefacts on the dev VM

Fred (2026-10-07): leftovers from testing; monitor in case `shelley clean` needs updating.

| Time (UTC) | `/apps/shpc/modules` | `/apps/shpc/wrappers` | `/apps/local` entries | Lmod symlinks under `/apps/Modules/modulefiles` |
|---|---|---|---|---|
| 2026-10-07 ~04:40 | 9 `module.lua` across 7 tools (fastqc had a version dir + `.version` but no `module.lua`) | not checked | `last`, `star-fusion` | none |
| 2026-10-07 05:04 | tree below `quay.io/biocontainers/` gone | `last`, `ngsfetch`, `samtools`, `seqtk`, `star`, `star-fusion` (version dirs with `99-shpc.sh` + `bin/`) | `last`, `star-fusion` | none |

Something removed the modules tree between the two snapshots (not shelley's design work; likely manual testing).

**Would require a `clean` change if:** after a `shelley clean <tool>:<tag>` (not a manual `rm`), any of these remain for that tag:
- `wrappers/quay.io/biocontainers/<tool>/<tag>/`
- `modules/quay.io/biocontainers/<tool>/<tag>/` or an orphan `.version`
- a local registry entry/marker for a tag no longer installed

Relevant code: `CVMFSModuleBuilder.uninstall_module` relies on `shpc uninstall --force` for modules/wrappers/containers and only checks Lmod symlinks itself (`shelley/builder/cvmfs_builder.py:592-721`). A tool whose Lmod symlink is already gone cannot be targeted by `clean` at all, because `_resolve_installed_version` lists only Lmod modulefiles (`shelley/commands/clean.py:27-50`).
