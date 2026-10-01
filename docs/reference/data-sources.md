# Data sources reference

Technical facts about every data artifact shelley bundles or reads at runtime.

---

## Key paths

Paths involved in a `shelley build` run, in the order they are touched:

| Path | Written by | Owner / mode | Why it matters |
|---|---|---|---|
| `/cvmfs/singularity.galaxyproject.org/all/` | Galaxy Project (read-only) | — | Source SIF files; `shelley build` reads from here, never writes |
| `/apps/shpc/settings.yml` | `shelley build` | `root:root` `0644` | shelley-managed shpc settings, passed to every `shpc` call as `--settings-file`. Do not edit; regenerated on each build |
| `/apps/shpc/modules/` | shpc | `root:root` `0755` | shpc `module_base` — generated `module.lua` and the `.version` default marker |
| `/apps/shpc/wrappers/` | shpc | `root:root` `0755` (scripts `0755`) | shpc `wrapper_base` — the per-alias wrapper scripts a loaded module puts on `PATH` |
| `/apps/shpc/containers/` | shpc | `root:root` `0755` | shpc `container_base` — near-empty, because `shpc install --keep-path` references the SIF in CVMFS instead of copying it |
| `/apps/shpc/views/` | shpc | `root:root` `0755` | shpc `views_base` — unused by shelley, created so `shpc view` stays usable |
| `/apps/local/<uri>/container.yaml` | `shelley build` | `root:root` `0644` | Local shpc registry entry: tags for tool versions **absent** from the upstream shpc-registry, plus a cache of upstream's own entry (written any time `shelley find`/`build` resolves versions). One file per tool, covering every tag — required by shpc's own registry lookup. See [clean-design.md](../explanation/clean-design.md) |
| `/apps/local/<uri>/<version>/` | `shelley build` | `root:root` `0755` | Marker directory, one per locally-curated tag (absent upstream). Holds `aliases.yaml`, a snapshot of that version's own aliases — `container.yaml`'s `aliases` field is shared across every tag, so this is the only place an earlier version's aliases survive a later version's build. Invisible to shpc; shelley-only bookkeeping |
| `/apps/Modules/modulefiles/<tool>/<version>.lua` | `shelley build` | symlink (mode not applicable) | Symlink into `/apps/shpc/modules/`; what `module avail` and `module load <tool>/<version>` resolve |

### Permissions model

Artifacts are **root-owned and world read + execute**: directories `0755`, files `0644`,
wrapper scripts `0755`, and never group- or other-writable. Any user on the machine can
`module load` a tool that any admin built; only the privileged build path writes.

Two mechanisms enforce this, because either alone leaves a gap:

- **`umask 022`**, set by `shelley build` before anything forks, so every file shpc
  creates starts out shared. Needed because `sudo` unions the caller's umask with the
  sudoers default — a user with `umask 077` would otherwise produce `0700` directories
  inside `/apps`.
- **an explicit `chmod` pass** over the subtrees the build touched (`a+rX` semantics:
  a file the owner can execute becomes `0755`, everything else `0644`). This catches
  directories created by an earlier build under a stricter umask, or by a direct `shpc`
  call outside shelley. It is scoped per tool, not to all of `/apps/shpc`, so build time
  does not grow as modules accumulate. Symlinks are skipped, never chmodded — `chmod`
  follows them, which would reach into read-only CVMFS.

shelley does **not** `chown` artifacts to the invoking user. Doing so would make the tree
single-user, and would let one unprivileged account rewrite modules everyone else runs.

### Overriding the layout

The three roots honour environment variables, mainly for testing (the test suite
redirects them into a tmp directory) and for a differently provisioned host:

| Variable | Default |
|---|---|
| `SHELLEY_SHPC_BASE` | `/apps/shpc` |
| `SHELLEY_LOCAL_REGISTRY` | `/apps/local` |
| `SHELLEY_LMOD_MODULES_PATH` | `/apps/Modules/modulefiles` |

They are forwarded explicitly across the `sudo` re-exec, so the elevated child agrees
with the parent about where to build.

> `SHELLEY_SHPC_BASE` is effectively write-once. A generated `module.lua` bakes in
> absolute wrapper and container paths, so changing the base after modules exist leaves
> every existing module pointing at a path that no longer holds anything. Rebuild rather
> than relocate.

---

## `toolfinder_meta.yaml`

