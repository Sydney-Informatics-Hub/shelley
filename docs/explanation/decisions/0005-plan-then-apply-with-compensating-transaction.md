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
   - `apply` runs inside `BuildTransaction`, a context manager that records an undo
     action for each write and runs them in reverse unless `commit()` is reached.
   - Rebuilding an installed tag first moves the existing install aside, and the undo
     moves it back.
3. Keep builds as they are, and make `clean` able to find and remove orphans, or provide
   a cleanup tool.

## Decision outcome

**Chosen: 2.** `clean` targets only `LINKED` and `DANGLING` tags, and there is no cleanup
tool.

### Consequences

- Good: the only path that keeps changes is total success followed by `commit()`. A
  cancelled prompt or a network failure writes nothing, and a failed rebuild restores
  the previous install.
- Good: the guarantee is testable. Phase 8 injects a failure at each `apply` step and
  asserts that `/apps` is unchanged.
- Bad: the filesystem is not transactional. Undo is compensation, so an undo can itself
  fail (e.g. if the disk is full). Undo failures are logged and reported, not hidden.
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
- Undo failures showing up in practice on BioShell VMs. Then add a recovery check to
  `find`.
