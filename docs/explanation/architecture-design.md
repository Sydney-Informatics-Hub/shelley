# Architecture design

The entry point to shelley's 2026 architecture review: what was found, what was decided,
and what happens next. It starts with a one-page summary for the product owner; the rest
links to the detailed pages.

---

## Summary for the product owner

**What shelley does.** It helps BioShell users find bioinformatics tools on the Galaxy
CVMFS mount and turn them into `module load`-able modules shared by everyone on the VM.

**What we found.** shelley works for the common case, but three of its bugs give users
wrong results without telling them:

1. **Wrong version.** `shelley find` and `shelley build` disagree about which version is
   "latest" for 331 tools. A user can be shown one version and get another.
2. **Broken modules when the network drops.** If GitHub can't be reached during a
   build, shelley reports success but the module is missing the tool's command, and
   the problem persists after the network comes back. Every user on the VM gets that
   broken module.
3. **Leftovers after a failed build.** A build that fails part-way can leave files
   behind that nothing can clean up. In a related bug, cancelling a prompt while
   rebuilding a tool deletes it for every user. On a training VM, such damage can be
   copied into the saved image.

All three were reproduced on a real BioShell VM. Most of the code sits in one 700-line
class, so every fix touches the same file, and adding a new source of software would
touch 10 files.

**What we decided.** We will split shelley into two parts:
- one that **finds** software, which runs as the user and never needs a password;
- one that **installs** it, which runs as root, prepares everything first, and undoes
  its work if anything fails.

Version ordering will follow the same rule Bioconda uses. If the network is down, the
build stops before changing anything and says so in plain words. Seven decision records
explain each choice and what would make us revisit it.

**What users will notice.**
- Builds either fully succeed or change nothing.
- Errors such as a mistyped version appear **before** the password prompt.
- A batch of builds asks for the password once.
- For 35 tools, the version a plain `shelley build` installs changes to the genuinely
  newest one; `find` reorders its list for 57.
- 575 multi-tool `mulled-*` containers need an explicit version.

**Plan and dates.** The PO's priority, build, comes first:

| Release | What | When (approx.) |
|---|---|---|
| 0.5.0 | New build available to try (opt-in) | early Nov 2026 |
| **0.6.0** | **New build for everyone: the three Tier 0 bugs fixed** | **mid-Nov 2026** |
| 0.7.0 | `find`, `search` and `clean` on the new design; "latest" agrees everywhere | end Nov 2026 |
| 0.8.0 | Old code removed | mid-Dec 2026, before the January image bump |

The new code is built alongside the old and switched on only once proven, so each
release can be rolled back. About 7 weeks of engineering time in total, delivered as
six moderate PRs, each reviewable in one sitting.

**Later, not scheduled.** EESSI (versioned R with Bioconductor) and Galaxy reference
data (genomes and indices) fit this design at a cost of 1–3 new modules each. Early
evidence: EESSI's R 4.5.2 bundle already contains DESeq2 and Seurat.

---

## All artefacts

| Diátaxis type | Page | What it holds |
|---|---|---|
| Reference | [glossary.md](../reference/architecture/glossary.md) | Agreed vocabulary and current term usage |
| Reference | [current-state.md](../reference/architecture/current-state.md) | As-is class, package, deployment, sequence and lifecycle diagrams; the responsibility table; Galaxy/shpc assumptions |
| Reference | [target-state.md](../reference/architecture/target-state.md) | To-be diagrams in the same style; module move map; target measures |
| Reference | [traceability.md](../reference/architecture/traceability.md) | Driver × module matrices, as-is and to-be |
| Explanation | [architecture-drivers.md](architecture-drivers.md) | The as-is design review (rubric, smells, pattern forces) and the ranked drivers |
| Explanation | [architecture-evaluation.md](architecture-evaluation.md) | Seven scenarios through both designs |
| Explanation | [decisions/0001](decisions/0001-split-discovery-from-exposure.md) to [0007](decisions/0007-resolve-before-elevating.md) | The design decisions (ADRs) |

