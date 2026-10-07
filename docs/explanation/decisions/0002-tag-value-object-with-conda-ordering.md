# 0002: A `Tag` value object with conda version ordering

- **Status:** accepted
- **Date:** 2026-10-07
- **Deciders:** Fred Jaya

## Context and problem statement

Container tags (`1.21--h50ea8bc_3`) are passed around as bare strings. `find` and `build`
order them with different functions
([cache.py:16](../../../shelley/utils/cache.py#L16),
[cvmfs_builder.py:165](../../../shelley/builder/cvmfs_builder.py#L165)) and pick a
different "latest" for 331 tools. This is the Tier 0 silent wrong-version match (T1).
`find` also matches installed versions by prefix ([find.py:30](../../../shelley/commands/find.py#L30)),
so `1.1` reads as installed when only `1.10` is (T4). Which ordering is right?

## Decision drivers

Correctness (rank 1); one rule shared by every command; tags are not PEP 440, so
`packaging.version` does not fit.

## Considered options

1. `find`'s `_version_key` (leading digits only).
2. `build`'s `_parse_version` (every number, with ASCII for letters).
3. **conda's `VersionOrder`** applied to the version part, which is the rule Bioconda itself
   uses to resolve versions.

## Decision outcome

**Chosen: 3**, wrapped in a frozen `Tag` dataclass with these properties:
- `version`: the leading `v` is normalised away, so `1.0` and `v1.0` are equal;
- `is_release`: `latest`, `broken` and `date.*` are never chosen as latest;
- `matches(requested)`: an exact tag or exact version, never a prefix;
- `latest()`: raises `TagRequired` for `mulled-*` containers, whose tags are content
  hashes with no order.

### Evidence

From the offline spike over the bundled snapshot: of the 331 disagreements, 271 are
`mulled-*`. On the 45 named-tool cases with a clear answer, conda ordering is right in
**43**, `build`'s rule in 36 and `find`'s in 8.

### Consequences

- Good: `find`'s top row and `build`'s default are the same tag; T1 and T4 are fixed at
  the type level.
- Bad: conda is not installable as a library dependency, so `conda/models/version.py` is
  vendored under `shelley/_vendor/` with its BSD-3-Clause notice. Two tools with `pN`
  patch suffixes (`bracken 3.1p1`, `dazz_db 1.0p2`) order as pre-releases; this was
  accepted.
- Bad: `mulled-*` users must name a tag; the error lists the tags available.

## Rejected alternatives

- **1:** right in 8 of 45 cases, and ties at the top in 246 tools.
- **2:** ranks `latest`, `broken` and `r93` above real versions, and pre-releases above
  finals (`2.0rc6` > `2.0.6`).
- **Newest by build date for `mulled-*`:** "latest" would mean something different for
  some tools than for all others, so it was rejected in favour of an explicit tag.

## Principles and patterns

Value Object; Replace Primitive with Object (Fowler); Fluent Python ch. 5 (data class
builders) and ch. 11 (a Pythonic object).

## What would reverse this decision

- A tool whose users rely on a `pN` patch being newest. Then add a shelley-specific rule
  for `pN`.
- conda changing `VersionOrder` in a way Bioconda follows. Then re-vendor it and re-run
  the spike (`tmp/design/spikes/q2_version_order.py` in the design work).
