# 0004: Fail fast when the network is unavailable

- **Status:** accepted
- **Date:** 2026-10-07
- **Deciders:** Fred Jaya

## Context and problem statement

`_load_registry_config` returns `{}` both when a tag is not in the upstream shpc-registry
and when GitHub is unreachable ([cvmfs_builder.py:93-97](../../../shelley/builder/cvmfs_builder.py#L93-L97)).
Alias discovery also returns `[]` on any failure
([guts_integration.py:118-119](../../../shelley/builder/guts_integration.py#L118-L119)).

A reproduction with all HTTP routed to a dead proxy (T6) showed the result. The build
"succeeded" but produced no tool command, and told the user the tag was not upstream,
which was false. It also wrote a local registry entry that kept breaking rebuilds after
the network returned.

## Decision drivers

Fred: a build must be robust to the network being down, and must say so (N1). Honest
failures (rank 3); shared-VM safety (rank 2).

## Considered options

1. **Fail fast:** detect unreachability before any write, and stop with a plain message.
2. Degrade: build from a cached copy of the upstream entry.

## Decision outcome

**Chosen: 1.**
- `tools/net.py` classifies the failure (DNS, timeout, proxy refused, HTTP error).
- `RegistryClient.fetch` and `extract_aliases` raise `NetworkUnavailable(host, reason)`.
- `ShpcExposer.plan` lets it propagate before anything is written.

The message (Fred's wording), for example: *"Couldn't reach GitHub
(raw.githubusercontent.com): the request timed out after 10 s. Try again in a few
seconds."*

### Consequences

- Good: T6 cannot recur; no wrong state is recorded; the user sees the cause.
- Bad: no offline builds, even for tags previously built on that VM.
- Bad: raw diagnostic output (e.g. `curl -sI`) is deliberately not shown. Fred judged it
  not beginner-friendly.

## Rejected alternatives

- **2:** the local registry would have to hold upstream caches, which is the dual role
  [ADR 0006](0006-local-registry-holds-authored-entries-only.md) removes. Caches can go
  stale and shadow newer upstream tags (shpc matches the first entry by name, `[code]`
  `shpc/main/registry/__init__.py:63-76`).
- **A longer message with a check command:** not beginner-friendly (Fred).

## Principles and patterns

Distinct failure types rather than overloaded empty results. Rhodes, Sentinel Object,
contrasts sentinels with `str.index()` raising as "more rigorous". Ousterhout ch. 10
(errors that must surface are not "defined out of existence").

## What would reverse this decision

- A real need for offline builds, e.g. air-gapped training VMs (the requirements say
  air-gapped operation is *not* required).
- Frequent transient failures on Nirin's proxy, where retrying would beat failing. Then
  add a bounded retry before failing.
