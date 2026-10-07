# Architecture drivers and as-is design review

Why shelley's current design needs to change, and what will decide between the
alternatives. The facts this page judges are in
[current-state.md](../reference/architecture/current-state.md); terms follow the
[glossary](../reference/architecture/glossary.md).

> **Status (2026-10-07):** Part 1, the as-is design review, is complete. Part 2, the
> drivers and quality-attribute ranking, was confirmed by Fred on 2026-10-07. The
> driver → module matrix is in
> [traceability.md](../reference/architecture/traceability.md).

- **Scope:** the Galaxy Singularity supplier and the metadata sources. EESSI is work in
  progress and enters only where it tests a design force.
- **Canon citations:** books are cited by topic, and by chapter where the chapter is
  known with confidence. Where a citation relies on recall of a paywalled book rather
  than a check of the text, it is marked *(from memory)*.

---

## Part 1: as-is design review

### 1.1 Headline findings

1. **Correctness, not structure, is the urgent problem.** There are two version-ordering
   rules, a prefix-glob "installed" check and `split("--")` repeated in five places. All
   are symptoms of tags being passed around as bare strings. Together they cause the
   known silent wrong-version match: 331 tools get a different "latest" from `find` and
   `build`. They also cause a second wrong-version display that is new to this review:
   `find` marks `1.1` as installed when only `1.10` is.
2. **Builds have no rollback.** Cancelling the alias prompt in `build -i` for an
   installed tag deletes the working module for every user (reproduced `[runtime]`).
   More generally, a build writes four kinds of artefact (registry entry,
   marker, shpc module and wrappers, Lmod symlink) with no record of what it created, so
   any failure part-way leaves orphans. `clean` cannot reach them, because it only sees
   tags that still have a symlink. The orphans on the dev VM show this state in practice,
   even though they came from testing.
3. **One class carries almost everything.** `CVMFSModuleBuilder` is 734 lines with at
   least five unrelated reasons to change, and it prints UI panels from inside the build.
   Every other module is small and mostly cohesive.