Working material, not published docs (`tmp/design/`, uncommitted):
- the migration plan and test seams;
- the spike scripts and results (offline build, cancelled rebuild, version ordering);
- the integration-discovery notes;
- the design rounds;
- the draft multi-supplier design (EESSI and reference data);
- the orphan watch list.

## Decisions still owed

| # | Decision | Owner | Needed by |
|---|---|---|---|
| 1 | Commit `tmp/design/` (as design-work) or keep it local; whether to gitignore `tmp/` | Fred | Before the batch 1 PR |
| 2 | Link the Tier 0 GitHub issues Fred created to the drivers (T1, T2, T6) | Fred | Before the batch 1 PR |
| 3 | Q5: what users see when the Galaxy Stratum 1 is unreachable (spike on a disposable VM) | Fred | Before batch 3a (switch build) |
| 4 | Q6: widen `search`'s join to `bioconductor-`/`r-` containers (+~1,300 tools)? | Fred / PO | Deferred; revisit with the R work |
| 5 | EESSI: exposure option (X1/X2/X3), the user-facing verb, and the EESSI version policy | Fred / PO | When EESSI is scheduled, after the D-Q1 PoC spike |
| 6 | Reference data: paths only, or `ref/<build>` modulefiles | Fred | When data is scheduled |
| 7 | BioShell PR adding `software.eessi.io` to the image (today hand-configured on the dev VM) | Fred | With the EESSI work |

## Risks register

| # | Risk | Likelihood | Impact | Mitigation | Trigger to act |
|---|---|---|---|---|---|
| R1 | The build undo cannot restore shpc's per-tool `.version` file exactly (shpc rewrites it on install *and* uninstall) | Medium | High: the undo would leave a wrong default version | Batch 0 spike first; fallback "install to staging, then rename" (ADR 0005) | Spike shows a tree-hash mismatch |
| R2 | Review capacity drops below one moderate PR a fortnight | Medium | Medium: the schedule slips | Option A fallback: stop after build, since all Tier 0s are fixed by 0.6.0 | Two PRs waiting > 2 weeks |
| R3 | Estimates are low (6 units a week assumed; 40 units total) | Medium | Medium | Batch order puts the PO's priority (build) first; batches 4–5 can slip without user harm | Batch 2 takes > 12 units |
| R4 | Legacy registry entries on deployed VMs behave differently from the dev VM sample (2 entries) | Low | Medium: a build on an old VM fails or keeps a bad entry | The merge/remove rule is tested with fixture entries; the opt-in period on real VMs (0.5.0) | A report during the opt-in |
| R5 | The Galaxy mount starts removing entries (the "append-only" basis of ADR 0003) | Low | Medium: `find` lists versions that cannot be built | The live `stat` at build time still catches it; refresh fortnightly | A removal seen in the refresh diff |
| R6 | Vendored conda `VersionOrder` drifts from conda upstream | Low | Low | Pinned copy with a source URL; re-run the ordering spike on refresh | Bioconda reorders a tool |
| R7 | The interim T1 gap: `find` and `build` disagree between 0.6.0 and 0.7.0 (about 3 weeks) | Certain | Low | Accepted by Fred; short window | — |
| R8 | The CVMFS cache (4 GB, 3.6 GB used on the dev VM) is too small for EESSI R bundles | High (when EESSI starts) | High: slow first loads, evictions | Measure in the D-Q1 spike; raise `CVMFS_QUOTA_LIMIT` in BioShell if needed (root disk about 16 GB free) | Spike shows evictions |
| R9 | EESSI `R` conflicts with BioShell's `R/4.3.3` module | Certain (when exposed) | Medium | Prefer exposure option X2 (lowercase `r/<ver>` wrappers) | Choosing X1 |
| R10 | Mermaid diagrams contain a syntax error that only shows when rendered | Medium | Low | Hand-checked; validation skipped by Fred's choice | A diagram fails to render on GitHub |