Sourced from [AustralianBioCommons/finder-service-metadata](https://github.com/AustralianBioCommons/finder-service-metadata/blob/main/data/data.yaml).

Each record is a YAML object. Key fields:

| Field | Type | Notes |
|---|---|---|
| `id` | string | Primary tool identifier, used as lookup key |
| `name` | string | Human-readable display name |
| `biotools` | string | bio.tools identifier (may differ from `id`) |
| `biocontainers` | string | BioContainers name (used for container lookup) |
| `description` | string \| null | Free-text description |
| `edam-operations` | list \| null | Controlled vocab for what the tool does |
| `edam-topics` | list \| null | Controlled vocab for scientific domain |
| `homepage` | string \| null | Project homepage URL |
| `license` | string \| null | SPDX identifier |

Field coverage across 714 entries (measured 2026-06-02):

| Field | Coverage |
|---|---|
| `id` | 100 % |
| `name` | 100 % |
| `description` | 72.5 % |
| `biotools` | 72.5 % |
| `edam-operations` | 69.7 % |
| `edam-topics` | 69.7 % |
| `homepage` | 78.7 % |
| `license` | 48.2 % |
| `biocontainers` | 16.9 % |
| `edam-inputs` | 22.5 % |
| `edam-outputs` | 19.6 % |

```bash
python3 shelley/scripts/assess_coverage.py toolfinder
```

---

## `rsec_meta.json.gz`

Built from [research-software-ecosystem/content](https://github.com/research-software-ecosystem/content) `*.biotools.json` files. See [docs/explanation/search-design.md](../explanation/search-design.md) for why only bio.tools entries are ingested.

Top-level structure:

```json
{
  "generated_at": "2026-06-02T...",
  "source": "https://github.com/research-software-ecosystem/content",
  "source_ref": "master",
  "source_commit": "7ac28185...",
  "entry_count": 34130,
  "field_coverage": {
    "name": 100.0, "description": 100.0, "homepage": 100.0,
    "license": 45.1, "edam-operations": 91.6, "edam-topics": 95.0,
    "edam-inputs": 11.7, "edam-outputs": 9.7
  },
  "entries": [
    {
      "id": "bwa", "name": "BWA", "biotools_id": "bwa",
      "description": "...", "homepage": "...", "license": "GPL-3.0",
      "edam-operations": ["Read mapping", "Sequence alignment"],
      "edam-topics": ["Genomics", "Mapping"],
      "edam-inputs": ["Nucleic acid sequence", "FASTQ"],
      "edam-outputs": ["Sequence alignment map", "SAM"]
    }
  ]
}
```

Field coverage across 34,130 entries (RSEC commit `7ac28185`):

| Field | Searched? | Coverage |
|---|---|---|
| `name` | Yes | 100 % |
| `description` | Yes | 100 % |
| `edam-operations` | Yes | 91.6 % |
| `edam-topics` | Yes | 95.0 % |
| `homepage` | No | 100 % |
| `license` | No | 45.1 % |
| `edam-inputs` | No | 11.7 % |
| `edam-outputs` | No | 9.7 % |

```bash
# From committed artifact (no network):
python3 shelley/scripts/assess_coverage.py rsec

# From upstream (re-fetches, ~90 s):
shelley-build-rsec --assess
```

### Per-tool field coverage — regression tools

Cross-reference of the regression tool matrix against both corpora. Numbers are counts of EDAM terms populated in the RSEC bio.tools entry. `—` = tool absent from that corpus, or field empty.

| Tool | In RSEC? | In TF? | edam-operations | edam-topics | edam-inputs | edam-outputs |
|---|---|---|---|---|---|---|
| fastqc | ✓ | ✓ | 3 | 3 | 5 | 2 |
| multiqc | ✓ | ✓ | 2 | 4 | — | 7 |
| salmon | ✓ | ✓ | 3 | 3 | 4 | 2 |
| bcftools | ✓ | ✓ | 2 | 4 | 3 | 3 |
| bwa-mem2 | ✓ | ✓ | 1 | 1 | 2 | — |
| fastp | ✓ | ✓ | 2 | 2 | — | — |
| sambamba | ✓ | ✓ | 2 | 3 | — | — |
| samblaster | ✓ | — | 1 | 3 | — | — |
| samtools | ✓ | ✓ | 7 | 4 | 4 | 4 |
| blast | ✓ | ✓ | 2 | 2 | 2 | 9 |
| star | ✓ | ✓ | 1 | 2 | 2 | 4 |
| star-fusion | ✓ | ✓ | 1 | 2 | — | — |
| seurat | ✓ | ✓ | — | 2 | — | — |
| parabricks | — | — | — | — | — | — |
| tidyverse | — | — | — | — | — | — |

Notable absences:
- **parabricks** — proprietary NVIDIA GPU toolkit; not in bio.tools. Use `find`/`build` by exact name.
- **tidyverse** — general-purpose R framework; absent from both corpora as `tidyverse` and `r-tidyverse`.
- **seurat** — indexed as `seurat` (bio.tools name), not `r-seurat` (Bioconda convention). Only topics populated.
- **star-fusion** — indexed as `star_fusion` (underscore) in toolfinder.

```bash
python3 shelley/scripts/assess_regression_tools.py
```

---

## `galaxy_singularity_cache.json.gz`

A gzipped JSON snapshot of the CVMFS Singularity image cache, generated by scanning `/cvmfs/singularity.galaxyproject.org/all`. Used for fast version lookups by `find` (including `find -v`) and `list`.

Top-level structure:

```json
{
  "generated_at": "2026-01-28T03:40:51.706534+00:00",
  "cvmfs_root": "/cvmfs/singularity.galaxyproject.org/all",
  "entry_count": 118594,
  "entries": [
    {
      "entry_name": "fastqc:0.12.1--hdfd78af_0",
      "tool_name": "fastqc",
      "tag": "0.12.1--hdfd78af_0",
      "path": "/cvmfs/singularity.galaxyproject.org/all/fastqc:0.12.1--hdfd78af_0",
      "size_bytes": 293400576,
      "mtime": 1697123456.0
    }
  ]
}
```

`tool_name` is the join key with metadata. Tags follow the Bioconda convention: `<version>--<build_string>`.

---

## `shelley/data/guts_db/` — supplementary guts manifests

Singularity manifests used at build time to subtract conda infrastructure from tool alias detection. See [docs/explanation/build-design.md](../explanation/build-design.md) for the reasoning.

Current manifests:

| Image | Install path | Purpose |
|---|---|---|
| `anaconda/miniconda:latest` | `/opt/miniconda3/bin` | Base conda tooling |
| `continuumio/miniconda3:latest` | `/opt/conda/bin` | Python-3 conda layer used by BioContainers |

The base OS families themselves are not committed here — they are sparse-cloned at build time from shpc-guts per `BASE_IMAGE_NAMESPACES` in `shelley/builder/guts_integration.py`.

---

## Regression tool matrix

Canonical regression set for `shelley build`. Verified by `test_ensure_local_registry_entry_newly_created` and `test_ensure_local_registry_entry_upstream_known` in `tests/test_cvmfs_builder.py`.

| Tool | Canonical version (CVMFS) | In upstream registry | newly_created | Key aliases |
|---|---|---|---|---|
| fastqc | `0.12.1--hdfd78af_0` | ✓ | False | `fastqc` |
| multiqc | `1.19--pyhdfd78af_0` | ✓ | False | `multiqc` |
| salmon | `1.10.1--h7e5ed60_0` | ✓ | False | `salmon` |
| bcftools | `1.23.1--hb2cee57_0` | ✓ | False | `bcftools` |
| bwa-mem2 | `2.2.1--he70b90d_8` | ✓ | False | `bwa-mem2` |
| fastp | `0.20.0--hdbcaa40_0` | ✗ (only ≥0.23.x) | True | `fastp` |
| sambamba | `0.8.1--hadffe2f_1` | ✗ (only ≥1.0.x) | True | `sambamba` |
| samblaster | `0.1.24--hc9558a2_3` | ✗ (only ≥0.1.25) | True | `samblaster` |
| samtools | `1.19--h50ea8bc_0` | ✗ (only `0.1.19`) | True | `samtools` |
| blast | `2.5.0--hc0b0e79_3` | ✗ | True | `blastn`, `blastp`, `blastx` |
| star | `2.7.11a--h0033a41_0` | ✓ | False | `STAR` |
| star-fusion | `1.0.0--pl5.22.0_0` | ✗ (only ≥1.9.1) | True | `STAR` (not `salmon`) |
| parabricks | n/a | ✗ | n/a | not in CVMFS — raises `ValueError` |
| seurat | n/a | ✗ | n/a | not in CVMFS — raises `ValueError` |

> **star-fusion 1.0.0 regression note:** `salmon` must NOT appear as an alias. It was incorrectly present when aliases were inherited from a newer build. The fix (always regenerate aliases from the specific SIF) is tested by `test_extract_aliases_star_fusion_1_0_0` (requires Singularity on PATH).

---

## Known issues

### `shpc` must be on PATH

All `shelley build` operations and CVMFS integration tests call `shpc` as a subprocess. `shpc` is installed at `/opt/shpc/bin/shpc` and is not on the default PATH:

```bash
module load shpc
```

In environments without the module system (e.g. GitHub Actions CI), `test_run_shpc_install_missing_cvmfs_path` will fail with `FileNotFoundError` rather than being skipped. This is a tracked known issue; the test is intentionally left as a documented failure until shpc path discovery is added to the builder.

### The shared settings file must exist before it is named

`shpc` exits with `"<path> does not exist."` if `--settings-file` points at a missing
file. shelley therefore omits the flag when `/apps/shpc/settings.yml` is absent, so
read-only commands still work on a machine that has never been built on. The build path
creates the file first, so a build always gets the shared layout.

### `/apps/local` must exist whenever it is in the registry list

shpc resolves its whole `registry` list eagerly, and a filesystem registry path that does
not exist raises `ValueError: No matching registry provider for /apps/local` on *every*
shpc command, including `config get`. shelley guards this twice: the directory is created
before the settings file is written, and the entry is dropped from the generated list if
the directory is somehow missing.

### A per-user `~/.singularity-hpc/settings.yml` is ignored

`--settings-file` is the highest-precedence layer in shpc's resolution chain, above
`~/.singularity-hpc/settings.yml` and above the central `/opt` defaults. This is
deliberate: it is what stops a per-user shpc config from redirecting a shared build back
into someone's home directory. A user running `shpc` directly still gets their own layout;
their modules simply are not shared.
