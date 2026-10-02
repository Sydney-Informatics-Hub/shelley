# Build design

Why the module builder is designed the way it is.

## Why shelley pins shpc to its own settings file

A built module has to be usable by every user on the machine, not just whoever ran the
build. That turns out to hinge entirely on where shpc installs.

shpc's central settings put every install base under `$HOME` — `module_base:
$HOME/shpc/modules` and likewise for `container_base`, `wrapper_base` and `views_base`.
Those keys are on shpc's environment-expansion list, so `$HOME` is expanded when the value
is read, not when the file is written. `shelley build` re-execs under `sudo -E`, which
preserves `HOME`. The result: **root writes the modules into the invoking user's home
directory**, which on a default Ubuntu install is `drwxr-x---` — unreadable and even
untraversable by anyone else. The modulefile symlink under `/apps/Modules/modulefiles`
points into a tree nobody but the builder can enter.

So shelley writes `/apps/shpc/settings.yml` and passes it to every shpc invocation as
`--settings-file`. That is the highest-precedence layer in shpc's resolution chain, above
`~/.singularity-hpc/settings.yml` and above the central defaults, which makes the build
immune to both `HOME` and a per-user shpc config. The file is *partial*: shpc always loads
its own defaults first and merges ours over the top, so shelley declares only the five keys
it cares about and inherits future upstream defaults for everything else.

Three alternatives were considered and rejected:

- **`shpc config set --central`** rewrites the ansible-managed `/opt` install shared with
  everyone who calls `shpc` directly, and it gets clobbered on any shpc upgrade. It also
  does not actually solve the problem: central is the *lowest* precedence layer, so a user
  with `~/.singularity-hpc/settings.yml` would still build into their own home.
- **`-c set:key:value` on every call** is applied after shpc has already constructed its
  registry from the unpatched settings, so `-c set:registry:…` is silently ineffective
  while `-c set:module_base:…` works. Asymmetric, and it leaves nothing on disk to inspect.
- **`env HOME=/apps/shpc`** happens to work, purely because the shpc defaults contain
  `$HOME`. It breaks silently if those defaults ever become absolute paths, gives no
  control over `registry`, and leaks into every other `$HOME` consumer in the subprocess
  tree — Singularity's cache, git, uv — depositing junk under `/apps/shpc`.

A corollary: shelley no longer calls `shpc config add registry` to register `/apps/local`.
shpc's config save writes the whole *merged* settings dict, which would expand our small
override file into a frozen snapshot of today's site defaults. The registry list is
declared in the settings file instead.

## Why artifacts are root-owned 0755 rather than chowned to the builder

Builds used to end with `chown -R $SUDO_USER:$SUDO_USER` over the shpc base, to let
subsequent non-root shpc calls write to the same paths. That is directly at odds with a
shared install: it hands the tree to one account, and even at `0755` it lets one
unprivileged user rewrite modules that everyone else executes.

Artifacts now stay `root:root` with directories `0755`, files `0644` and wrapper scripts
`0755`. Nothing but the privileged build path needs to write there, so read, traverse and
execute for everyone is both sufficient and strictly safer. Tests that need a writable
tree point `SHELLEY_SHPC_BASE` at a temporary directory instead of relying on ownership of
a production path.

Permissions are enforced in two layers — a `umask 022` set before anything forks, plus an
explicit `chmod` pass over the subtrees the build touched. Neither suffices alone: the
umask does not fix directories a previous build created under a stricter one, and the chmod
pass would have to walk all of `/apps/shpc` to find them, which gets slower with every
module installed. The pass is scoped per tool rather than per version, because shpc writes
a `.version` file beside the version directories to tell Lmod which is the default — an
unreadable one breaks a bare `module load <tool>` for everyone else.

## Why local registry aliases are generated fresh from each SIF

`shelley build` has two paths depending on whether the requested version is in the upstream [shpc-registry](https://github.com/singularityhub/shpc-registry):

- **Version in upstream registry** — `shpc install` is called directly; the upstream registry's `aliases` field is used as-is. The one exception is `--interactive`: curating aliases always routes through a local entry (below) so the edit persists and shadows upstream, even though the version itself is not "absent" in the sense this section otherwise describes.
- **Version absent from upstream** — shelley creates a local `container.yaml` under `/apps/local/` (declared as the first entry in shpc's registry search path by shelley's settings file, so local entries shadow upstream ones). As part of building that entry, it calls `extract_aliases` to diff the exact CVMFS SIF and generate the `aliases` field fresh. The local entry is never copied or inherited from another version of the same tool.

The reason for the no-inheritance rule is correctness. A concrete failure mode: if `star-fusion 1.0.0` inherited the local registry entry from `star-fusion 1.10.1`, the module would expose `salmon` as an alias — because `salmon` was present in the `1.10.1` container but absent from `1.0.0`. Any user running `module load star-fusion/1.0.0` and calling `salmon` would get a command-not-found error, or silently pick up a wrong binary from elsewhere on PATH.

The regression test `test_extract_aliases_star_fusion_1_0_0` explicitly asserts that `salmon` does not appear in the `1.0.0` alias list. `star-fusion 1.0.0` uses the local fallback path (`newly_created=True` in the regression matrix), so this test exercises the alias generation directly.

Regenerating aliases fresh keeps each version's own *install* correct, but `aliases` is one field shared by the whole `container.yaml` file — so building a second locally-curated version of the same tool still overwrites what's on disk with that version's own aliases. `shelley clean` addresses this by snapshotting each locally-curated version's aliases into its own marker directory; see [clean-design.md](clean-design.md#why-marker-directories-also-snapshot-that-versions-aliases).

## Why guts_db exists — the conda subtraction problem

`shelley build` discovers tool aliases by diffing the tool's container against a database of base OS images (the [shpc-guts](https://github.com/singularityhub/shpc-guts) database). The diff returns files that are unique to the tool container — in theory, the tool's own executables.

In practice, BioContainers conda packages install the tool _and_ a full conda stack (`python`, `pip`, `conda`, `mamba`, ~90 conda-infrastructure binaries) into `/opt/conda/bin/` or `/usr/local/bin/`. The base OS images in shpc-guts contain neither conda nor these executables, so the diff returns all ~90 conda binaries as "unique" — inflating the alias list with entries like `mamba`, `pip3`, `activate`, and so on that are not tool-specific.

`shelley/data/guts_db/` is a supplementary manifest database in the same JSON format as shpc-guts. At runtime, `extract_aliases` merges `guts_db/` into the sparse-cloned shpc-guts working directory before running the diff. This adds conda-layer manifests (`anaconda/miniconda`, `continuumio/miniconda3`) to the subtraction set, removing ~90–100 spurious entries from every BioContainers alias list.

The two current manifests cover slightly different conda installations:

| Image | Covers |
|---|---|
| `anaconda/miniconda:latest` | `/opt/miniconda3/bin` |
| `continuumio/miniconda3:latest` | `/opt/conda/bin` — the standard BioContainers layer |

Without `continuumio/miniconda3`, roughly 100 extra conda-infrastructure executables appear as tool aliases.

## The relocation problem — why base images leaked through the diff

Adding manifests to the subtraction set only helps when the base image and the tool container agree on _where_ a binary lives. They often don't, and until [container-guts](https://github.com/Sydney-Informatics-Hub/guts) grew basename matching, the diff compared whole path strings and so missed every relocated copy:

- shpc-guts' `busybox` manifests record every applet at `/bin/<name>`. BioContainers images built on busybox symlink the same applets into `/sbin`, `/usr/bin` and `/usr/sbin`. `/bin/devmem` and `/sbin/devmem` are different strings, so `devmem` came back as unique to the tool.
- Ubuntu keeps ncurses at `/usr/bin/{clear,reset,tic,tput}`; conda ships its own copies under `/usr/local/bin/`. Same failure.

On the `biocontainers/samtools` reference diff in the guts repo this accounted for 22 of 29 alias candidates — `devmem`, `freeramdisk`, `makedevs`, `runlevel`, `dnsd`, `inetd`, `telnet`, `tftp`, `lspci`, `clear`, `reset`, `tic`, `tput` and friends. Crucially, **adding base images does not fix it**: all 29 still survived with `debian`, `centos` and `fedora` added to the subtraction set, because the problem was never a missing image. That measurement is also why those three families are deliberately absent from `BASE_IMAGE_NAMESPACES` — once basename matching is doing the work, `ubuntu` and `busybox` plus the conda manifests supply every name the other families would, and the reference diff returns an identical alias list either way.

The fix lives in guts, not shelley: `Database.diff` now also drops entries whose *basename* belongs to a base image, and reports them under a new `shadowed_paths` key. An executable on PATH is identified by its name, not its absolute location, so this belongs in the library where every guts consumer benefits. `unique_fs` is deliberately left as a plain path-level difference, since `guts similar` scores off it.

Shelley keeps one piece of policy on top: basename matching would also drop a tool legitimately named like a base binary (`sort`, `time`, `join`), so `extract_aliases` takes a `keep=` argument — the tool name — and pulls that one back out of `shadowed_paths`.

## Local registry fallback — when and why it triggers

The upstream [shpc-registry](https://github.com/singularityhub/shpc-registry) does not carry every version of every tool. Older patch releases and some tools are present in CVMFS but absent from the registry.

A local entry is created when the requested version has no upstream registry entry, **or** whenever `--interactive` is used — even for a version that *is* upstream, so that curated aliases persist and shadow the upstream entry. When `shelley build` takes either path, it:

1. Creates or updates a `container.yaml` under `/apps/local/<uri>/` (the local shpc registry path, declared in shelley's settings file rather than registered via `shpc config add`).
2. Retries `shpc install` pointing at the local registry.

This is transparent to the user — it adds a few minutes to the build and is logged (only for the absent-upstream case; an interactive curation of an upstream version is not itself a fallback). The `newly_created` flag in the regression matrix (see [docs/reference/data-sources.md](../reference/data-sources.md)) records which tools consistently require a local entry for this second reason. Both paths are marked with a per-version marker directory so `shelley clean` can find them later — see [clean-design.md](clean-design.md#why-per-version-marker-directories-exist).
