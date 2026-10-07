# Target-state architecture (to-be)

The agreed design for shelley's classes, modules, deployment and runtime flows. It is
drawn in the same style as [current-state.md](current-state.md) so the two can be read
side by side, and it uses the [glossary](glossary.md) terms. The design decisions and
their reasons are in the ADRs under [docs/explanation/decisions/](../../explanation/decisions/),
and the drivers each part serves are in [traceability.md](traceability.md#to-be).

- **Status:** agreed 2026-10-07 (design Option C; Option A is the recorded fallback).
  Once the migration is complete, this page replaces `current-state.md`.
- **Scope:** the Galaxy Singularity supplier and the metadata sources. A second supplier
  (EESSI, work in progress) plugs in as described in [§9](#9-adding-a-second-supplier-to-be).
- **Evidence:** this page describes a design, not observed behaviour. File and line
  references point to the as-is code a part replaces; `[code]` labels refer to external
  code (shpc) whose behaviour the design relies on.

Contents:

1. [Class diagrams](#1-class-diagrams-to-be)
2. [Package diagram and move map](#2-package-diagram-and-move-map-to-be)
3. [Component and deployment](#3-component-and-deployment-to-be)
4. [Sequence diagrams](#4-sequence-diagrams-to-be)
5. [Artefact lifecycle state diagram](#5-artefact-lifecycle-state-diagram-to-be)
6. [Responsibility table](#6-responsibility-table-to-be)
7. [Where Galaxy and shpc assumptions live](#7-where-galaxy-and-shpc-assumptions-live-to-be)
8. [Target measures](#8-target-measures-to-be)
9. [Adding a second supplier](#9-adding-a-second-supplier-to-be)

---

## 1. Class diagrams (to-be)

### 1a. Discovery: read-only, runs as the user

```mermaid
---
title: Discovery classes (to-be)
---
classDiagram
    direction LR
    class services {
        <<module>>
        +find(name, verbose) FindResult
        +search(query) SearchResult
        +resolve(spec) ResolvedTag
    }
    class GalaxyCatalogue {
        +tool_ids() set~str~
        +tags(tool) list~Tag~
        +resolve(tool, requested) Tag
        +verify(tool, tag) Path
        +installed(tool) dict
    }
    class Tag {
        <<frozen dataclass>>
        +raw: str
        +version: str
        +build: str
        +is_release: bool
        +sort_key() tuple
        +matches(requested) bool
    }
    class tags_module {
        <<module tags>>
        +latest(tool, tags) Tag
        +conda_order(version) VersionOrder
    }
    class TagState {
        <<enum>>
        AVAILABLE
        LINKED
        DANGLING
    }
    class MetadataSource {
        +entries: list~dict~
        +load() MetadataSource
        +search(query, limit) list~str~
        +lookup(name) dict
    }
    class RsecSource
    class ToolfinderSource
    class FindResult {
        <<frozen dataclass>>
    }
    class snapshot {
        <<data file>>
        galaxy_singularity_cache.json.gz
    }

    services ..> GalaxyCatalogue
    services ..> MetadataSource
    services ..> FindResult : returns
    GalaxyCatalogue "1" --> "1" snapshot : parses once per process
    GalaxyCatalogue ..> Tag
    GalaxyCatalogue ..> TagState
    tags_module ..> Tag
    MetadataSource <|-- RsecSource
    MetadataSource <|-- ToolfinderSource
    %% GalaxyCatalogue replaces utils/cache.py, CVMFSModuleBuilder._get_available_tools/list_versions/search_tool_version, find.module_is_installed/list_installed_versions
    %% installed() maps each installed Tag to its TagState
    %% MetadataSource.search pulled up from rsec.py:76-105 and toolfinder.py:58-87; lookup() replaces find.py:61-67 and the private _flatten_edam call
    %% tags_module uses shelley/_vendor/conda_version.py (conda VersionOrder, BSD-3-Clause)
```

### 1b. Exposure: privileged and transactional, runs as root

```mermaid
---
title: Exposure classes (to-be)
---
classDiagram
    direction LR
    class services {
        <<module>>
        +build(spec, interactive) BuildResult
        +clean(spec, force) CleanResult
        +build_many(specs) list~BuildResult~
    }
    class privilege {
        <<module>>
        +needs_root() bool
        +reexec(argv) int
    }
    class ShpcExposer {
        +plan(tool, tag, curate) BuildPlan
        +apply(plan) Path
        +remove(tool, tag) CleanResult
    }
    class BuildPlan {
        <<frozen dataclass>>
        +ref: tool and Tag
        +sif: Path
        +in_upstream: bool
        +local_entry: dict or None
        +replace_existing: bool
    }
    class BuildTransaction {
        <<context manager>>
        +record(undo) None
        +commit() None
    }
    class RegistryClient {
        +fetch(uri) dict or None
    }
    class LocalRegistry {
        +read(uri) dict or None
        +write(uri, entry, marker) None
        +remove_tag(uri, tag) None
    }
    class Shpc {
        <<facade>>
        +install(uri_tag, sif) None
        +uninstall(uri_tag) None
        +module_base() Path
    }
    class Lmod {
        <<facade>>
        +load_build_modules() None
        +link(tool, tag, target) Path
    }
    class net {
        <<module>>
        +fetch_text(url) str
        +diagnose(url) Reachability
    }
    class guts_integration {
        <<module>>
        +extract_aliases(sif, keep) list~dict~
        +edit_aliases_interactive(aliases) list~dict~
    }

    services ..> privilege
    services ..> ShpcExposer
    ShpcExposer ..> BuildPlan : creates
    ShpcExposer ..> BuildTransaction : applies inside
    ShpcExposer ..> RegistryClient
    ShpcExposer ..> LocalRegistry
    ShpcExposer ..> guts_integration
    ShpcExposer ..> Shpc
    ShpcExposer ..> Lmod
    RegistryClient ..> net
    %% ShpcExposer replaces CVMFSModuleBuilder.shpc_install, _ensure_local_registry_entry, _share_build_artifacts, uninstall_module (cvmfs_builder.py:300-721)
    %% net raises NetworkUnavailable(host, reason); RegistryClient.fetch returns None only for "not upstream"
    %% errors module (not drawn): NetworkUnavailable, MountUnavailable, TagNotFound, TagRequired, AmbiguousTag
```

---

## 2. Package diagram and move map (to-be)

```mermaid
---
title: Package dependencies (to-be)
---
flowchart TD
    init["shelley/__init__<br/>__version__ only"]
    client["client<br/>commands table, render, cli and REPL loops"]
    services["services"]
    privilege["privilege"]
    galaxy["galaxy<br/>catalogue, exposer, registry"]
    search["search<br/>metadata sources"]
    core["tags, errors, results, transaction"]
    tools["tools<br/>shpc, lmod, net"]
    builder["builder.guts_integration"]
    utils["utils<br/>globals, perms, style, update_check"]
    update["commands.update"]
    vendor["_vendor.conda_version"]

    client --> services
    client --> utils
    client --> update
    services --> galaxy
    services --> search
    services --> privilege
    services --> core
    galaxy --> core
    galaxy --> tools
    galaxy --> builder
    galaxy --> utils
    core --> vendor
    tools --> utils
    update --> utils
    utils --> init
```

Layering rule: `client` → `services` → (`galaxy`, `search`, `privilege`) → (`core`, `tools`,
`builder`, `utils`). No module imports from a layer above it, and `shelley/__init__`
re-exports nothing but `__version__`. This removes the cycle and the three inversions
listed in [current-state §2](current-state.md#2-package-and-dependency-diagram-as-is).

| To-be module | Contents | Replaces (as-is) | Fowler refactoring |
|---|---|---|---|
| `shelley/tags.py` | `Tag`, `latest()`, `conda_order()` | `cache._version_key`; `CVMFSModuleBuilder._parse_version`, `_sort_versions`, `_get_latest_version`; every `split("--")` | Replace Primitive with Object; Combine Functions into Class |
| `shelley/_vendor/conda_version.py` | conda's `VersionOrder`, licence notice kept | — | — |
| `shelley/errors.py` | `NetworkUnavailable`, `MountUnavailable`, `TagNotFound`, `TagRequired`, `AmbiguousTag` | `RuntimeError`/`ValueError` messages matched by regex ([build.py:195](../../../shelley/commands/build.py#L195)) | Replace Error Code with Exception |
| `shelley/results.py` | `FindResult`, `SearchResult`, `BuildPlan`, `BuildResult`, `CleanResult`, `TagState` | payload and report dicts ([find.py:112-121](../../../shelley/commands/find.py#L112-L121), [cvmfs_builder.py:714-721](../../../shelley/builder/cvmfs_builder.py#L714-L721)) | Replace Record with Data Class |
| `shelley/transaction.py` | `BuildTransaction` | — | — |
| `shelley/galaxy/catalogue.py` | `GalaxyCatalogue` | [utils/cache.py](../../../shelley/utils/cache.py); [cvmfs_builder.py:158-238](../../../shelley/builder/cvmfs_builder.py#L158-L238), [:723-869](../../../shelley/builder/cvmfs_builder.py#L723-L869); [find.py:21-43](../../../shelley/commands/find.py#L21-L43) | Extract Class; Move Function |
| `shelley/galaxy/exposer.py` | `ShpcExposer` | [cvmfs_builder.py:240-721](../../../shelley/builder/cvmfs_builder.py#L240-L721) | Extract Class; Split Phase |
| `shelley/galaxy/registry.py` | `RegistryClient`, `LocalRegistry` | [cvmfs_builder.py:71-133](../../../shelley/builder/cvmfs_builder.py#L71-L133) | Move Function |
| `shelley/tools/shpc.py` | `Shpc` façade and the settings file | [cvmfs_builder.py:42-68](../../../shelley/builder/cvmfs_builder.py#L42-L68), [builder/shpc_settings.py](../../../shelley/builder/shpc_settings.py) | Move Function |
| `shelley/tools/lmod.py` | `Lmod` façade | [utils/modules.py](../../../shelley/utils/modules.py); [cvmfs_builder.py:572-578](../../../shelley/builder/cvmfs_builder.py#L572-L578) | Move Function |
| `shelley/tools/net.py` | `fetch_text`, `diagnose` | `curl` in [cvmfs_builder.py:86-92](../../../shelley/builder/cvmfs_builder.py#L86-L92), [:346-351](../../../shelley/builder/cvmfs_builder.py#L346-L351); `urlopen` in [update_check.py:82](../../../shelley/utils/update_check.py#L82) | Substitute Algorithm |
| `shelley/privilege.py` | `needs_root`, `reexec` | [build.py:25-82](../../../shelley/commands/build.py#L25-L82) | Move Function |
| `shelley/services.py` | `find`, `search`, `resolve`, `build`, `build_many`, `clean` | logic in [commands/](../../../shelley/commands/), [utils/batch.py](../../../shelley/utils/batch.py) | Split Phase |
| `shelley/client/commands.py` | `COMMANDS` table; CLI and REPL loops | [client/cli.py](../../../shelley/client/cli.py), [commands/interactive.py](../../../shelley/commands/interactive.py), [utils/args.py](../../../shelley/utils/args.py), [utils/commands.py](../../../shelley/utils/commands.py) | Replace Conditional with a dispatch table |
| `shelley/client/render.py` | Rendering of every result type | rendering in `commands/*.py`, [utils/render.py](../../../shelley/utils/render.py) | Move Function |
| `shelley/search/*` | `search()` and `lookup()` on the base class | itself | Pull Up Method |
| Kept as-is | `builder/guts_integration.py` (raises `NetworkUnavailable` on clone failure), `utils/globals.py` (Galaxy constants moved out), `utils/perms.py`, `utils/style.py`, `utils/update_check.py`, `commands/update.py` | — | Move Field (constants) |
| Removed | `CVMFSModuleBuilder`, `utils/cache.py`, `commands/{build,clean,find,search,interactive}.py`, `utils/batch.py`, `utils/modules.py`, `get_registry_tags`, `list_cvmfs_versions`, 4 unused `ShelleyStyle` methods | — | Remove Dead Code; Inline |

---

## 3. Component and deployment (to-be)

The deployment is unchanged from [current-state §3](current-state.md#3-component-and-deployment-diagram-as-is),
with these differences:

| Element | As-is | To-be |
|---|---|---|
| Upstream registry fetch | `curl` subprocess, failures read as "not upstream" | `urllib` via `tools/net.py`; failure raises `NetworkUnavailable` with a diagnosed reason |
| shpc-guts clone | `git` subprocess; failure → no aliases | unchanged command; failure raises `NetworkUnavailable` |
| `/apps/local` | upstream caches and shelley-authored entries | shelley-authored entries only; on each build of a tool that has one, the fresh upstream tags are merged in |
| Registry tag value | `sha256` of the whole SIF, read through the CVMFS cache | the fixed string `local:keep-path` (shpc accepts any string, `[code]` `shpc/main/schemas.py:13-18`) |
| Snapshot refresh | monthly CI | fortnightly CI |
| Mount access per build | full listing of `all/` (125k entries) | one `stat` of the chosen SIF; a full listing only when the requested tag is missing from the snapshot |

---

## 4. Sequence diagrams (to-be)

### 4.1 `shelley search <description>`

```mermaid
---
title: search (to-be)
---
sequenceDiagram
    actor U as User
    participant CMD as client.commands
    participant S as services
    participant M as RsecSource
    participant C as GalaxyCatalogue
    participant R as client.render
    U->>CMD: shelley search quality control
    CMD->>S: search(query)
    S->>M: load()
    S->>C: tool_ids() - from the parsed snapshot
    S->>M: search(query) over entries with a Galaxy container
    S-->>CMD: SearchResult(names, descriptions)
    CMD->>R: paginate(result)
    R-->>U: pages of 10
```

### 4.2 `shelley find <tool> [-v]`

```mermaid
---
title: find (to-be)
---
sequenceDiagram
    actor U as User
    participant CMD as client.commands
    participant S as services
    participant M as RsecSource
    participant C as GalaxyCatalogue
    participant R as client.render
    U->>CMD: shelley find samtools
    CMD->>S: find("samtools", verbose)
    S->>M: lookup(name) - exact id or name, else close matches
    S->>C: tags(tool) - sorted by Tag.sort_key
    S->>C: installed(tool) - exact Tag match with TagState
    S->>S: latest = tags.latest(tool, tags), same rule as build
    S-->>CMD: FindResult(meta, tags, states, latest)
    CMD->>R: render(result)
    R-->>U: top row equals what "shelley build samtools" installs
```

### 4.3 `build`, part 1: resolve as the user, then elevate

```mermaid
---
title: build, part 1 of 3 - resolve then elevate (to-be)
---
sequenceDiagram
    actor U as User
    participant CMD as client.commands
    participant S as services
    participant C as GalaxyCatalogue
    participant P as privilege
    participant CH as shelley (root child)
    U->>CMD: shelley build samtools/1.21
    CMD->>S: build("samtools/1.21", interactive)
    S->>C: resolve("samtools", "1.21") - exact tag or version, conda rule
    alt TagNotFound, AmbiguousTag, or TagRequired for mulled
        S-->>U: typed error listing tags - no sudo prompt
    end
    S->>C: verify(tool, tag) - stat the SIF on the mount
    alt MountUnavailable
        S-->>U: "Galaxy CVMFS is not mounted" - no sudo prompt
    end
    S->>P: needs_root()
    alt needs root
        P->>CH: sudo -E env .. python -m shelley build samtools --resolved-tag 1.21--h50ea8bc_3 [-i]
        CH->>CH: verify the tag, then continue with parts 2 and 3
        CH-->>U: exit code and rendered result
    else
        S->>S: continue with parts 2 and 3 in this process
    end
```

### 4.4 `build`, part 2: plan, with no writes

```mermaid
---
title: build, part 2 of 3 - plan (to-be)
---
sequenceDiagram
    participant X as ShpcExposer
    participant N as RegistryClient
    participant L as LocalRegistry
    participant G as guts_integration
    actor U as User
    X->>N: fetch(uri)
    alt unreachable
        N-->>U: NetworkUnavailable "Couldn't reach GitHub (raw.githubusercontent.com): the request timed out after 10 s. Try again in a few seconds."
    end
    X->>L: read(uri)
    opt local entry exists
        X->>X: merge fresh upstream tags into it, or mark it for removal if no LINKED tag uses it and it has no markers
    end
    alt tag in upstream and not interactive
        X->>X: plan uses the upstream entry, no local write
    else tag not upstream, or -i
        opt tag not upstream
            X->>G: extract_aliases(sif, keep=tool)
            G-->>X: aliases, or NetworkUnavailable on clone failure
        end
        opt -i
            X->>U: curate aliases (cancel ends here, nothing written)
        end
    end
    X-->>X: BuildPlan(ref, sif, in_upstream, local_entry, replace_existing)
```

### 4.5 `build`, part 3: apply inside a transaction

```mermaid
---
title: build, part 3 of 3 - apply (to-be)
---
sequenceDiagram
    participant X as ShpcExposer
    participant T as BuildTransaction
    participant L as LocalRegistry
    participant SH as Shpc
    participant LM as Lmod
    participant FS as /apps
    X->>T: enter - default is to undo everything
    opt plan.replace_existing
        X->>FS: move the tag's shpc subtrees and link aside
        X->>T: record(move them back)
    end
    opt plan.local_entry
        X->>L: write entry and marker
        X->>T: record(restore previous entry)
    end
    X->>SH: install(uri:tag, sif) with --keep-path
    X->>T: record(shpc uninstall)
    X->>FS: harden this tool's subtrees
    X->>LM: link(tool, tag, module.lua)
    X->>T: record(unlink)
    X->>T: commit - delete the moved-aside copies
    T-->>X: on any exception before commit, run the undo list in reverse
```

### 4.6 `shelley build <tools-file>` (batch)

```mermaid
---
title: build batch (to-be)
---
sequenceDiagram
    actor U as User
    participant CMD as client.commands
    participant S as services
    participant P as privilege
    U->>CMD: shelley build tools.txt
    CMD->>S: build_many(specs)
    S->>S: resolve every spec first (part 1, as the user)
    Note over S: an unresolvable spec is recorded as failed, the others continue (as-is semantics)
    S->>P: one re-exec with every resolved tag - a single sudo prompt
    loop each resolved tag, in the root child
        P->>P: plan and apply (parts 2 and 3), one transaction per tag
    end
    S-->>CMD: list of BuildResult
    CMD-->>U: summary table, exit 0 only if all succeeded
```

### 4.7 `shelley clean <tool>:<tag> [-y]`

```mermaid
---
title: clean (to-be)
---
sequenceDiagram
    actor U as User
    participant CMD as client.commands
    participant S as services
    participant C as GalaxyCatalogue
    participant P as privilege
    participant X as ShpcExposer (root child)
    participant T as BuildTransaction
    U->>CMD: shelley clean samtools:1.21
    CMD->>S: clean("samtools:1.21", force)
    S->>C: installed("samtools") - LINKED or DANGLING tags
    alt no match or several
        S-->>U: typed error listing installed tags
    end
    S->>U: confirm unless -y
    S->>P: reexec(clean samtools --resolved-tag 1.21--h50ea8bc_3 -y)
    P->>X: remove(tool, tag)
    X->>T: shpc uninstall, unlink, remove authored registry tag
    X-->>CMD: CleanResult
    CMD-->>U: render
```

### 4.8 `shelley update` and the update notice

Unchanged from [current-state §4.8](current-state.md#48-shelley-update-and-the-update-notice),
except that the version fetch goes through `tools/net.py`.

---

## 5. Artefact lifecycle state diagram (to-be)

```mermaid
---
title: Galaxy tool:tag lifecycle (to-be)
---
stateDiagram-v2
    state "AVAILABLE - in snapshot, SIF verified on mount" as Available
    state "Planned - BuildPlan, nothing written" as Planned
    state "Applying - inside BuildTransaction" as Applying
    state "LINKED - loadable" as Linked
    state "DANGLING - link target removed outside shelley" as Dangling
    [*] --> Available
    Available --> Planned : plan - network, aliases, prompt
    Planned --> Available : NetworkUnavailable or cancel - no writes
    Planned --> Applying : apply
    Applying --> Linked : commit
    Applying --> Available : failure - undo; a replaced install is restored
    Linked --> Dangling : deleted outside shelley
    Linked --> Available : clean
    Dangling --> Available : clean
```

There is no orphaned state: every write happens inside `BuildTransaction`, and every
failure before `commit` is undone.

Legacy artefacts on VMs built with shelley ≤ 0.4.0 are handled as follows:
- A local entry that no `LINKED` tag uses and that has no marker is removed by the next
  build of that tool, inside its transaction.
- A local entry that is still in use gets the fresh upstream tags merged in.
- A module built while offline under T6 (no tool command) is fixed by
  `shelley clean <tool>:<tag>` followed by a rebuild.

---

## 6. Responsibility table (to-be)

| Module / class | Knows | Does | Collaborates with | Runs as |
|---|---|---|---|---|
| `client.commands` | argument syntax, help text, the hidden `--resolved-tag` flag | Parses, calls one service, renders; the CLI and the REPL loop over the same table | `services`, `client.render` | user |
| `client.render` | panel and table layouts | Renders result dataclasses | `utils.style` | user or root |
| `services` | use-case order | One function per use case; resolves before elevating; returns results | `GalaxyCatalogue`, `ShpcExposer`, `MetadataSource`, `privilege` | user (and root child) |
| `privilege` | sudo policy, re-exec argv | Decides on and performs the elevated re-exec | `sudo` | user |
| `GalaxyCatalogue` | snapshot schema, mount layout, `tool:tag` grammar, Lmod link layout | Lists, resolves, verifies and reports install state | `Tag`, snapshot, mount, Lmod directory | user |
| `Tag`, `tags.latest` | version grammar, conda ordering, non-version tags, mulled rule | Parses, orders, matches | vendored `VersionOrder` | either |
| `ShpcExposer` | shpc URI layout, registry entry schema, marker format, permission subtrees | Plans and applies builds; removes tags | `RegistryClient`, `LocalRegistry`, `guts_integration`, `Shpc`, `Lmod`, `BuildTransaction`, `perms` | root |
| `BuildTransaction` | undo actions recorded so far | Undoes in reverse unless committed | — | root |
| `RegistryClient` | upstream URL | Fetches an upstream entry, or `None` if not upstream | `net` | root |
| `LocalRegistry` | `/apps/local` layout, markers | Reads, writes, merges and removes authored entries | filesystem, `perms` | root |
| `Shpc`, `Lmod` | CLI argv, settings file, Lmod driver | Wrap one external tool each | `subprocess` | root |
| `net` | timeouts, error classification | Fetches; diagnoses failures in plain words | `urllib` | either |
| `MetadataSource` family | corpus formats, tokenisation | Loads, searches and looks up metadata | data files | user |
| `utils.globals`, `utils.perms` | shared layout and modes | Path resolution; permission hardening | — | either |
| `update`, `update_check` | uv layouts, release check | As-is | `net` | user |

---

## 7. Where Galaxy and shpc assumptions live (to-be)

The 14 assumptions in [current-state §7](current-state.md#7-hard-coded-galaxy-and-shpc-assumptions-as-is),
and where each one is held in the target design:

| # | Assumption | Held only in |
|---|---|---|
| 1 | Galaxy mount path | `galaxy/catalogue.py` (default from `utils.globals`) |
| 2 | Flat `tool:tag` files | `galaxy/catalogue.py` |
| 3 | `version--build` grammar | `tags.py` |
| 4 | `quay.io/biocontainers/<tool>` URI | `galaxy/exposer.py`, `galaxy/registry.py` |
| 5 | `shpc install --keep-path` plus a link | `galaxy/exposer.py`, `tools/shpc.py`, `tools/lmod.py` |
| 6 | Upstream shpc-registry on GitHub | `galaxy/registry.py` |
| 7 | Aliases from a guts diff | `builder/guts_integration.py` |
| 8 | Root, shpc and singularity for builds | `privilege.py`, `tools/` |
| 9 | One modulefile per `tool/tag.lua` | `galaxy/catalogue.py` (read), `tools/lmod.py` (write) |
| 10 | Versions from the bundled snapshot | `galaxy/catalogue.py` |
| 11 | `search` joined to Galaxy ids | `services.search` via `GalaxyCatalogue.tool_ids()` |
| 12 | User messages naming Galaxy | `client/render.py` |
| 13 | Hardening walks shpc subtrees | `galaxy/exposer.py` |
| 14 | Image-patched shpc module template | BioShell (unchanged) |

All shelley-side assumptions now sit in `galaxy/`, `tags.py`, `tools/`, `privilege.py`
and `client/render.py`. None remain in `services` or `client/commands.py`.

---

## 8. Target measures (to-be)

| Quality attribute (rank) | Target |
|---|---|
| Correctness (1) | `find`'s latest equals `build`'s default for every tool in the snapshot; no prefix matching anywhere |
| Shared-VM safety (2) | A failure injected at each `apply` step leaves `/apps` identical to before |
| Honest failures (3) | An offline build raises `NetworkUnavailable` before any write; `MountUnavailable` and resolution errors are reported before any sudo prompt |
| Testability (4) | Every service is testable with fakes for the catalogue, `Shpc`, `Lmod` and `RegistryClient`; no unmarked test touches `/apps`, `~`, the mount or the network |
| Operability (5) | No full-SIF read; no full mount listing on the default build path |
| Reviewability (6) | Delivered as moderate PRs, each reviewable in one sitting and named after Fowler refactorings |
| Extensibility (7) | A second supplier touches ≤ 3 modules (§9) |

---

## 9. Adding a second supplier (to-be)

A second supplier adds a catalogue class and an exposer class in its own package, plus a
name-to-pair lookup in `services`. When that second pair exists, a `typing.Protocol`
for each of the two roles is extracted from the two concrete classes. For EESSI (work
in progress), the exposer makes an existing module tree visible to Lmod and needs no
`BuildTransaction`. The open questions for that integration are tracked outside the
published docs.
