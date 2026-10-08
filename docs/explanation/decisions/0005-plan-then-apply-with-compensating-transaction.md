# 0005: Plan, then apply inside an undoing transaction

- **Status:** accepted
- **Date:** 2026-10-07
- **Deciders:** Fred Jaya

## Context and problem statement

A build writes four kinds of artefact: a registry entry and marker, an shpc module and
its wrappers, permission changes, and an Lmod link. It interleaves those writes with
network calls and prompts, and keeps no record of what it created
([cvmfs_builder.py:531-578](../../../shelley/builder/cvmfs_builder.py#L531-L578)).
Two consequences follow:
- A failure part-way leaves orphans (T2, Tier 0).
- Cancelling the `-i` prompt on an installed tag deletes the working module for every user
  on the VM, because `shpc uninstall` runs before the prompt (T5, reproduced).

Fred: "shelley and BioShell shouldn't produce orphaned tags in the first place."

## Decision drivers

Shared-VM safety (rank 2); honest failures (rank 3); testability (rank 4).

## Considered options

1. Reorder lines and add `try/except` cleanup in `shpc_install`.
2. **Split the build into `plan` and `apply`:**
   - `plan` does all network calls, alias discovery and prompts, writes nothing, and
     returns a frozen `BuildPlan`;
   - `apply` runs inside `BuildTransaction`, a context manager that, on entry, records a
     **pre-image** of the tool's five subtrees (shpc modules, wrappers and containers, the
     local registry entry, and the Lmod directory: paths, modes, symlink targets and file
     bytes). Unless `commit()` is reached, it restores that pre-image exactly.
   - Rebuilding an installed tag first moves the existing install aside, and the undo
     moves it back.
3. Keep builds as they are, and make `clean` able to find and remove orphans, or provide
   a cleanup tool.

## Decision outcome

**Chosen: 2.** `clean` targets only `LINKED` and `DANGLING` tags, and there is no cleanup
tool.

**Amended 2026-10-08 after the batch 0 spike** (real shpc 0.1.33, 30 runs in scratch
roots). The undo mechanism changed from per-step inverse actions (`shpc uninstall`,
unlink, …) to the pre-image restore:
- the pre-image restored the tree exactly in **14 of 14** injected failures, including a
  rebuild of an installed tag (still loadable and runnable afterwards) and a legacy tool
  directory at mode `0700`;
- per-step inverse actions were exact in only 1 of 14. `shpc uninstall` itself restored
  shpc's paths and the per-tool `.version` file correctly, but empty shelley-created
  directories were left behind, and the permission hardening could not be undone.

### Consequences

- Good: the only path that keeps changes is total success followed by `commit()`. A
  cancelled prompt or a network failure writes nothing, and a failed rebuild restores
  the previous install.
- Good: the guarantee is testable. Phase 8 injects a failure at each `apply` step and
  asserts that `/apps` is unchanged.
- Bad: the filesystem is not transactional. Undo is compensation, so an undo can itself
  fail (e.g. if the disk is full). Undo failures are logged and reported, not hidden.
- Bad: two concurrent builds of the same tool would race on the same subtrees. The
  transaction takes a per-tool lock (e.g. `fcntl.flock` on `local/<uri>/.lock`); this
  was not exercised by the spike.
- Bad: orphans left by earlier versions are not cleaned up by `clean`. See
  [target-state §5](../../reference/architecture/target-state.md#5-artefact-lifecycle-state-diagram-to-be)
  for how legacy entries are handled.

## Rejected alternatives

- **1:** fixes today's two cases, but nothing stops the next helper from writing early.
- **3:** treats the symptom; Fred rejected both a cleanup tool and orphan-aware `clean`.
- **The State pattern for the lifecycle:** no object changes behaviour by state, so an
  `Enum` (`TagState`) is enough.

## Principles and patterns

Unit of Work, used as a compensating transaction (Cosmic Python ch. 6: "only one code path
that leads to changes … total success and an explicit commit"); context managers (Fluent
Python ch. 18); Split Phase (Fowler).

## What would reverse this decision

- shpc gaining an atomic install or "install to staging, then swap". Then use it instead
  of the moving-aside.
- A tool whose subtrees become large (e.g. if `--keep-path` were dropped and SIFs were
  copied into `containers/`). Then the pre-image is too costly and per-step undo with
  explicit pruning is preferable.
- Undo failures showing up in practice on BioShell VMs. Then add a recovery check to
  `find`.
