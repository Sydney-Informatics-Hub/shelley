# 0006: The local registry holds shelley-authored entries only

- **Status:** accepted
- **Date:** 2026-10-07
- **Deciders:** Fred Jaya

## Context and problem statement

`/apps/local/<uri>/container.yaml` plays two roles: a best-effort cache of the upstream
shpc-registry entry, and a shelley-authored entry for tags absent upstream or curated
with `-i` ([glossary](../../reference/architecture/glossary.md#registry-registry-entry-marker-directory)).
Several problems follow from that:
- The dual role is why `uninstall_module` needs a 48-line docstring
  ([cvmfs_builder.py:593-639](../../../shelley/builder/cvmfs_builder.py#L593-L639)).
- shpc uses the first registry entry it finds by name and exits if the tag is missing
  (`[code]` `shpc/main/registry/__init__.py:63-76`, `shpc/main/modules/module.py:44-53`),
  so any local entry shadows upstream for every tag of its tool.
- Each local entry also records `sha256` of the whole SIF, which reads up to 9.6 GB
  through a 4 GB CVMFS cache.

## Decision drivers

Correctness (rank 1); shared-VM safety (rank 2); operability (rank 5). With fail-fast
([ADR 0004](0004-fail-fast-when-network-unavailable.md)), no offline cache is needed.

## Considered options

1. Keep the dual role.
2. **Authored entries only.** On each build of a tool that has a local entry, merge the
   fresh upstream tags into it. Remove an entry that no `LINKED` tag uses and that has no
   marker (a legacy artefact). Write the tag value `local:keep-path` instead of a SIF
   hash.
3. Authored entries only, plus a `shelley-registry-cleanup` admin command for legacy
   entries.

## Decision outcome

**Chosen: 2.**

### Consequences

- Good: a curated `-i` entry no longer blocks builds of newer upstream tags of the same
  tool. Legacy entries from ≤ 0.4.0 Tier 0 bugs are repaired by the next build of that
  tool, with no admin step. `clean` loses the cache bookkeeping.
- Good: no full-SIF read. shpc ignores the tag value when installing with `--keep-path`
  and a local image (`[code]` `shpc/main/modules/module.py:99-109`), and its schema
  accepts any string (`[code]` `shpc/main/schemas.py:13-18`).
- Bad: a module built offline under T6 that is still `LINKED` is not repaired
  automatically. The fix is `shelley clean <tool>:<tag>` and a rebuild.
- Bad: an entry's `aliases` field is still shared by every tag in it (an shpc schema
  limit); the marker snapshot keeps each tag's own aliases, as today.

## Rejected alternatives

- **1:** it keeps both the bookkeeping and the stale-shadow failure.
- **3:** Fred: shelley should not produce such entries in the first place, so a cleanup
  tool treats a symptom.
- **Removing unused entries only (no merge):** a legitimate `-i` entry would still shadow
  upstream.

## Principles and patterns

Information hiding and pulling complexity down (Ousterhout ch. 4–5).

## What would reverse this decision

- shpc changing its registry lookup to fall through to the next registry when a tag is
  missing. Then the merge step is unnecessary.
- A need to verify SIF integrity at build time. Then hash on demand (`-v`) rather than on
  every build.
