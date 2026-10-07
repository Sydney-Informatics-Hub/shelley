# 0001: Split discovery from exposure

- **Status:** accepted
- **Date:** 2026-10-07
- **Deciders:** Fred Jaya (lead engineer); design review with Claude

## Context and problem statement

`CVMFSModuleBuilder` is a 734-line class with at least six reasons to change: the tag
grammar, the registry schema, the shpc CLI, permissions, the Lmod layout and the prompts.
Every Tier 0 fix lands in it. A second supplier would touch 10 modules
([architecture-drivers §1.3](../architecture-drivers.md#13-code-smells-fowler-refactoring-2nd-ed)).
The question is how to restructure without over-building for EESSI, which is still work
in progress.

## Decision drivers

Ranked quality attributes ([architecture-drivers §2.5](../architecture-drivers.md#25-quality-attributes-ranked)):
correctness (1), shared-VM safety (2), honest failures (3), testability (4), reviewability
(6), with extensibility deliberately last (7).

## Considered options

- **A. Fix in place:** keep `CVMFSModuleBuilder`, and add the common core beside it.
- **B. Ports and adapters:** a `Supplier` Protocol, a composite catalogue and a supplier
  registry.
- **C. Split discovery from exposure:** a read-only `GalaxyCatalogue` (runs as the user),
  a privileged, transactional `ShpcExposer` (runs as root), service functions returning
  results, and one command table.

## Decision outcome

**Chosen: C.** It follows a seam that already exists at runtime, between the unprivileged
parent and the root child. That lets the tool spec be validated before the sudo prompt,
gives one fake per role for tests, and divides the work into reviewable PRs. **A is the
recorded fallback** if review capacity tightens.

### Consequences

- Good: the Large Class goes; Galaxy assumptions sit in `galaxy/`, `tags.py` and `tools/`
  ([target-state §7](../../reference/architecture/target-state.md#7-where-galaxy-and-shpc-assumptions-live-to-be)).
  A second supplier costs 2–3 modules, down from 10.
- Bad: more files move than under A, so the early PRs are larger diffs, even though they
  are mechanical.

## Rejected alternatives

- **A:** fixes the Tier 0s, but Divergent Change stays: every fix keeps landing in one
  700-line file, which works against rank 6.
- **B:** three of its four patterns fail the justification test today. A Protocol, a
  composite and a registry over a single supplier are speculative and shallow (Fluent
  Python ch. 13; Ousterhout ch. 4), and EESSI's shape (how it is exposed) is still
  unknown.

## Principles and patterns

Repository (Cosmic Python ch. 2); Service Layer as plain functions (Cosmic Python ch. 4);
Façade per external tool (Mak, Façade *(from memory)*; Cosmic Python ch. 3, 13); bounded
contexts (Evans); "abstract on the second real case"; Extract Class and Split Phase
(Fowler).

## What would reverse this decision

- **Towards B:** a concrete EESSI exposure design (integration question E-Q1 answered) and
  a second catalogue/exposer pair in code. Then extract a `typing.Protocol` per role from
  the two concrete classes.
- **Towards A:** PO review capacity dropping below one moderate PR a fortnight, or the
  PR 1 spike showing the move costs more than about 2 units on top of the fixes.
