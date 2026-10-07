# Architecture glossary

The domain terms shelley uses, defined as the code uses them **now**. The same names
are used in the architecture diagrams ([current-state.md](current-state.md)) and should
be used in the code and docs.

- **Snapshot:** shelley `dev` @ `bb70383` (v0.4.0), BioShell `main` @ `8780dcc`, and a
  live BioShell VM inspected on 2026-10-07.
- **Evidence labels:** `[code]` source, with file:line · `[test]` exercised by a test ·
  `[doc]` docs only · `[runtime]` observed on the VM · `[inferred]` reasoning, not
  observed.
- Where docs and code disagree, the code is taken as the definition and the conflict is
  listed under [Conflicts between docs and code](#conflicts-between-docs-and-code).

---

## Agreed vocabulary

Canonical names agreed on 2026-10-07. Sections below record current usage, including where it differs.

| Term | Means | Replaces / distinct from |
|---|---|---|
| **Supplier** | An upstream that delivers runnable software (today: the Galaxy Singularity CVMFS directory) | "Source" when it means software; "CVMFS" when it means Galaxy only |
| **Metadata source** | A corpus of tool descriptions searched by shelley (RSEC, toolfinder) | "Source" alone |
| **Build** | Make a supplier's software loadable by writing artefacts under `/apps` (the Galaxy path) | "Install" when it means `shelley build` |
| **Expose** | Make a supplier's existing modules loadable without writing artefacts (reserved for the incoming EESSI supplier) | — |
| **Tag** | The full container tag, `<version>--<build_string>` | "Version" when the full string is meant |
| **Version** | The short version, the tag up to the first `--` | — |
| **Latest** | The newest version under one ordering rule (two rules exist today; see [Version](#version-tag-short-version-build)) | — |
| **Stack** | A module that delivers a set of R packages | Undefined in code today |

---

## shelley terms (as-is)

### Tool

A named piece of software a user asks for, such as `samtools`. In the code it has four
spellings, which are joined by string normalisation:

| Where | Field / form | Example | Evidence |
|---|---|---|---|
| Galaxy SIF filename | `tool_name`: text before the first `:` | `star-fusion` | `[code]` [cvmfs_builder.py:212-217](../../../shelley/builder/cvmfs_builder.py#L212-L217), [build_galaxy_cache.py:77-78](../../../shelley/scripts/build_galaxy_cache.py#L77-L78) |
| RSEC metadata | `id` (bio.tools id) and `name` | `star-fusion`, `STAR-Fusion` | `[code]` [find.py:61-67](../../../shelley/commands/find.py#L61-L67) |
| shpc registry URI | `quay.io/biocontainers/<tool_name>` | `quay.io/biocontainers/star-fusion` | `[code]` [cvmfs_builder.py:130](../../../shelley/builder/cvmfs_builder.py#L130), [:512](../../../shelley/builder/cvmfs_builder.py#L512), [:640](../../../shelley/builder/cvmfs_builder.py#L640) |
| Lmod module name | `<lmod_modules>/<tool_name>/` | `star-fusion/` | `[code]` [cvmfs_builder.py:573](../../../shelley/builder/cvmfs_builder.py#L573) |

- The join between RSEC and the Galaxy cache is case-insensitive, with `-` folded to
  `_` (`[code]` [cache.py:31](../../../shelley/utils/cache.py#L31),
  [search.py:29](../../../shelley/commands/search.py#L29)). `find` instead tries the
  `-`/`_` variants as written (`[code]` [cache.py:46-50](../../../shelley/utils/cache.py#L46-L50)).
- bio.tools ids and BioContainers names can differ, e.g. `seurat` vs `r-seurat`
  (`[doc]` [data-sources.md:183](../data-sources.md)).
- **Tool spec**: the CLI argument `<tool>[/<version>]` or `<tool>[:<version>]`. Both
  separators are accepted by `build` and `clean` (`[code]`
  [build.py:157-162](../../../shelley/commands/build.py#L157-L162),
  [clean.py:16-24](../../../shelley/commands/clean.py#L16-L24)).

### Version, tag, short version, build

| Term | Meaning | Evidence |
|---|---|---|
| **Tag** | The text after the first `:` in a Galaxy SIF filename. Usually the Bioconda form `<version>--<build_string>` | `[code]` [cvmfs_builder.py:215](../../../shelley/builder/cvmfs_builder.py#L215); `[doc]` [data-sources.md:216](../data-sources.md) |
| **Short version** | The tag up to the first `--` | `[code]` [cache.py:68](../../../shelley/utils/cache.py#L68), [cvmfs_builder.py:828](../../../shelley/builder/cvmfs_builder.py#L828) |
| **Build** | One SIF. A short version can have several builds that differ only in build string | `[code]` [cache.py:80-94](../../../shelley/utils/cache.py#L80-L94) |
| **Version** | Context-dependent: a short version (`find` table, `build` request), a full tag (modulefile name, shpc tag, `clean` match) | `[code]` see rows above and [cvmfs_builder.py:574](../../../shelley/builder/cvmfs_builder.py#L574) |

- 3,842 of the 122,520 cached tags have no `--` build string (e.g. `10x_bamtofastq:1.4.1`)
  `[runtime]`.
- Tags are not PEP 440 versions. `packaging` is used only for shelley's own update
  check (`[code]` [update_check.py:93-97](../../../shelley/utils/update_check.py#L93-L97)).
- **Version ordering has two implementations:**
  - `_version_key`, which keeps the leading digits only and is used by `find`
    (`[code]` [cache.py:16-21](../../../shelley/utils/cache.py#L16-L21));
  - `CVMFSModuleBuilder._parse_version`, which keeps every number in each dot-part and
    is used by `build` (`[code]` [cvmfs_builder.py:165-189](../../../shelley/builder/cvmfs_builder.py#L165-L189)).

  Over the bundled cache, the two disagree on the newest short version for 331 of 13,183
  tools, e.g. `bracken`: `find` lists `3.1` first, while `shelley build bracken` selects
  `3.1p1` `[runtime]`.

### Container / SIF

A Singularity Image Format (SIF) file on the Galaxy CVMFS mount, at
`/cvmfs/singularity.galaxyproject.org/all/<tool_name>:<tag>`. Entries are flat files
(`file` reports "run-singularity script executable") `[runtime]`. Code reads them as
files or symlinks (`[code]` [cvmfs_builder.py:211](../../../shelley/builder/cvmfs_builder.py#L211)).

- **Container path**: the full path above, shown by `find -v` (`[code]`
  [cache.py:80-94](../../../shelley/utils/cache.py#L80-L94)) and passed to
  `shpc install --keep-path`, which references the SIF in place rather than copying it
  (`[code]` [cvmfs_builder.py:263-284](../../../shelley/builder/cvmfs_builder.py#L263-L284)).
- **Base image**: a base OS image manifest (ubuntu, alpine, busybox, rockylinux, plus the
  bundled miniconda manifests) that is subtracted from a SIF's file list to find its
  aliases (`[code]` [guts_integration.py:56-61](../../../shelley/builder/guts_integration.py#L56-L61)).
- "Image" also means the BioShell VM image in the docs and the user guide.

### Module / modulefile

Four distinct things are called "module":

| Term | What it is | Location | Created by | Evidence |
|---|---|---|---|---|
| **Lmod modulefile** (user-facing) | Symlink `<tool>/<tag>.lua` → the shpc module | `/apps/Modules/modulefiles` (`SHELLEY_LMOD_MODULES_PATH`) | `shelley build` | `[code]` [cvmfs_builder.py:572-578](../../../shelley/builder/cvmfs_builder.py#L572-L578) |
| **shpc module** | Generated `module.lua` plus a `.version` default marker, under `quay.io/biocontainers/<tool>/<tag>/` | `/apps/shpc/modules` (`module_base`) | `shpc install` | `[code]` [globals.py:66-68](../../../shelley/utils/globals.py#L66-L68); `[doc]` [data-sources.md:15](../data-sources.md) |
| **BioShell modulefile** | Hand-written Tcl modulefile `<tool>/<ver>` (R, rstudio, nextflow, …) | `/apps/Modules/modulefiles` | Ansible role `common` and others | `[runtime]` |
| **Build modules** | The Lmod modules `shpc` and `singularity`, loaded into the process before a build | `/opt/Modules/modulefiles` | Ansible | `[code]` [globals.py:27](../../../shelley/utils/globals.py#L27), [modules.py:31-66](../../../shelley/utils/modules.py#L31-L66) |

- The Lmod modulefile and the BioShell modulefiles share one directory and one name
  space.
- **Installed** has two definitions:
  - `find`: some `<version>*.lua` under the tool directory resolves to a readable file
    (`[code]` [find.py:21-30](../../../shelley/commands/find.py#L21-L30));
  - `clean`: any `*.lua` exists, dangling symlinks included (`[code]`
    [find.py:33-43](../../../shelley/commands/find.py#L33-L43)).
- On this VM, `/apps/shpc/modules` holds 9 shpc `module.lua` files across 7 tools, and
  `/apps/Modules/modulefiles` holds no shelley symlinks, so none of them is loadable
  `[runtime]`.

### Alias and wrapper

- **Alias**: a `{name, command}` pair. `name` is what the user types; `command` is the
  executable inside the container (`[code]`
  [guts_integration.py:125-137](../../../shelley/builder/guts_integration.py#L125-L137)).
  It comes from one of three places:
  - the upstream registry entry's `aliases`;
  - a guts diff of the SIF against base images
    (`[code]` [guts_integration.py:82-122](../../../shelley/builder/guts_integration.py#L82-L122));
  - interactive curation with `build -i`
    (`[code]` [guts_integration.py:257-281](../../../shelley/builder/guts_integration.py#L257-L281)).
- **Wrapper**: the script shpc generates for each alias, which runs the alias's command
  inside the SIF. Wrappers live under `/apps/shpc/wrappers/quay.io/biocontainers/<tool>/<tag>/bin/`,
  and loading the module puts them on `PATH` (`[code]`
  [globals.py:76-78](../../../shelley/utils/globals.py#L76-L78); `[doc]`
  [build-modules.md:22](../../how-to/build-modules.md)). shelley does not write
  wrappers itself; shpc does.

### View

An shpc *view* is a named collection of installed shpc modules. shelley creates
`/apps/shpc/views` (`views_base`) only so that `shpc view` keeps working, and never
creates or installs into a view (`[code]` [globals.py:81-83](../../../shelley/utils/globals.py#L81-L83);
no `view` subcommand appears in any shpc call in `shelley/`). The `build` sequence has
no `shpc view install` step.

"View" in [cache.py:87](../../../shelley/utils/cache.py#L87) means the `find -v`
output, which is unrelated.

### Registry, registry entry, marker directory

- **shpc registry**: the place shpc looks up a container URI's `container.yaml`. shelley
  pins the search path, local registry first, then upstream (`[code]`
  [shpc_settings.py:47-64](../../../shelley/builder/shpc_settings.py#L47-L64)).
- **Upstream registry**: `github.com/singularityhub/shpc-registry` (`[code]`
  [globals.py:23](../../../shelley/utils/globals.py#L23)), fetched with `curl` from
  `raw.githubusercontent.com` (`[code]`
  [cvmfs_builder.py:86-92](../../../shelley/builder/cvmfs_builder.py#L86-L92)).
- **Local registry**: `/apps/local` (`SHELLEY_LOCAL_REGISTRY`) (`[code]`
  [globals.py:51-53](../../../shelley/utils/globals.py#L51-L53)).
- **Registry entry**: `<registry>/quay.io/biocontainers/<tool>/container.yaml`, with
  one file per tool covering every tag. Keys: `docker`, `tags` (`{tag: "sha256:<SIF digest>"}`),
  `aliases` (one list shared by every tag), `latest`, `maintainer`, `description`
  (`[code]` [cvmfs_builder.py:353-405](../../../shelley/builder/cvmfs_builder.py#L353-L405)).
  A local entry plays two roles in one file:
  1. **a cache of the upstream entry**, written best-effort by `get_registry_tags`
     (`[code]` [cvmfs_builder.py:101-111](../../../shelley/builder/cvmfs_builder.py#L101-L111)).
     In v0.4.0 nothing calls `get_registry_tags` at runtime (only tests do), so pure
     cache entries come from earlier shelley versions. On the dev VM, `star-fusion`
     has an upstream maintainer, no marker, and a tag (`1.0.0`) that is not upstream:
     an entry authored before marker directories existed `[runtime]`;
  2. **a shelley-authored entry** for tags missing upstream, or for interactively
     curated aliases (`[code]` [cvmfs_builder.py:526-550](../../../shelley/builder/cvmfs_builder.py#L526-L550)).
- **Marker directory**: `<entry dir>/<tag>/aliases.yaml`, which holds that tag's own
  aliases and an `in_upstream` flag. It is invisible to shpc, and is used by `clean` to
  decide whether to delete the tag (`[code]`
  [cvmfs_builder.py:410-425](../../../shelley/builder/cvmfs_builder.py#L410-L425),
  [:686-712](../../../shelley/builder/cvmfs_builder.py#L686-L712)).
- **In upstream**: the requested tag is a key of the freshly fetched upstream entry's
  `tags` (`[code]` [cvmfs_builder.py:521-524](../../../shelley/builder/cvmfs_builder.py#L521-L524)).

### Shared build layout and build roots

- **Build roots**: the three prefixes a build writes to, `/apps/shpc`, `/apps/local` and
  `/apps/Modules/modulefiles`. Each can be overridden by environment variable (`[code]`
  [globals.py:104-106](../../../shelley/utils/globals.py#L104-L106)).
- **Shared build layout**: the build roots plus the four shpc bases, all root-owned and
  world-readable (`[code]` [globals.py:91-101](../../../shelley/utils/globals.py#L91-L101),
  [perms.py](../../../shelley/utils/perms.py)).
- **Elevated re-exec**: when the build roots are not writable, `build` and `clean`
  re-run the same shelley with `sudo -E env PATH=… SHELLEY_*=…` (`[code]`
  [build.py:93-124](../../../shelley/commands/build.py#L93-L124),
  [clean.py:118-143](../../../shelley/commands/clean.py#L118-L143)).

### Build, install, clean

- **Build** (`shelley build`): resolve a tool spec to one Galaxy SIF; optionally write a
  local registry entry; run `shpc install --keep-path`; harden permissions; symlink the
  Lmod modulefile (`[code]` [cvmfs_builder.py:491-590](../../../shelley/builder/cvmfs_builder.py#L491-L590)).
- **Install** has three meanings:
  - installing shelley itself ([install.md](../../how-to/install.md));
  - `shpc install`, the step inside a build;
  - the "Install" panel in `find`, which suggests `shelley build`
    (`[code]` [find.py:283-291](../../../shelley/commands/find.py#L283-L291)).
- **Clean** (`shelley clean`): `shpc uninstall`; remove the Lmod symlink; prune the
  registry tag or entry (`[code]` [cvmfs_builder.py:592-721](../../../shelley/builder/cvmfs_builder.py#L592-L721)).

### Supplier / source

- **Supplier** does not appear in the code or docs. The requirements use it for an
  upstream that delivers runnable software, e.g. "EESSI as a direct supplier" (`[doc]`
  R/Python requirements draft v0.3, line 38).
- Today shelley has one supplier, the Galaxy Singularity CVMFS directory, and it is
  hard-coded: `cvmfs_singularity()` (`[code]`
  [globals.py:61-63](../../../shelley/utils/globals.py#L61-L63)), the `quay.io/biocontainers`
  URI prefix (`[code]` [cvmfs_builder.py:39](../../../shelley/builder/cvmfs_builder.py#L39))
  and the bundled cache.
- **Source** in the code means a **metadata source**: a corpus of tool descriptions,
  not of software. `MetadataSource` has two subclasses, `RsecSource` (used by `find`
  and `search`) and `ToolfinderSource` (used only by the maintainer scripts under
  `scripts/`) (`[code]` [base.py:21](../../../shelley/search/base.py#L21),
  [rsec.py:20](../../../shelley/search/rsec.py#L20),
  [toolfinder.py:20](../../../shelley/search/toolfinder.py#L20)).
- **Corpus**: the bundled metadata file of a metadata source, e.g. `rsec_meta.json.gz`,
  with 34,130 entries (`[doc]` [data-sources.md:118](../data-sources.md)).

### CVMFS repository / mount

- **CVMFS repository**: a read-only filesystem named by its fully qualified repository
  name, mounted on demand by autofs at `/cvmfs/<fqrn>` `[runtime]`.
  - Configured by the image: `data.galaxyproject.org`, `singularity.galaxyproject.org`
    (`[code]` BioShell `build/ansible/vars/tool-versions.yml:29`).
  - On this VM, `software.eessi.io` was also added by hand to
    `/etc/cvmfs/default.local`, with the `cvmfs-config-eessi` 0.6.0 package
    `[runtime]`.
  - `data.galaxyproject.org` is mounted but not read by shelley `[code]`.
- **Galaxy Singularity mount**: `/cvmfs/singularity.galaxyproject.org/all`, the only
  repository shelley reads (`[code]` [globals.py:16](../../../shelley/utils/globals.py#L16)).
- **CVMFS client cache**: the local disk cache of fetched CVMFS content, with a
  4,096 MB quota (`CVMFS_QUOTA_LIMIT`) `[runtime]`.
- In the code and in user messages, "CVMFS" means the Galaxy Singularity directory
  specifically, e.g. `_is_cvmfs_available`, "not found in CVMFS" (`[code]`
  [cvmfs_builder.py:158-163](../../../shelley/builder/cvmfs_builder.py#L158-L163),
  [:814-817](../../../shelley/builder/cvmfs_builder.py#L814-L817)).

### Index / cache

"Index" does not appear in the code. The docs use "CVMFS container index" for the
Galaxy container cache (`[doc]` [maintain-corpus.md:133](../../how-to/maintain-corpus.md)).
"Cache" has four meanings:

| Term | What it is | Read by | Evidence |
|---|---|---|---|
| **Galaxy container cache** | `shelley/data/galaxy_singularity_cache.json.gz`, a bundled snapshot of a directory listing of the Galaxy mount. Generated 2026-07-21: 122,520 entries, 13,187 tool names, including 4 non-container entries (`bin`, `*.py`, `bjoern.txt`) | `find`, `search` (filter) | `[code]` [cache.py:24-53](../../../shelley/utils/cache.py#L24-L53); `[runtime]` |
| **Registry cache** | A local registry entry holding a copy of the upstream entry | `get_registry_tags`, `shpc` | `[code]` [cvmfs_builder.py:71-113](../../../shelley/builder/cvmfs_builder.py#L71-L113) |
| **CVMFS client cache** | See CVMFS above | CVMFS client | `[runtime]` |
| **Update-check cache** | `~/.cache/shelley/update_check.json` (or `$XDG_CACHE_HOME`), with a 24 h time-to-live | startup notice | `[code]` [update_check.py:45-52](../../../shelley/utils/update_check.py#L45-L52) |

- `find` reads versions from the Galaxy container cache; `build` lists the live mount
  directory (`[code]` [find.py:58](../../../shelley/commands/find.py#L58),
  [cvmfs_builder.py:195-221](../../../shelley/builder/cvmfs_builder.py#L195-L221)).
  The two can therefore differ by whatever changed on the mount after the snapshot.

### Stack

"Stack" does not appear in the code. The requirements use it for a set of R packages
delivered together and activated as one unit:

- iteration 1: EESSI's `R-bundle-CRAN` and `R-bundle-Bioconductor` modules "are the only
  stacks" (`[doc]` R/Python requirements draft v0.3, line 6);
- deferred: SIH-curated stacks (F3) and trainer-built stacks (F6).

EESSI uses "software stack" for the whole of its software layer (`[doc]`
<https://www.eessi.io/docs/compatibility_layer/>).

---

## Incoming supplier: EESSI (work in progress)

EESSI (`/cvmfs/software.eessi.io`) is the intended second supplier. It is configured by hand on the dev VM and is not part of the BioShell image or of shelley yet `[runtime]`. Its terms (EESSI version, compatibility and software layers, CPU target, toolchain, toolchain-suffixed module names) will be added here when the integration is designed.

## Overloaded and inconsistent terms

| Term | Meanings in use | Where they collide |
|---|---|---|
| Tool | SIF `tool_name`, RSEC `id`/`name`, shpc URI segment, Lmod module name | Joined by case and `-`/`_` folding in two different ways |
| Version | Short version, full tag | `find` shows short versions; modulefiles and `clean` use full tags |
| Latest | Newest by `_version_key` (`find`) vs newest by `_parse_version` (`build`) | 331 tools resolve differently `[runtime]` |
| Installed | Readable modulefile (`find`) vs any `.lua` name (`clean`) | `find` and `clean` can disagree on the same tool |
| Module | Lmod modulefile, shpc module, BioShell modulefile, build modules | Lmod modulefiles and BioShell modulefiles share one directory and name space |
| CVMFS | Any CVMFS repository vs the Galaxy Singularity directory | Code and user messages say "CVMFS" when they mean Galaxy only |
| Cache | Galaxy container cache, registry cache, CVMFS client cache, update-check cache | — |
| Source | Metadata source (code) vs software supplier (requirements) | No shared term for "where runnable software comes from" |
| Stack | R package set (requirements) vs a whole software distribution (EESSI docs) | Undefined in code |
| Install | Install shelley, `shpc install`, `find`'s "Install" panel = `shelley build` | — |
| Image | VM image, SIF, base OS image manifest | — |

## Conflicts between docs and code

| Doc says | Code or runtime shows | Evidence |
|---|---|---|
| README Documentation table links `docs/tutorials/nfcore-rnaseq.md` | File does not exist | `[runtime]` |
| README Architecture tree lists `script/` | Package directory is `scripts/` | `[code]` |
| `galaxy_singularity_cache.json.gz` is used by `find` "and `list`" | There is no `list` command; `list_cvmfs_versions` has no callers | `[doc]` [data-sources.md:194](../data-sources.md); `[code]` [build.py:206](../../../shelley/commands/build.py#L206) |
| Each Galaxy entry is "a `tool:tag` container directory" | Entries are flat SIF files | `[code]` [build_galaxy_cache.py:69](../../../shelley/scripts/build_galaxy_cache.py#L69); `[runtime]` |
| Interactive help lists `find`, `search`, `build` | The REPL also dispatches `clean` | `[code]` [commands.py:9-25](../../../shelley/utils/commands.py#L9-L25), [interactive.py:68-73](../../../shelley/commands/interactive.py#L68-L73) |
| Design brief: build = resolve → registry entry → `shpc install` → `shpc view install` → link | No `shpc view` call exists | `[code]` [cvmfs_builder.py:491-590](../../../shelley/builder/cvmfs_builder.py#L491-L590) |
| `uninstall_module` docstring: `shelley find` calls `get_registry_tags` | `find` no longer calls it; it has no runtime caller | `[code]` [cvmfs_builder.py:601-605](../../../shelley/builder/cvmfs_builder.py#L601-L605) |
| Design brief: "122k Galaxy entries" | 122,520 in the bundled cache; `data-sources.md` example still says 118,594 | `[runtime]`; `[doc]` [data-sources.md:202](../data-sources.md) |
