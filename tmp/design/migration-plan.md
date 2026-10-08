# Migration plan: current state → target state

**Not documentation.** Fred will turn this into GitHub issues and a milestone; it will go stale once it is in the tracker.

**Inputs:**
- [target-state.md](../../docs/reference/architecture/target-state.md);
- ADRs [0001](../../docs/explanation/decisions/0001-split-discovery-from-exposure.md) to [0007](../../docs/explanation/decisions/0007-resolve-before-elevating.md);
- the ranked drivers ([architecture-drivers §2](../../docs/explanation/architecture-drivers.md#part-2-drivers-quality-attributes-and-priorities)).

**Revised 2026-10-07 (Fred):**
- The PO's priority is completing the **build** functionality, so build migrates first; the riskiest unknown still comes before everything.
- Migration is a **parallel change**: new modules and tests are built alongside the old implementation, switched on when ready, and the old implementation is deleted only once certain.

**Conventions:**
- **1 unit = 1.5 h**; about **6 usable units a week** (confirmed by Fred).
- **Each batch is one PR**, reviewable in one sitting; its numbered steps are commits.
- Every batch leaves shelley releasable.
- **Scope:** Galaxy supplier and metadata sources. EESSI and `data.galaxyproject.org` stay latent.

## How each area migrates: expand, switch, contract

This is Parallel Change, also called expand–migrate–contract (martinfowler.com, *Parallel Change* *(from memory)*). Each area goes through four stages:

1. **Expand.** New modules and their tests land next to the old code. They are not wired to the CLI, so users see no change, and the PO reviews only new files.
2. **Opt in.** The CLI routes to the new path when `SHELLEY_NEW_BUILD=1` is set. `SHELLEY_*` variables are already forwarded across the sudo re-exec ([build.py:47-50](../../shelley/commands/build.py#L47-L50)), so the root child follows the same path. Released this way, Fred and the PO can try it on real VMs.
3. **Switch.** The default flips to the new path once the "certain" criteria below are met. For one release, `SHELLEY_LEGACY_BUILD=1` remains as an escape hatch.
4. **Contract.** After one release with no regression and no use of the escape hatch, the old implementation and the flag are deleted.

**On-disk compatibility during the overlap.** Old `find` and `clean` must keep working on modules built by the new path, and the new path must handle what the old one built. So the new build keeps, unchanged:
- the Lmod link layout (`<tool>/<tag>.lua` → shpc `module.lua`);
- the shpc settings file and layout;
- the `container.yaml` schema;
- the marker format (`<tag>/aliases.yaml` with `in_upstream`).

The only format change, the tag value `local:keep-path` in place of a SIF hash, is never read by old code, which only checks whether tag keys exist.

**"Certain" criteria for switching build:**
- (a) the failure-injection, exposer-contract and catalogue-contract suites are green;
- (b) a scripted smoke run on the dev VM with `SHELLEY_NEW_BUILD=1` builds the regression tool matrix ([data-sources.md](../../docs/reference/data-sources.md#regression-tool-matrix)), including one `-i` build, one rebuild of an installed tag, one cancelled `-i`, and one build behind a dead proxy;
- (c) the PO has built at least one tool on their own VM with the flag;
- (d) one release (0.5.0) has been out with the opt-in, and no regressions were reported.

## Overview

| Order | Batch (one PR) | Stage | Fixes | Effort | User-visible | Release |
|---|---|---|---|---|---|---|
| 0 | **Spike: transaction against real shpc** (not merged) | — | de-risks T2/T5 | 2 | none | — |
| 1 | **New build core:** `Tag`, `GalaxyCatalogue` (resolve/verify), `net`, registry | expand | — | 9 | none | — |
| 2 | **New build path, opt-in:** façades, `BuildTransaction`, `ShpcExposer`, resolve-before-elevate, `services.build` | expand + opt in | T1 (build side), T2, T5, T6 behind the flag | 9.5 | only with `SHELLEY_NEW_BUILD=1` | 0.5.0 |
| 3a | **Switch build** | switch | **T2, T5, T6 (Tier 0) for everyone**; T1 for `build` | 1.5 | yes: conda "latest"; mulled needs a tag; fail fast offline; one sudo prompt per batch | 0.6.0 |
| 3b | **Delete the old build** | contract | — | 2 | none | 0.6.1 |
| 4 | **find, search and clean on the new core** (same expand → opt-in → switch, flag `SHELLEY_NEW_DISCOVERY`) | all four stages | **T1 fully** (`find` agrees with `build`), T4, N2 | 10 | `find`'s order and installed flags change | 0.7.0 |
| 5 | **One command surface and final removal** | contract | Repeated Switches, import cycle, dead code | 6 | REPL help gains `clean` | 0.8.0 |
| | **Total** | | | **40 units ≈ 7 weeks of Fred's time** | | |

**T1 interim:** between 3a and 4, `build` uses conda ordering while `find` still uses `_version_key`, so the two keep disagreeing, for a different set of tools, for about three weeks. See checkpoint question 1.

---

## Batch 0: spike, transaction against real shpc (2 units, not merged): **DONE 2026-10-08, go**

Result: `spikes/batch0_results.md`. The pre-image undo was exact in 14/14 injected failures; ADR 0005 is amended to use it. New item: a per-tool lock (step 2.2).

- **Question:** can `apply` be undone exactly, with the real shpc 0.1.33, at every step, including rebuilding an installed tag by moving it aside?
- **Method:** extend `tmp/design/spikes/spike_partial_failures.py` (scratch build roots, `seqtk:r93--0`):
  1. Hash the scratch tree (paths, modes, symlink targets, file bytes).
  2. Inject a failure after each step: entry write, shpc install, harden, link.
  3. Undo, re-hash, and compare.
  4. Repeat with an existing install moved aside.
- **Specific risks to check:**
  - shpc writes `modules/<uri>/.version` per *tool* on install (`shpc/main/modules/base.py:463-466`) **and rewrites it on uninstall** (`:150`), so undo must restore it;
  - `shpc uninstall` may prune parent directories;
  - BioShell's `moduleDir` template patch assumes module files are read through the symlink.
- **Exit:** go/no-go for ADR 0005 as written. If no-go, use "install to staging, then rename into place" and amend the ADR.

## Batch 1: new build core, alongside the old (9 units, expand, no release needed)

**DONE 2026-10-08 (uncommitted).** New: `shelley/_vendor/conda_version.py` (VersionOrder subset of conda @ c755016, BSD-3-Clause), `shelley/errors.py`, `shelley/tags.py`, `shelley/galaxy/{catalogue,registry}.py`, `shelley/tools/net.py`, `tests/build_core/` (84 tests, including the live-mount contract). The only edit to an existing file is `pyproject.toml`: ruff `extend-exclude = ["tmp", "shelley/_vendor"]`. That also fixes `dev` CI, which was failing ruff on the committed `tmp/design` notes. Deviations from the plan:
- the vendored file is trimmed to the VersionOrder part (340 lines, not 715);
- `GalaxyCatalogue.resolve` raises `AmbiguousTag` instead of prompting; the prompt moves to `services` in batch 2;
- `LocalRegistry` has no `remove`, because the batch 2 transaction restores a pre-image instead.

New files only; nothing existing is edited except `NOTICE`.

| Step (commit) | Scope | New files | Tests | Fowler refactoring | Units |
|---|---|---|---|---|---|
| 1.1 | Vendor conda's `VersionOrder` (BSD-3-Clause notice) | `shelley/_vendor/conda_version.py` | Known-pair smoke test | — | 0.5 |
| 1.2 | `Tag`, `latest()` with the mulled rule; typed errors | `shelley/tags.py`, `shelley/errors.py` | Golden tag table from the Q2 spike; property tests (total order; no prefix match) | Replace Primitive with Object (new, parallel) | 2 |
| 1.3 | `GalaxyCatalogue`: `tags`, `resolve`, `verify` (one `stat`), live-listing fallback | `shelley/galaxy/catalogue.py` | Catalogue contract suite over a fixture mount and snapshot; a `cvmfs`-marked run against the live mount | Extract Class (new, parallel) | 2.5 |
| 1.4 | `net.fetch_text`/`diagnose`; `NetworkUnavailable`; `RegistryClient` | `shelley/tools/net.py`, `shelley/galaxy/registry.py` | Simulated DNS failure, timeout and connection refused; Fred's message wording | Substitute Algorithm (curl → urllib) | 2 |
| 1.5 | `LocalRegistry`: authored entries; merge upstream tags; legacy-entry rule; marker format unchanged | `shelley/galaxy/registry.py` | Stale-shadow and legacy-entry tests; round trip: an entry written by `LocalRegistry` is read by the old `uninstall_module` | — | 2 |

## Batch 2: new build path, opt-in (9.5 units) → 0.5.0

| Step | Scope | Files | Tests | Fowler refactoring | Units |
|---|---|---|---|---|---|
| 2.1 | `Shpc` and `Lmod` façades (wrap the existing `shpc_settings` and Lmod loader rather than copying them) | `shelley/tools/shpc.py`, `shelley/tools/lmod.py` | `FakeShpc`, `FakeLmod` | Extract Class | 1.5 |
| 2.2 | `BuildTransaction`: pre-image of the tool's 5 subtrees on entry, exact restore unless committed, per-tool `flock` | `shelley/transaction.py` | Port the spike's tree-hash check as a unit test on a fixture tree; commit keeps; exception restores exactly; failing restore reported; two processes contend for the lock | — | 1.5 |
| 2.3 | `ShpcExposer.plan`/`apply` with move-aside (per batch 0); tag value `local:keep-path` | `shelley/galaxy/exposer.py`, `shelley/results.py` | **Failure injection** at each step (tree hash unchanged); **spike A port** (cancelled `-i` keeps the module); **spike B port** (dead proxy: `NetworkUnavailable`, nothing written); real-shpc variants marked `shpc` | Split Phase | 3.5 |
| 2.4 | `privilege` (resolve first, then re-exec with hidden `--resolved-tag`); `services.build`, `services.build_many` (one elevation per batch) | `shelley/privilege.py`, `shelley/services.py` | Bad spec → no sudo call; batch resolves all specs and elevates once; failed specs reported individually | Move Function (copy, then old deleted in 3b) | 2 |
| 2.5 | Opt-in routing: when `SHELLEY_NEW_BUILD=1`, the CLI and REPL `build` call `services.build`; CHANGELOG "experimental" | `client/cli.py`, `commands/interactive.py` (one branch each) | CLI routing tests for both values of the flag | — | 1 |

## Batch 3a: switch build (1.5 units) → 0.6.0

Once the "certain" criteria hold:
- the default becomes the new path, and `SHELLEY_LEGACY_BUILD=1` selects the old one for this release;
- update the CHANGELOG ("latest" now follows conda ordering; `mulled-*` needs a tag; builds fail fast when offline; one sudo prompt per batch);
- update `docs/explanation/build-design.md`.

## Batch 3b: delete the old build (2 units) → 0.6.1

After one release with no regression and no use of the escape hatch, delete:
- `CVMFSModuleBuilder.shpc_install`, `_ensure_local_registry_entry`, `_share_build_artifacts`, `_run_shpc_install`, `_compute_sha256`, `_is_registry_miss`, `search_tool_version` and their private helpers;
- `get_registry_tags`;
- the old branch in `commands/build.py` and `utils/batch.py`;
- both flags;
- the tests that only exercised the deleted code.

`uninstall_module` stays until batch 4. Fowler: Remove Dead Code.

## Batch 4: find, search and clean on the new core (10 units) → 0.7.0

Same four stages, with flag `SHELLEY_NEW_DISCOVERY` (covers `find`, `search` and `clean`):

| Step | Scope | Units |
|---|---|---|
| 4.1 | `GalaxyCatalogue.installed()` with `TagState` (`AVAILABLE`/`LINKED`/`DANGLING`); `MetadataSource.lookup()`; pull `search()` up into the base (Pull Up Method) | 2.5 |
| 4.2 | `services.find`, `services.search`; `client/render.py` for their results | 3 |
| 4.3 | `ShpcExposer.remove` inside a transaction; `services.clean` (resolve before elevating) | 2 |
| 4.4 | Opt-in, then switch after the same style of criteria (agreement test: `find`'s top row equals `build`'s default for every named tool in the snapshot) | 1 |
| 4.5 | Contract: delete `utils/cache.py`, the old `find`/`search`/`clean` code, `uninstall_module`, the rest of `CVMFSModuleBuilder` | 1.5 |

## Batch 5: one command surface and final removal (6 units) → 0.8.0

| Step | Scope | Fowler refactoring | Units |
|---|---|---|---|
| 5.1 | `client/commands.py` `COMMANDS` table; CLI and REPL both loop over it (REPL help gains `clean`); parity test | Replace Conditional with a dispatch table | 3 |
| 5.2 | Delete `commands/{build,clean,find,search,interactive}.py`, `utils/{batch,args,commands}.py`, `list_cvmfs_versions`, 4 unused `ShelleyStyle` methods; `shelley/__init__` exports only `__version__` (CHANGELOG "Removed": `from shelley import CVMFSModuleBuilder`; BioShell does not use it) | Remove Dead Code; Inline | 2 |
| 5.3 | Docs: `target-state.md` replaces `current-state.md`; update the how-to and explanation pages | — | 1 |

---

## PO review batches and calendar

From Wednesday 2026-10-07, at about 6 units a week:

| Week of | Work | PR or release |
|---|---|---|
| 12 Oct | Batch 0 spike (2); batch 1 steps 1.1–1.3 (5) | — |
| 19 Oct | Batch 1 steps 1.4–1.5 (4); batch 2 starts (2) | **PR: Batch 1, new build core** (new files only; focus: golden tag table, catalogue contract) |
| 26 Oct | Batch 2 (6) | — |
| 2 Nov | Batch 2 finish (1); rework (2); smoke-run script (2) | **PR: Batch 2, new build path (opt-in)** → **0.5.0**; Fred and the PO try `SHELLEY_NEW_BUILD=1` |
| 9 Nov | Trial on VMs; batch 4 expand starts (4) | — |
| 16 Nov | Batch 3a (1.5); batch 4 (4) | **PR: Batch 3a, switch build** → **0.6.0** |
| 23 Nov | Batch 4 (4) | — |
| 30 Nov | Batch 3b (2), after a two-week soak; batch 4 finish (2) | **PR: Batch 3b, delete old build** → 0.6.1; **PR: Batch 4** → **0.7.0** |
| 7 Dec | Batch 5 (6) | **PR: Batch 5** → **0.8.0** |

The build functionality is complete for everyone by **0.6.0 (about 16 Nov)**, and the whole migration lands by mid-December, before the January BioShell image bump.

---

## Test seams

### 1. Fake CVMFS mount and snapshot fixtures

- **`galaxy_mount(tmp_path, entries)`** creates a directory of **empty** files named `tool:tag`. Neither the catalogue nor `stat` needs real SIF bytes.
- **`galaxy_snapshot(tmp_path, entries)`** writes a matching `galaxy_singularity_cache.json.gz` in the real schema, so tests can create drift between the two (an entry in the mount but not the snapshot).
- **A golden entry set** reused across tests: the Q2 spike's hard cases (`bracken 3.1`/`3.1p1`, `burst 1.0`/`v1.0`, `hicexplorer latest`, `lofreq broken`, `integron_finder 2.0rc6`, a `mulled-v2-*` hash pair, `seqtk r93`/`1.5`) plus ordinary ones.
- `SHELLEY_CVMFS_PATH` points at the fixture mount for every test by default (an extension of `conftest.py`'s autouse redirect).

### 2. Contract tests

- **Catalogue contract** (`tests/contracts/test_catalogue.py`), parametrised over catalogue factories:
  - *fixture* (always);
  - *live Galaxy mount* (marked `cvmfs`; this is where Fred's CI-with-CVMFS issue plugs in).

  Assertions:
  - `tags()` is sorted by `Tag.sort_key`;
  - `resolve(None)` equals `latest()`;
  - `resolve(v)` accepts an exact tag or version only;
  - `verify` raises `MountUnavailable` when the mount is absent;
  - `installed()` reports `LINKED` and `DANGLING` correctly.

  Future EESSI and `data.galaxyproject.org` catalogues join the parametrisation; this is the "every supplier must pass" suite.
- **Exposer contract** (`tests/contracts/test_exposer.py`), Galaxy only for now:
  - `plan` performs no writes (tree hash unchanged);
  - `apply` is all-or-nothing under failure injection;
  - `remove` after `apply` restores the original tree, apart from the Lmod directory created on first build.

### 3. Fakes for edge-to-edge tests (Cosmic Python ch. 3 and 5)

| Fake | Behaviour |
|---|---|
| `FakeShpc` | Records argv; creates the `module.lua`, `.version` and wrapper dirs real shpc would; `fail_on=("install", n)` to inject failure |
| `FakeLmod` | Records loads; creates and removes links in the tmp Lmod dir |
| `FakeRegistry(entries, reachable=True)` | Returns entries, `None`, or raises `NetworkUnavailable` |
| `FakeCatalogue(tags, installed)` | In-memory, for service tests |
| `make_services(**fakes)` fixture | Builds `services` with defaults replaced, as bootstrap-style dependency injection (Cosmic Python ch. 13) using keyword arguments, not a container |

### 4. Isolation from the real `/apps`, `~` and the network

- **Paths:** `conftest.py` already redirects the three build roots per test. Extend it to also redirect `SHELLEY_CVMFS_PATH`, `HOME` and `XDG_CACHE_HOME` to tmp.
- **Network off by default:** an autouse fixture patches `socket.create_connection` to raise unless the test is marked `network`. That gives the declared-but-unused `network` marker a purpose.
- **Teardown guard (T3, dev machines only, low priority):** a session-scoped fixture records a hash of `/apps/shpc`, `/apps/local`, `/apps/Modules/modulefiles` and `~/.cache/shelley` before the session and fails the run if they changed. This catches any test that creates a module outside the redirected roots.
- **Markers:**
  - default: hermetic;
  - `cvmfs`: live mount (CI once CVMFS is mounted);
  - `shpc`: real shpc and Singularity;
  - `network`: real network.

  CI runs the default set on every PR, and adds `cvmfs` when the mount is available.

## Tier 0 coverage

| Tier 0 | Fixed for everyone in | Proven by |
|---|---|---|
| T1 silent wrong-version match | `build` side in 3a; fully (with `find`) in 4 | Golden tag table; agreement test over the bundled snapshot |
| T6 offline build misreports and persists | 3a | Dead-proxy test (spike B port); stale-shadow and legacy-entry tests |
| T2 orphaned build artefacts | 3a | Failure injection at every `apply` step; exposer contract |
