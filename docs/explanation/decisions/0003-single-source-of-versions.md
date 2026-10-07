# 0003: One source of versions: the snapshot plus a live check

- **Status:** accepted
- **Date:** 2026-10-07
- **Deciders:** Fred Jaya

## Context and problem statement

`find` reads versions from the bundled Galaxy snapshot
([find.py:58](../../../shelley/commands/find.py#L58)). `build` lists the live mount
directory, all 125k entries, on every build
([cvmfs_builder.py:210](../../../shelley/builder/cvmfs_builder.py#L210)). Their views
differ: the snapshot dated 2026-07-21 is 3,088 entries behind the mount. A user can be
shown one thing and get another (N2).

## Decision drivers

Correctness (rank 1); operability (rank 5): listing the mount takes about 4 s per build;
read-only commands must work without the mount where possible (C10).

## Considered options

1. Always list the live mount.
2. Use only the snapshot.
3. **The snapshot for listing; a live `stat` of the chosen SIF at build time; a full live
   listing only when a requested tag is missing from the snapshot.**

## Decision outcome

**Chosen: 3**, held in one place: `GalaxyCatalogue`. The snapshot refresh moves from
monthly to **fortnightly** (Fred).

### Evidence

Over the snapshot's 11 weeks, the mount gained 3,088 entries (about 280 a week) and lost
**none**. A stale snapshot therefore misses new tags but never lists a tag that is gone,
and the live `stat` guards against the case where it ever does.

### Consequences

- Good: `find` and `build` agree; a default build needs one `stat` instead of a 4 s
  listing; `find` keeps working without the mount.
- Bad: `find` cannot show tags newer than the last refresh (at most about two weeks with
  the fortnightly cadence). `build tool/<new tag>` still works through the live
  fallback.

## Rejected alternatives

- **1:** about 4 s per `find`, and the read-only commands need the mount.
- **2:** a build of a tag added since the refresh would fail, and a removed tag (not
  observed so far) would only fail inside shpc.

## Principles and patterns

Repository (Cosmic Python ch. 2) with an in-memory fake for tests.

## What would reverse this decision

- Evidence that the Galaxy mount *removes* entries. Then `find` should mark snapshot
  rows it cannot verify, or the refresh should run more often.
- Fortnightly CI refreshes that cannot be reviewed and released at that pace. Then move
  to a live listing cached per VM.
