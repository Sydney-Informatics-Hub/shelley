# Getting started with shelley

This tutorial walks you through finding and installing a bioinformatics tool on a BioShell virtual machine for the first time.

## Prerequisites

- You have logged into a BioShell VM on Nectar
- `shelley` is already installed (it ships with BioShell)
- CVMFS is mounted at `/cvmfs/singularity.galaxyproject.org/`

If `shelley` is not yet installed (for example, on a VM not yet baked with it),
see [../how-to/install.md](../how-to/install.md).

Verify your setup:

```bash
shelley --help
```

You should see the list of available commands. If not, check with your system administrator.

## Step 1 — Find a tool by name

Start with a tool you already know you need. Use `find` when you know its name:

```bash
shelley find fastqc
```

shelley returns the tool's description the top most recent container versions. You also see the next few most recent versions and whether each can be built immediately.

Try a few variations — `find` handles case, hyphens, and underscores:

```bash
shelley find STAR
shelley find bwa-mem2
shelley find samtools
```

## Step 2 — Search by what you want to do

Use `search` when you know the task but not which tool to use:

```bash
shelley search "quality control"
shelley search "variant calling"
shelley search "de novo assembly"
```

Each result shows why it matched. Shorter technical phrases work better than full sentences.

> **Note:** Search is under active development. Results are currently alphabetical — relevance ranking is coming.

## Step 3 — Check available versions

`shelley find` shows only the five most recent versions by default. To see every
available container, add the `-v` (verbose) flag:

```bash
shelley find samtools -v
```

This returns every available container sorted newest-first, paginated, with buildable status for each version. Use this when you need to pin an exact version for reproducibility.

## Step 4 — Build a module

Once you know the tool and version you want, build its Lmod module:

```bash
shelley build samtools
```

This installs the most recent available version. To install a specific version:

```bash
shelley build samtools/1.19
```

After a successful build, load the module normally:

```bash
module load samtools
samtools --version
```

## Step 5 — Remove a module

When you no longer need a version, remove it with `clean`. It requires an explicit
version, and asks for confirmation before removing anything:

```bash
shelley clean samtools:1.19
```

## Next steps

- [docs/how-to/find-and-search.md](../how-to/find-and-search.md) — tips and all options for `find` and `search`
- [docs/how-to/build-modules.md](../how-to/build-modules.md) — building multiple modules at once
- [docs/how-to/clean-modules.md](../how-to/clean-modules.md) — removing modules
- [docs/reference/cli.md](../reference/cli.md) — complete command reference
