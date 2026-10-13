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
/apps/shpc/modules/quay.io/biocontainers/<tool>/<version>/    -> removed (shpc uninstall)
/apps/shpc/wrappers/quay.io/biocontainers/<tool>/<version>/   -> removed
/apps/shpc/containers/quay.io/biocontainers/<tool>/<version>/ -> removed
/apps/Modules/modulefiles/<tool>/<version>.lua                -> removed (shelley's link)
```

shelley removes the wrapper and container directories itself if shpc leaves them behind,
so nothing is left over for that version.

If that was the last installed version of the tool, all of the tool's directories go too,
including its local registry entry under `/apps/local/`. While other versions stay
installed, the local registry entry is only changed for a version shelley added there; see
[docs/explanation/clean-design.md](../explanation/clean-design.md).

Removal is all-or-nothing: if any step fails, everything is put back as it was and the
error is shown.

## Requirements

Same as `build`:

- Write access to `/apps/Modules/modulefiles/`, `/apps/shpc/` and `/apps/local/`.
  shelley asks for `sudo` if needed, after it has checked that the version is installed.
- On BioShell, shelley loads the `shpc` module itself.

## Troubleshooting

### `Clean Failed` … `shpc uninstall failed for …`

shpc could not remove the module. As the panel says, nothing was removed: shelley put
everything back, so the version is still installed and still loads. The message includes
shpc's own output; fix the cause and run the same `shelley clean` again.

### The tool still shows up under `module avail` after cleaning

Run `shelley find <tool> -v` — it checks that the modulefile symlink actually
resolves, not just that a `.lua` file with that name exists. If the tool is
genuinely gone, `module avail`'s cache may just need a moment; a fresh shell
session picks it up immediately.