4. **"Not found" and "couldn't check" look the same.** `_load_registry_config` returns
   `{}` both for "not in the upstream registry" and for "GitHub unreachable". With no
   network, every build silently takes the local-entry path, and then alias discovery
   also fails because it needs a `git clone`. The result is a "successful" module with no
   tool command, and a message that wrongly says the tag is not upstream. The bad local
   entry then shadows upstream on later online rebuilds until `clean` `[runtime]` ([cvmfs_builder.py:93-97](../../shelley/builder/cvmfs_builder.py#L93-L97),
   [:521-528](../../shelley/builder/cvmfs_builder.py#L521-L528),
   [guts_integration.py:118-119](../../shelley/builder/guts_integration.py#L118-L119)).
5. **The tests are fast and thorough, but rely on patching.** 273 tests pass offline in
   about 5 s, through about 190 `monkeypatch`/`patch` sites aimed at module attributes.
   There is no seam, such as an injected shpc or mount object, that a second supplier
   could reuse.

### 1.2 Rubric scores

Scale: 3 = good, 2 = acceptable, 1 = poor, – = not applicable (only supplier-adapter-like
modules are scored on substitutability). One line of justification follows each table
row group.

| Module / class | Cohesion | Coupling | Encapsulation | Depth | Substitutability | Testability | Pythonic fit | Least astonishment |
|---|---|---|---|---|---|---|---|---|
| `CVMFSModuleBuilder` + registry functions | 1 | 1 | 1 | 2 | 1 | 2 | 1 | 2 |
| `commands.build` | 2 | 2 | 2 | 2 | – | 2 | 2 | 2 |
| `commands.clean` | 2 | 1 | 2 | 2 | – | 2 | 2 | 2 |
| `commands.find` | 2 | 2 | 1 | 2 | – | 2 | 2 | 1 |
| `commands.search` | 3 | 2 | 2 | 2 | – | 1 | 3 | 2 |
| `MetadataSource` hierarchy | 3 | 3 | 2 | 2 | 3 | 3 | 2 | 3 |
| `utils.cache` (Galaxy cache) | 2 | 3 | 1 | 2 | – | 2 | 2 | 2 |
| `guts_integration` | 2 | 2 | 3 | 3 | – | 2 | 3 | 2 |
| `shpc_settings` | 3 | 3 | 3 | 3 | – | 3 | 3 | 3 |
| `utils.perms` | 3 | 3 | 3 | 3 | – | 3 | 3 | 3 |
| `utils.globals` | 2 | 3 | 2 | 2 | – | 3 | 3 | 2 |
| `utils.style` / `ShelleyStyle` | 2 | 2 | 2 | 2 | – | 3 | 1 | 2 |
| CLI + REPL dispatch | 2 | 1 | 2 | 1 | – | 2 | 2 | 2 |
| `utils.batch` | 2 | 1 | 3 | 2 | – | 2 | 3 | 2 |
| `commands.update` + `update_check` | 3 | 2 | 3 | 3 | – | 3 | 3 | 3 |

**`CVMFSModuleBuilder` + registry functions**
- *Cohesion 1:* it changes for the tag grammar, registry schema, shpc CLI, permission
  model, Lmod layout and interactive prompts (Divergent Change; Fowler).
- *Coupling 1:* it imports 5 internal modules plus `questionary`, `yaml`,
  `subprocess`/`curl` and the presentation layer.
- *Encapsulation 1:* callers pass a raw `(tool, tag)` and get back a symlink path and an
  untyped report dict. The `quay.io/biocontainers` layout leaks to `clean`, `perms` and
  the docs.
- *Depth 2:* its public interface is small (`search_tool_version`, `shpc_install`,
  `uninstall_module`) over a lot of behaviour, which is deep (Ousterhout, ch. 4). But the
  depth comes from bundling unrelated jobs, not from hiding one.
- *Substitutability 1:* it is the only supplier implementation, and its constructor binds
  the Galaxy path as a default argument.
- *Testability 2:* it is tested heavily, but only by patching `subprocess.run`, `curl`
  and the filesystem.
- *Pythonic fit 1:* the module-level functions and the class share state through
  globals; private helpers are called across the class boundary.
- *Least astonishment 2:* prompts and panels appear in the middle of a build, from inside
  the builder.

**`commands.build`:** coh 2, it mixes elevation policy with build orchestration · cpl 2,
six imports · enc 2, it knows the build roots · depth 2 · test 2, `needs_sudo` is
injectable through env vars · pyth 2 · LA 2, a sudo prompt appears even for an invalid
spec (version resolution runs only after the re-exec, unlike `clean`).

**`commands.clean`:** coh 2 · cpl 1, it imports two sibling commands · enc 2 · depth 2 ·
test 2, 32 tests · pyth 2 · LA 2, confirmation before sudo is good, but orphans are
unreachable.

**`commands.find`:** coh 2, lookup plus a lot of rendering · cpl 2 · enc 1, it calls the
private `_flatten_edam` and knows the modulefile naming · depth 2 · test 2 · pyth 2 · LA 1,
it shows wrong "installed" flags and a "latest" that differs from what `build` installs.

**`commands.search`:** coh 3 · cpl 2 · enc 2 · depth 2 · test 1, no direct test ·
pyth 3 · LA 2, it silently hides tools whose bio.tools id differs from the container
name (e.g. `seurat`).

**`MetadataSource` hierarchy:** coh 3 · cpl 3 · enc 2, `entries` is a public list of raw
dicts · depth 2 · subst 3, both subclasses are interchangeable · test 3, entries are
injectable · pyth 2, the base class's "why not an ABC" is a defensible choice, but
`search()` is copied verbatim into both subclasses · LA 3.

**`utils.cache`:** coh 2 · cpl 3 · enc 1, it returns `(tag, path, mtime)` tuples and
re-parses 122k entries on every call · depth 2 · test 2 · pyth 2 · LA 2.

**`guts_integration`:** coh 2, alias discovery and the interactive editor live in one
module · cpl 2 · enc 3 · depth 3, one call hides a sparse clone, a manifest merge and a
diff · test 2 · pyth 3 · LA 2, it swallows `SystemExit` and every other error, so "no
aliases" can mean "broken".

**`shpc_settings`, `utils.perms`:** 3 across the board. They are small, deep and
idempotent, are tested without root, and their docstrings record the shpc behaviour
they depend on.

**`utils.globals`:** coh 2, layout and Galaxy constants together · enc 2, the constants
are importable even though the docs say to use the resolvers · pyth 3, resolve-per-call
is a sensible "global object" (Rhodes, Global Object).

**`utils.style` / `ShelleyStyle`:** pyth 1, a class of 17 static methods used as a
namespace; in Python the module is already the namespace (Rhodes; Fluent Python, ch. 7
*(from memory)*). Four of the methods are unused. Coh 2, rendering plus the update-check
trigger.

**CLI + REPL dispatch:** cpl 1, `cli` has a fan-out of 10 · depth 1, `if`/`elif` chains
that forward to commands · LA 2, the REPL help omits `clean`.

**`utils.batch`:** cpl 1, a utility that depends on a command (layering inversion).

**`commands.update` + `update_check`:** they do one thing each, fail quietly, are
tested, and have an opt-out.

### 1.3 Code smells (Fowler, *Refactoring* 2nd ed.)

| Smell | Instance | Evidence |
|---|---|---|
| Large Class | `CVMFSModuleBuilder`, 734 lines | [cvmfs_builder.py:136-869](../../shelley/builder/cvmfs_builder.py#L136-L869) |
| Divergent Change | `CVMFSModuleBuilder` changes for 6 unrelated reasons (see rubric) | same |
| Shotgun Surgery | A new supplier touches 10 runtime modules (current-state §7). A change to the tag grammar touches 4 files (`cvmfs_builder`, `cache`, `clean`, `find`) | [current-state §7](../reference/architecture/current-state.md#7-hard-coded-galaxy-and-shpc-assumptions-as-is) |
| Primitive Obsession | Tool, tag and short version are `str`; candidate versions are `(tool, tag)` tuples; cache rows are `(tag, path, mtime)`; aliases are dicts; the clean report and the find payload are dicts | [cvmfs_builder.py:195-238](../../shelley/builder/cvmfs_builder.py#L195-L238), [cache.py:34-53](../../shelley/utils/cache.py#L34-L53), [cvmfs_builder.py:714-721](../../shelley/builder/cvmfs_builder.py#L714-L721), [find.py:112-121](../../shelley/commands/find.py#L112-L121) |
| Duplicated Code | Version ordering ×2; `search()` ×2; spec parsing ×2; sudo re-exec block ×2; the upstream URL ×2; the URI f-string ×3; dispatch ×2 | [cache.py:16](../../shelley/utils/cache.py#L16) / [cvmfs_builder.py:165](../../shelley/builder/cvmfs_builder.py#L165); [rsec.py:76-105](../../shelley/search/rsec.py#L76-L105) / [toolfinder.py:58-87](../../shelley/search/toolfinder.py#L58-L87); [build.py:157-162](../../shelley/commands/build.py#L157-L162) / [clean.py:16-24](../../shelley/commands/clean.py#L16-L24); [build.py:93-124](../../shelley/commands/build.py#L93-L124) / [clean.py:118-143](../../shelley/commands/clean.py#L118-L143); [cvmfs_builder.py:86](../../shelley/builder/cvmfs_builder.py#L86) / [:346](../../shelley/builder/cvmfs_builder.py#L346) |
| Data Clumps | `tool_name, version, container_path, uri` travel together | [cvmfs_builder.py:300-310](../../shelley/builder/cvmfs_builder.py#L300-L310) |
| Long Parameter List | `_ensure_local_registry_entry`, 8 parameters including a UI `status` spinner | same |
| Feature Envy | `find` calls `MetadataSource._flatten_edam`; `clean` uses `find.list_installed_versions` | [find.py:107-109](../../shelley/commands/find.py#L107-L109), [clean.py:10](../../shelley/commands/clean.py#L10) |
| Repeated Switches | Command dispatch in `cli` and `interactive` | [cli.py:72-145](../../shelley/client/cli.py#L72-L145), [interactive.py:46-75](../../shelley/commands/interactive.py#L46-L75) |
| Global Data | The `console` singleton; the module-level `_LOADED` flag | [style.py:95](../../shelley/utils/style.py#L95), [modules.py:23](../../shelley/utils/modules.py#L23) |
| Dead Code | `list_cvmfs_versions` → `list_versions_with_paths`; 4 `ShelleyStyle` methods; `ToolfinderSource` at runtime | [build.py:206](../../shelley/commands/build.py#L206); [style.py](../../shelley/utils/style.py) |
| Mysterious Name | `utils.globals` holds Galaxy-specific constants; `find_tool_sync` has no async counterpart | [globals.py:16](../../shelley/utils/globals.py#L16), [find.py:46](../../shelley/commands/find.py#L46) |
| Comments (used as deodorant) | A 48-line docstring explains `uninstall_module`'s state rules; the complexity it documents is the registry entry's dual role | [cvmfs_builder.py:593-639](../../shelley/builder/cvmfs_builder.py#L593-L639) |

**Divergent Change vs Shotgun Surgery.** shelley shows both, and they point the same way.
The Galaxy specifics are concentrated in one class (Divergent Change), and the parts that
are not concentrated are spread across 10 modules as bare strings and path conventions
(Shotgun Surgery). Adding a second supplier today would mean editing the god class *and*
those 10 modules.

### 1.4 Does each pattern-map force exist in the code?

Hypotheses from the design brief, checked against `[code]` evidence. "Real" means the
force acts on today's code; "latent" means it appears only when a second supplier
arrives; "absent" means no evidence.

| Force | Verdict | Evidence | Simplest response that would satisfy it |
|---|---|---|---|
| Suppliers vary | **Latent.** There is one supplier, so no variation exists in code yet. EESSI is the second case but is work in progress | current-state §7, 14 assumptions in 10 modules | None until EESSI is concrete ("abstract on the second real case"). Meanwhile, reduce the Shotgun Surgery by moving Galaxy constants and the tag grammar into one module |
| Choosing a supplier | **Absent** | single code path | — |
| Build is a fixed sequence of steps | **Real, but with one implementation.** Note there is no `shpc view install` step | [cvmfs_builder.py:491-590](../../shelley/builder/cvmfs_builder.py#L491-L590) | A plain function per step; Template Method has nothing to vary yet (Mak, Template Method *(from memory)*) |
| Partial side effects; orphans | **Real, Tier 0** | current-state §5, rows "RegEntry → Orphan", "ShpcInst → Orphan", "Linked → Dangling" | Strongest candidate for a Unit-of-Work-style context manager (Cosmic Python ch. 6; Fluent Python ch. 18) |
| Index over 122k entries plus a second supplier | **Real for consistency, latent for scale.** `find` reads the snapshot and `build` lists the mount; each call re-parses the snapshot | [find.py:58](../../shelley/commands/find.py#L58), [cvmfs_builder.py:210](../../shelley/builder/cvmfs_builder.py#L210), [cache.py:39-41](../../shelley/utils/cache.py#L39-L41) | One read-only catalogue function that both commands call (Repository, Cosmic Python ch. 2), with an in-memory fake for tests |
| Wrapping shpc, Lmod, `subprocess`, sudo | **Real.** 14 external-process or network call sites in 7 modules; tests patch about 190 sites | `grep subprocess.run\|urlopen\|exec(` | One thin façade per tool (shpc, Lmod, registry fetch), passed in (Cosmic Python ch. 3 and 13) |
| Versions and tags as strings | **Real, Tier 0** | 1.3 Primitive Obsession; current-state §5 | A frozen dataclass `Tag` with parsing and one ordering rule (Fluent Python ch. 5 and 11); not `packaging.version`, because tags are not PEP 440 |
| Artefact lifecycle | **Real as a concept, but no object has the lifecycle.** States are inferred from the filesystem | current-state §5 | An `Enum` used for reporting and for `clean`'s orphan detection; the State pattern is not justified, because no object changes behaviour by state |
| "Not found" vs "not buildable" vs "mount absent" vs "network down" | **Real** | Headline 4; `find` collapses `None` (no cache file) and `[]` with `or []` ([find.py:58](../../shelley/commands/find.py#L58)) | Distinct result types or sentinels (Rhodes, Sentinel Object; Ousterhout ch. 10) |
| Module-level globals (`console`, settings) | **Real but benign.** Tests already redirect paths via env vars | [globals.py](../../shelley/utils/globals.py), [style.py:95](../../shelley/utils/style.py#L95) | Keep them (Rhodes, Global Object) |
| CLI and REPL dispatch duplication | **Real** | 1.3 Repeated Switches | One command table of plain functions shared by both (Fluent Python ch. 7, functions as objects; Command) |

---

## Part 2: drivers, quality attributes and priorities

Drivers are what the target design must satisfy. Each has an ID used in
[traceability.md](../reference/architecture/traceability.md).

### 2.1 Existing capabilities to preserve (C)

The no-go rule "Galaxy CVMFS CLI-tool delivery must stay as-is" (requirements draft
v0.3) makes every current user-facing behaviour a driver.

| ID | Capability | Evidence |
|---|---|---|
| C1 | `search`: keyword search of RSEC bio.tools metadata, limited to tools with a Galaxy container | `[code]` [search.py](../../shelley/commands/search.py); `[doc]` [search-design.md](search-design.md) |
| C2 | `find`: name lookup with metadata, versions, an installed flag and the next command to run | `[code]` [find.py](../../shelley/commands/find.py) |
| C3 | `build`: turn one Galaxy SIF into a shared, loadable Lmod module, through the upstream or the local registry | `[code]` [cvmfs_builder.py:491-590](../../shelley/builder/cvmfs_builder.py#L491-L590); `[doc]` [build-design.md](build-design.md) |
| C4 | `build -i`: curate the commands a module exposes | `[code]` [guts_integration.py:257-281](../../shelley/builder/guts_integration.py#L257-L281) |
| C5 | Batch build from a tools file | `[code]` [batch.py](../../shelley/utils/batch.py) |
| C6 | `clean`: remove one installed tag | `[code]` [clean.py](../../shelley/commands/clean.py); `[doc]` [clean-design.md](clean-design.md) |
| C7 | `interactive` REPL | `[code]` [interactive.py](../../shelley/commands/interactive.py) |
| C8 | `update` and the daily update notice | `[code]` [update.py](../../shelley/commands/update.py), [update_check.py](../../shelley/utils/update_check.py) |
| C9 | Shared multi-user layout: root-owned, world-readable `/apps`, built through a `sudo -E` re-exec | `[code]` [build.py:25-124](../../shelley/commands/build.py#L25-L124), [perms.py](../../shelley/utils/perms.py); `[doc]` [build-design.md](build-design.md) |
| C10 | Read-only commands (`find`, `search`) work without Lmod, shpc or root, e.g. via `uvx` on a non-BioShell host | `[code]` [modules.py:1-12](../../shelley/utils/modules.py#L1-L12), [cvmfs_builder.py:144-148](../../shelley/builder/cvmfs_builder.py#L144-L148) |

### 2.2 Tier 0 defects (T)

Fred has filed some of these as GitHub issues; their numbers are not linked here yet.

| ID | Defect | Priority | Evidence |
|---|---|---|---|
| T1 | Silent wrong-version match: `find` and `build` order versions differently (331 tools) | **Tier 0**, confirmed by Fred as the silent wrong-version match | `[runtime]` current-state §5 |
| T2 | Orphaned build artefacts after a partial failure; `clean` cannot reach them | **Tier 0**; dev-VM leftovers are on the watch list | `[code]`, `[runtime]` current-state §5; `tmp/design/watchlist.md` |
| T3 | A test that creates a module must tear it down | **Deprioritised**: not reproduced (today's offline run wrote nothing outside pytest's tmp dirs), and it affects dev machines only, never user VMs | `[test]` 2026-10-07 run |
| T4 | `find` marks `1.1` installed when only `1.10--…` is (prefix glob) | **Deprioritised** (Fred, 2026-10-07) | `[runtime]` scratch check |
| T5 | Cancelling `build -i` on an installed tag deletes the module for every user | **Deprioritised** (Fred, 2026-10-07) | `[runtime]` spike A |
| T6 | Network down: build "succeeds" without the tool command, misreports the tag as not upstream, and the bad entry persists | **Tier 0** (Fred, 2026-10-07) | `[runtime]` spike B |

### 2.3 New functional drivers (N, F)

| ID | Driver | In scope now? | Evidence |
|---|---|---|---|
| N1 | When the network or GitHub is unreachable, a build must fail or degrade safely and **say the network is down**, never record a wrong registry state | Yes | Fred, 2026-10-07 |
| N2 | `find` and `build` must agree on the available versions and on "latest" (the snapshot is 3,088 entries behind the live mount) | Yes | `[runtime]` 125,608 live vs 122,520 cached |
| F1 | Many R versions selectable through Lmod | Latent: EESSI supplier, work in progress | requirements draft v0.3 |
| F4 | A selected stack works in RStudio Server, the terminal and Nextflow | Latent: EESSI | same |
| F5 | Off-menu packages: free on research VMs, locked in training | Latent | same |
| F7 | shelley discovers packages (`search DESeq2` → stacks), activates stacks, and offers admin build tooling | Partly: the discovery part is a metadata-source question; RSEC has no Bioconductor records today (`[doc]` [search-design.md:33](search-design.md)) | same |
| F2, F3, F6, F8 | Python versions; SIH-curated stacks; trainer-built stacks; immutable stacks | Deferred by the requirements | same |
| PoC | `module load r/4.6.0` → RStudio → `library(DESeq2); library(Seurat)` works | Latent: EESSI; note the version name mismatch in `tmp/design/eessi-notes.md` | same |
| E1 | Expose a supplier's existing Lmod modules without building anything (EESSI) | Latent: shapes how cheap a second supplier must be, not what is built now | glossary, "Expose" |

### 2.4 Constraints (K)

| ID | Constraint | Evidence |
|---|---|---|
| K1 | Galaxy CLI-tool delivery must keep working unchanged | requirements draft v0.3, "No-go" |
| K2 | About 1.5 days a week of engineering | design brief |
| K3 | PO review is expensive, and the main cost is context switching: prefer moderate PRs that the PO can review in one sitting, each leaving shelley releasable | design brief; Fred, 2026-10-07 |
| K4 | Shared multi-user VMs: a change to `/apps` affects every user | `[code]` C9 |
| K5 | CVMFS cache quota 4,096 MB, already 3.6 GB used on the dev VM; root disk about 16 GB free | `[runtime]` `cvmfs_config stat`; requirements draft v0.3 |

### 2.5 Quality attributes, ranked (proposal)

Confirmed by Fred on 2026-10-07, with extensibility deliberately last. The ranking is the tie-breaker for Phase 5. It follows the refocus on the Galaxy supplier
and the metadata sources: extensibility to new suppliers is ranked deliberately low until
EESSI is concrete.

| Rank | Quality attribute | Why this rank | Drivers it serves | Measure |
|---|---|---|---|---|
| 1 | **Correctness of what shelley reports and installs**: one version rule, one view of what is available and installed | Wrong answers are silent, so users act on them; T1 is the confirmed Tier 0 | T1, T4, N2, C2, C3 | Zero disagreements between `find` and `build` over the whole cache; property tests over real tags |
| 2 | **Safety on shared VMs**: no partial failure leaves a broken or orphaned module | A failed or cancelled build affects every user (K4); T2 is Tier 0, and T5 (deprioritised) shows the same mechanism | T2, T5, C6, C9 | Every failure injected at each build step leaves `/apps` exactly as before |
| 3 | **Honest failure reporting**: network, mount or registry problems are named, never recorded as facts | Fred's N1; T6 shows a wrong state persisting after the cause has gone | N1, T6 | Offline build reports "network unavailable" and writes nothing |
| 4 | **Testability without live CVMFS, shpc, sudo or network** | Keeps the 5-second offline suite and lets the fixes for ranks 1–3 be tested; today's 190 patch sites are brittle. Tests that create modules tear them down (T3, dev machines only) | T3, all | Supplier, shpc and registry behaviour testable with fakes; no test touches `/apps`, `~`, the mount or the network unless marked |
| 5 | **Operability within resource limits** | Each build lists a 125k-entry directory (~4 s) and reads the whole SIF to hash it (p95 670 MB, max 9.6 GB) through a 4 GB cache (K5) | K5, C3 | No full-SIF read on the default path; no full mount listing per build |
| 6 | **Reviewability and delivery fit**: each PR is a moderate, coherent, releasable batch of recognisable refactorings | K2, K3 | all | Each PR reviewable in one sitting; related changes batched; refactorings named from Fowler's catalogue |
| 7 | **Extensibility to a second supplier** | EESSI is the leaning direction but still work in progress; designing for it now would be speculative | E1, F1, F4, F7 | Adding a supplier touches ≤ 3 modules, down from 10 |

`[inferred]` Ranks 1–3 are harms users see; ranks 4–7 are costs the team carries.
Testability (4) sits above operability (5) because, without fakes, the fixes for ranks
1–3 cannot be verified offline.
