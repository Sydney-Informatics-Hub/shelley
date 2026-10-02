# How to maintain data artifacts

Steps for keeping the bundled data files up to date. For the rationale behind what each artifact contains and why, see [docs/reference/data-sources.md](../reference/data-sources.md) and [docs/explanation/search-design.md](../explanation/search-design.md).

## Automated monthly refresh

[`.github/workflows/refresh-data.yml`](../../.github/workflows/refresh-data.yml)
regenerates `toolfinder_meta.yaml`, `rsec_meta.json.gz` and
`galaxy_singularity_cache.json.gz` on the 1st of each month, and opens a PR into
`dev` if any of them changed. `guts_db/` is not included; refresh it
[manually](#refresh-a-guts-base-image-manifest).

The workflow checks out `dev` and runs the same commands as the manual steps below.
It mounts CVMFS on the runner with
[`cvmfs-contrib/github-action-cvmfs`](https://github.com/cvmfs-contrib/github-action-cvmfs)
for the Galaxy scan.

To run it outside the schedule, open **Actions → Refresh data → Run workflow**.

### What counts as a change

The builders stamp each artifact with `generated_at`, and gzip records its own
timestamp, so a regenerated file always differs byte-for-byte.
[`.github/scripts/compare_data.py`](../../.github/scripts/compare_data.py) compares
*content* instead: it drops `generated_at`, sorts Galaxy entries by name, and
restores any file whose content is unchanged. If nothing changed, no PR is opened.

To run the comparison locally after regenerating by hand:

```bash
uv run python .github/scripts/compare_data.py shelley/data/rsec_meta.json.gz
```

### Reviewing a refresh PR

1. **Trigger CI.** CI does not run automatically on PRs opened by a workflow, because
   GitHub does not trigger workflows from its built-in token. Close and reopen the PR
   to start it.
2. **Check the entry counts** in the PR description. A steady increase is normal.
   A large drop usually means an upstream problem, such as a partial CVMFS listing or
   a restructured RSEC repo, rather than tools being removed. Do not merge it until
   you have checked upstream.
3. **Spot-check the CLI** on the PR branch, for example `uv run shelley find fastqc`
   and `uv run shelley search "read mapping"`.
4. Merge into `dev`.

### If a source fails

Each source is refreshed independently, so one failing upstream does not block the
others. The PR, if any, covers only the sources that succeeded, and its description
lists the ones that failed. The run is marked as failed, so GitHub notifies you.

A failed source leaves its committed file untouched: builders write to a temporary
path and only replace the artifact on success. Re-run the workflow, or regenerate
that file manually with the steps below.

### Setup requirements

- The workflow must be on `main`, because scheduled workflows run from the default
  branch. It still refreshes data on `dev`.
- **Settings → Actions → General → Workflow permissions** must have *Allow GitHub
  Actions to create and approve pull requests* enabled, or the PR step fails.

## Regenerate `rsec_meta.json.gz`

The RSEC search corpus is built from the [research-software-ecosystem/content](https://github.com/research-software-ecosystem/content) repository. Regenerate after upstream updates:

```bash
# From the repo root:
uv run shelley-build-rsec
```

This sparse-clones `data/` from the RSEC repo (~90 s), parses every `*.biotools.json` file, and writes `shelley/data/rsec_meta.json.gz`.

```bash
# Force tarball download instead of sparse clone:
uv run shelley-build-rsec --method tarball

# Check field-coverage statistics without writing anything:
uv run shelley-build-rsec --assess

# Fetch a specific branch/tag:
uv run shelley-build-rsec --ref main
```

After regenerating:

```bash
git add shelley/data/rsec_meta.json.gz
git commit -m "DEV: Regenerate rsec_meta.json.gz from RSEC content"
```

## Run field-coverage assessment

Check how well-populated each metadata field is across both corpora (reads committed artifacts, no network required):

```bash
uv run python shelley/scripts/assess_coverage.py           # both sources
uv run python shelley/scripts/assess_coverage.py rsec
uv run python shelley/scripts/assess_coverage.py toolfinder
```

## Check per-tool field coverage for regression tools

Cross-reference the 15-tool regression matrix against both corpora:

```bash
uv run python shelley/scripts/assess_regression_tools.py
```

## Refresh a guts base-image manifest

The `shelley/data/guts_db/` directory holds Singularity manifests used to subtract conda infrastructure from tool containers. Refresh when a base image's conda version makes a major jump.

Requires Singularity on PATH e.g. `module load singularity`:

```bash
# anaconda/miniconda
uv run guts manifest -c singularity -i fs -i paths \
    -o shelley/data/guts_db/docker.io/anaconda/miniconda/latest.json \
    anaconda/miniconda

# continuumio/miniconda3
uv run guts manifest -c singularity -i fs -i paths \
    -o shelley/data/guts_db/docker.io/continuumio/miniconda3/latest.json \
    continuumio/miniconda3
```

Move new manifests under the correct namespace path (`docker.io/<org>/<image>/<tag>.json`) then commit.

## Regenerate `galaxy_singularity_cache.json.gz`

The CVMFS container index is built by scanning the Galaxy Singularity CVMFS mount directly. Run on a system where CVMFS is mounted:

```bash
uv run shelley-build-galaxy
```

This scans `/cvmfs/singularity.galaxyproject.org/all` (about 30 s on BioShell) and
writes `shelley/data/galaxy_singularity_cache.json.gz`. Use `--cvmfs-root` to scan
a different directory, or `--out` to write elsewhere.

After regenerating:

```bash
git add shelley/data/galaxy_singularity_cache.json.gz
git commit -m "DEV: Regenerate galaxy_singularity_cache.json.gz"
```

## Refresh `toolfinder_meta.yaml`

> **Note:** `toolfinder_meta.yaml` is no longer used in shelley
but retained for record keeping purposes

`toolfinder_meta.yaml` is an unmodified copy of `data/data.yaml` from
[AustralianBioCommons/finder-service-metadata](https://github.com/AustralianBioCommons/finder-service-metadata):

```bash
curl -fsSL -o shelley/data/toolfinder_meta.yaml \
    https://raw.githubusercontent.com/AustralianBioCommons/finder-service-metadata/main/data/data.yaml
```

Then commit the updated file.
