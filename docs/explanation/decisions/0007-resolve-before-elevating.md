# 0007: Resolve before elevating, and pass the tag with a hidden flag

- **Status:** accepted
- **Date:** 2026-10-07
- **Deciders:** Fred Jaya

## Context and problem statement

`build` runs as two processes. The parent runs as the user. When `/apps` is not writable,
it re-runs shelley under `sudo` as a root child, which does the install
([build.py:93-124](../../../shelley/commands/build.py#L93-L124)). Today the parent passes
the raw spec (`samtools/1.21`), and the child re-parses it and re-lists the 125k-entry
mount. This has three effects:
- a bad spec is reported only after the sudo password prompt (`clean` already resolves
  first, [clean.py:83-117](../../../shelley/commands/clean.py#L83-L117));
- resolution runs twice;
- in principle, the child can pick a different tag from the one the user was shown.

## Decision drivers

Least astonishment; correctness (rank 1); shared-VM safety (rank 2): root should act only
on validated input.

## Considered options

1. Keep re-resolving in the child.
2. **The parent resolves the tag, and passes it as a hidden `--resolved-tag <tag>` flag.**
   The child re-checks only that this exact SIF exists, then plans and applies.
3. The parent writes a `BuildPlan` JSON file, and the child reads and applies it.

## Decision outcome

**Chosen: 2.** The flag is accepted by the command table but not listed in `--help`.
`clean` uses the same flag. A batch resolves every spec first, then elevates once; specs
that fail to resolve still fail individually, as today.

### Consequences

- Good: a mistyped tool or version, a missing mount, or a mulled container without a tag
  is reported before any sudo prompt. Root does exactly what the user was shown.
- Good: one sudo prompt per batch instead of one per spec.
- Bad: one hidden flag to maintain and test.

## Rejected alternatives

- **1:** password first, then the error; resolution done twice.
- **3:** root would act on a file the user's process wrote. It would need safe creation,
  validation of every field, and cleanup on every exit path, and a tampered plan (aliases,
  paths) would run as root. It would only be needed if the network and prompt work moved
  to the parent, which is not proposed: the child already owns the terminal for `-i`
  prompts.

## Principles and patterns

Split Phase (Fowler); validating at the trust boundary; Mak, user expectations *(from
memory)*.

## What would reverse this decision

- Moving alias curation (`-i`) into the unprivileged parent, so that the child needs more
  than a tag. Then revisit option 3, with a root-owned temp directory.
- sudo policy on BioShell images that strips unknown arguments (not observed).
