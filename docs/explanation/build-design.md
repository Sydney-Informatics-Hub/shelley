# Build design

Design choices for `shelley build`. For how to build modules, see
[../how-to/build-modules.md](../how-to/build-modules.md). For the paths, owners and modes
a build writes, see [../reference/data-sources.md](../reference/data-sources.md).

## Three build paths: upstream, local and interactive

`shpc install` can only install a tag that a registry entry lists. The three paths differ
in where that entry comes from:

- **Upstream (default):** the version is in the [shpc-registry](https://github.com/singularityhub/shpc-registry),
  so shpc uses upstream's entry and its aliases as they are.
- **Local:** the version is on the Galaxy mount but absent upstream (older patch releases
  and some tools), so shelley writes its own entry.
- **Interactive (`-i`):** the user curates the aliases, and shelley writes them to its own
  entry, whether or not the version is upstream.

### Local registry entries

shelley writes its entries to `/apps/local/<uri>/container.yaml`, the local registry,
which shpc searches first:

| Case | Aliases come from | Marker records |
|---|---|---|
| The version is absent upstream | Alias discovery on this version's SIF | `in_upstream: false` |
| `-i` is used, for any version | Upstream's aliases if the version is upstream, else alias discovery; then the user's edits | `in_upstream` as fetched |

Each authored version also gets a marker, `<uri>/<tag>/aliases.yaml`, so that `clean` can
tell which tags shelley added ([clean-design.md](clean-design.md#shelley-creates-versioned-tool-subdirectories)).

shpc uses the *first* entry it finds and never falls through to upstream, so a local entry
hides upstream for every tag of that tool. The local registry therefore never caches
upstream entries, and each build merges fresh upstream tags into an existing local entry,
so a curated `-i` entry cannot block newer upstream versions.

### Alias discovery and its limitations

Aliases become the module's wrapper scripts, the commands available after `module load`.
For a local entry they are discovered by diffing the version's own SIF against base OS
images ([shpc-guts](https://github.com/singularityhub/shpc-guts)); what remains should be
the tool's own executables. `shelley/data/guts_db/` adds conda manifests to the
subtraction, so the ~90 conda binaries in every BioContainers image (`mamba`, `pip3`, …)
are not exposed.

Aliases are never copied from another version, because container contents differ. If
`star-fusion 1.0.0` inherited `1.10.1`'s entry, it would expose `salmon`, which only
`1.10.1` contains, and `salmon` would fail or silently run another copy from `PATH`
(`test_extract_aliases_star_fusion_1_0_0` guards this).

The diff is a heuristic with two known limits:

- **A tool named like a base binary** (`sort`, `time`, `join`) would be dropped, because
  base-image binaries are matched by name. Discovery passes the tool's name as `keep=`.
- **Discovery that fails for any reason other than the network** gives no aliases; the
  build continues and warns that the module has no wrapper scripts.

Running `shelley build --interactive/i` resolves this by allowing users to
handpick which aliases should be included. Because `aliases` is one
field shared by every tag in a `container.yaml`, each version's list is also kept in its
versioned subdirectory ([clean-design.md](clean-design.md#why-marker-directories-also-snapshot-that-versions-aliases)).

## Failed or cancelled builds leave nothing behind

Earlier versions left artefacts behind when a build failed or was cancelled part-way, and
`shelley clean` could not see them because they had no modulefile link. So a build now
removes everything it wrote unless it finishes. It writes:

| Artefact | Path | Written by |
|---|---|---|
| Local registry entry and marker (some builds) | `/apps/local/quay.io/biocontainers/<tool>/container.yaml`, `…/<tool>/<tag>/aliases.yaml` | shelley |
| shpc module, wrapper scripts, container directory | `/apps/shpc/{modules,wrappers,containers}/quay.io/biocontainers/<tool>/<tag>/` | `shpc install` |
| Permission changes | the directories above | shelley |
| Lmod modulefile link | `/apps/Modules/modulefiles/<tool>/<tag>.lua` | shelley |

### `BuildPlan` and `BuildTransaction`

1. **`plan`** decides everything before writing anything: it fetches the upstream registry
   entry, discovers aliases, asks the `-i` questions, and returns a `BuildPlan`.
2. **`apply`** performs the writes inside a `BuildTransaction`, which first records a
   *pre-image* of the tool's five directories (local entry, the three shpc directories and
   the Lmod directory): every path's type, mode, symlink target and bytes. Unless
   `commit()` runs, it restores that pre-image: new paths deleted, changed files rewritten.

A rebuild first renames the installed version aside (`<name>.aside`), so `apply` either
succeeds completely or changes nothing: rebuilding `samtools/1.19` and failing part-way
leaves the previous `samtools/1.19` in place. Cancelling `-i` on an installed version
prints "Build cancelled; nothing was changed." and the module still runs.

Two builds of the same tool would write the same directories, so the transaction holds a
per-tool lock (`/apps/shpc/.locks/<tool>.lock`). A second build waits up to five minutes,
then stops; builds of different tools never wait.

Two alternatives were rejected. Reordering the steps and adding `try/except` cleanup would
not stop the next change from writing before the last prompt, whereas a plan object makes
"no writes before `apply`" testable. Letting `clean` or a cleanup tool find orphans treats
the symptom: shelley should not create them.

## Built modules are usable by every account

BioShell training VMs are snapshotted into images, so a module built once must work for
every training account on every VM made from that image.

### Root-owned and globally accessible

Artefacts stay `root:root`: directories and wrapper scripts `0755`, files `0644`. Handing
the tree to the builder (`chown -R $SUDO_USER`) was rejected, because it lets one user
rewrite modules everyone else runs. A `umask 022` plus a `chmod` pass over the tool's
directories ensure no level is left untraversable, which would hide every module below it.

### shpc is pinned to shelley's settings file

shpc's defaults put every install base under `$HOME`, and a build runs under `sudo -E`,
which preserves `HOME`, so root would install into the builder's home, which on Ubuntu
nobody else can enter. shelley passes `/apps/shpc/settings.yml` to every shpc call as
`--settings-file`, the highest-precedence layer. The file is partial: it sets only the four
install bases and `registry` (local first), and inherits shpc's defaults otherwise.

The alternatives (`shpc config set --central`, `-c set:`, `HOME=/apps/shpc`) lose to a
per-user config, are ignored for `registry`, or leak into other `$HOME` users such as git.

## Build steps and error handling

A build runs in four steps: resolve the request as the user, elevate with `sudo`, `plan` as
root, then `apply`. Each failure is reported at the earliest step that can detect it, so
a typo never costs a password and nothing reaches `apply` that could fail in `plan`:

| Failure | Example | Reported |
|---|---|---|
| Unknown tool or version | `shelley build samtools/9.9` | Before the password prompt, with the available versions |
| A version with several builds | `shelley build samtools/1.21` | Before the password prompt: the user picks one |
| A `mulled-*` container with no tag | `shelley build mulled-v2-…` | Before the password prompt, listing the tags |
| Galaxy mount absent, or the SIF missing from it | — | Before the password prompt |
| GitHub unreachable | — | After the password prompt, in `plan`, before any write |
| `-i` cancelled | — | After the password prompt, in `plan`, before any write |

The root child receives only the resolved tag, and accepts only a `tool:tag` it can verify
on the mount:

```
sudo -E env PATH=… SHELLEY_…=… python -m shelley build --resolved-tag samtools:1.21--h50ea8bc_3
```

Network failures and `-i` come after it because `plan` runs in the root child.

"Not upstream" and "unreachable" are kept distinct: only HTTP 404 means a tag is absent
upstream. If an outage were read as "not upstream", the build would write a local entry
with no aliases, and that entry would keep hiding upstream, leaving a module without its
command even after the network returned. Any other failure of the registry fetch, or of
the clone of the base-image manifests for alias discovery, stops the build in `plan`:

> Couldn't reach GitHub (raw.githubusercontent.com): the request timed out after 10 s.
> Try again in a few seconds.
