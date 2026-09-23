# How to build Lmod modules

## Build a single module

```bash
shelley build <tool>
```

shelley resolves the most recent available version from CVMFS, runs `shpc install`, and creates a symlink under `/apps/Modules/modulefiles/<tool>/`. After a successful build:

```bash
module load <tool>
```

## Where artifacts go

Builds are shared. Everything lands under `/apps`, owned by `root` and readable and
executable by every user on the machine:

```
/apps/shpc/modules/quay.io/biocontainers/<tool>/<version>/module.lua
/apps/shpc/wrappers/quay.io/biocontainers/<tool>/<version>/bin/*
/apps/Modules/modulefiles/<tool>/<version>.lua   -> symlink to the module.lua above
```

Nothing is written to your home directory. See
[docs/reference/data-sources.md](../reference/data-sources.md) for the full path table and
the permissions model.

## Other users on this machine

Any user can load a module that any admin built — no extra setup, no rebuild per user:

```bash
module load singularity <tool>/<version>
<tool> --version
```

`module load singularity` is needed because the generated module's wrapper scripts invoke
`singularity` from `PATH`.

Use this as the acceptance check after a build, as a different account:

```bash
sudo -u <someone-else> -H bash -lc 'cd ~ && module load singularity <tool>/<version> && <tool> --version'
```

### Specify a version

```bash
shelley build samtools/1.19
shelley build star/2.7.11a
```

Version strings follow the Bioconda convention — see `shelley find <tool> -v` for exact tags available on CVMFS.

### What happens when a tool is absent from the upstream shpc-registry

If the requested version has no entry in the [shpc-registry](https://github.com/singularityhub/shpc-registry), shelley creates a local `container.yaml` under `/apps/local/<uri>/` and retries the install. This typically adds a few extra minutes to the build. For the reasoning behind this design, see [docs/explanation/build-design.md](../explanation/build-design.md).

## Build multiple modules — file input

Pass a plain-text file of tool specs (one per line) to `shelley build`:

```bash
shelley build tools.txt
```

**File format** — each line is a tool spec in the same format accepted by the
single-build command. Blank lines and `#` comments are ignored:

```
# Core alignment tools
samtools/1.21
bwa
bowtie2/2.5.1  # pinned for reproducibility

fastqc
```

shelley detects that the argument is a file, parses it, and runs the batch
builder — showing a progress table and results summary for each tool.

## Requirements

- `shpc` must be on PATH (`module load shpc`)
- CVMFS must be mounted at `/cvmfs/singularity.galaxyproject.org/`
- Write access to `/apps/Modules/modulefiles/`, `/apps/shpc/` and `/apps/local/` — shelley
  will prompt for sudo if needed. The latter two are created on first build, so a fresh
  machine always needs sudo.

## Uninstalling a module

> To remove a module you no longer need, see [clean-modules.md](clean-modules.md).

## Troubleshooting

### A build still writes to `$HOME/shpc`

That is the signature of an **older shelley** doing the install. Because a build re-execs
under sudo, the process that actually installs is what matters — and shelley ≤0.2.0
resolved that process by looking up `shelley` on `PATH`, which can find a different
installation than the one you invoked. Running a checkout on a machine that also has a
system-wide `shelley` would silently hand the privileged half of the build to the
system copy.

Check which shelley is doing the work:

```bash
which -a shelley          # more than one? the system copy may be winning
shelley --version         # the one on PATH
uv run shelley --version  # the checkout
```

Current versions re-exec via `python -m shelley` from the running interpreter, so this
cannot happen. If you see it, the install performing the build predates that fix — upgrade
the system-wide copy with `shelley update`, or invoke the checkout explicitly:

```bash
uv run python -m shelley build <tool>
```

A second symptom of the same cause: shelley ≤0.2.0 ran `shpc config add registry
/apps/local`, which edits the root-owned central shpc settings at
`/opt/shpc/singularity-hpc/shpc/settings.yml`. Current versions never touch that file. If
`registry:` there mentions `/apps/local`, an old build wrote it; the line is safe to remove,
and worth removing, because a filesystem registry path that stops existing makes *every*
`shpc` command fail for every user on the machine.

### A module is listed by `module avail` but `module load` fails for other users

Modules built before shelley moved to a shared layout (v0.2.0 and earlier) were installed
into the *builder's* home directory, which no other user can read. The modulefile symlink
still exists, so `module avail` lists it, but loading it only works for the original
builder.

Find them:

```bash
find /apps/Modules/modulefiles -xtype l                 # dangling symlinks
find /apps/Modules/modulefiles -type l ! -readable      # unreadable targets
find /apps/Modules/modulefiles -type l -lname '/home/*' # pointing into a home directory
```

There is no migration — `module.lua` bakes in absolute paths, so the files cannot be moved
or chmodded into working order. Rebuild the affected tools with the current shelley.
`shelley find <tool> -v` will not mark these as installed, since it checks that the
symlink actually resolves.
