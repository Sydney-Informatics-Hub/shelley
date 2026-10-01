# How to remove Lmod modules

## Remove a single module

```bash
shelley clean <tool>:<version>
```

An explicit version is required — `shelley clean samtools` on its own does not pick
a "latest" version to remove, unlike `build`. Instead it lists what's currently
installed:

```bash
shelley clean samtools
```
```
❌ shelley clean requires an explicit version, e.g. samtools:<version>.

Suggestion:
Currently installed versions of 'samtools':
  • 1.21--h96c455f_1

Re-run with one of these, e.g.:
shelley clean samtools:1.21--h96c455f_1
```

A short version resolves the same way `build` resolves one, as long as it matches
exactly one installed build:

```bash
shelley clean samtools:1.21
```

By default, `clean` asks for confirmation before removing anything:

```
? Remove samtools/1.21--h96c455f_1? This deletes its module, wrappers, and container artifacts. (y/n)
```

Pass `-y` to skip the prompt — useful for scripting:

```bash
shelley clean samtools:1.21--h96c455f_1 -y
```

## What gets removed

```
/apps/shpc/modules/quay.io/biocontainers/<tool>/<version>/    -> removed (via shpc uninstall)
/apps/shpc/wrappers/quay.io/biocontainers/<tool>/<version>/   -> removed (via shpc uninstall)
/apps/shpc/containers/quay.io/biocontainers/<tool>/<version>/ -> removed (via shpc uninstall)
/apps/Modules/modulefiles/<tool>/<version>.lua                -> removed (shelley's own symlink)
```

If that was the last installed version of the tool, the now-empty
`/apps/Modules/modulefiles/<tool>/` directory is removed too.

`/apps/local/` (the local shpc registry) is deliberately left alone in most cases —
see [docs/explanation/clean-design.md](../explanation/clean-design.md) for why, and
for the one case where a local registry tag *is* safely pruned.

## Requirements

Same as `build`:

- `shpc` must be on PATH (`module load shpc`)
- Write access to `/apps/Modules/modulefiles/`, `/apps/shpc/` and `/apps/local/` —
  shelley will prompt for sudo if needed.

## Troubleshooting

### `shpc uninstall reported an issue`

```
╭──────────────────── shpc uninstall reported an issue ────────────────────╮
│ quay.io/biocontainers/samtools:1.21--h96c455f_1: ... — the Lmod          │
│ modulefile symlink was still cleaned up.                                 │
╰────────────────────────────────────────────────────────────────────────────╯
```

This means shpc's own bookkeeping had already lost track of the install (for
example, its module/wrapper/container directories were removed by hand, or a
previous `clean` was interrupted partway through). shelley's own state — the
modulefile symlink — is independent and still gets cleaned up regardless, so
`module avail` will correctly stop listing the tool. Safe to ignore.

### The tool still shows up under `module avail` after cleaning

Run `shelley find <tool> -v` — it checks that the modulefile symlink actually
resolves, not just that a `.lua` file with that name exists. If the tool is
genuinely gone, `module avail`'s cache may just need a moment; a fresh shell
session picks it up immediately.
