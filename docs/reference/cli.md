# CLI reference

Complete reference for all `shelley` commands.

```
shelley <command> [args]
```

---

## `find`

```bash
shelley find <tool_name> [-v | -vv]
```

| Argument | Type | Required | Description |
|---|---|---|---|
| `tool_name` | string | Yes | Tool to look up |
| `-v`, `--verbose` | flag | No | Show every available container version, paginated, instead of the recent-versions preview |
| `-vv` | flag | No | As `-v`, but list every individual build (one row per `--hash`) with its full CVMFS container path |

Verbosity stacks: `-vv` is equivalent to `-v -v`.

Looks up a tool by name. Case-insensitive; handles hyphen/underscore variants. Matches against the `id` and `name` fields in the RSEC corpus; falls back to fuzzy matching when no exact match is found.

**Returns:** Tool description, homepage, and EDAM operations; a table of container versions with buildable and install status; an install prompt. By default only the five most recent versions are shown. `-v` expands this to the full paginated version list, sorted newest-first (✓ = in the upstream shpc-registry, ✗ = requires local registry fallback). `-vv` further expands each version into its individual builds and adds a **Container Path** column with the full CVMFS image path.

---

## `search`

```bash
shelley search <query>
```

| Argument | Type | Required |
|---|---|---|
| `query` | string | Yes |

Keyword search across tool metadata. Matches on name, description, EDAM operations, and EDAM topics. Results returned in alphabetical order.

**Returns:** List of matching tools with descriptions and latest container versions.

> Relevance ranking is under development.

---

## `build`

```bash
shelley build <tool_spec>
```

| Argument | Type | Required | Format |
|---|---|---|---|
| `tool_spec` | string | Yes | `<tool>`, `<tool>/<version>`, `<tool>:<version>--<hash>`, or a path to a text file of tool specs |

When `tool_spec` is an existing file, each non-blank non-comment line is treated as a tool spec and built in sequence. See [Build multiple modules](../how-to/build-modules.md).

Installs an Lmod module for a tool from CVMFS via `shpc`. Creates a local registry entry if the version is absent from the upstream shpc-registry. Prompts for sudo if the module directory is not writable.

**Returns:** Build status output.

Requires `shpc` on PATH and CVMFS mounted.

---

## `clean`

```bash
shelley clean <tool>:<version> [-y]
```

| Argument | Type | Required | Format |
|---|---|---|---|
| `tool:version` | string | Yes | `<tool>:<version>` or `<tool>/<version>` — an explicit version is required; a full or short version string (e.g. `1.21` or `1.21--h96c455f_1`) is accepted as long as it resolves to exactly one installed build |
| `-y` | flag | No | Skip the confirmation prompt |

Uninstalls a specific installed tool version — the inverse of `build`. Removes the
`shpc`-managed module, wrappers and container artifacts, and the Lmod modulefile
symlink under `/apps/Modules/modulefiles/` (pruning the tool's directory too if that
was the last installed version). Prompts for confirmation before removing anything
unless `-y` is passed. Prompts for sudo if the shared directories are not writable.

Running with no version, or a version that isn't installed, lists every currently
installed version of that tool instead of uninstalling anything:

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

**Returns:** Clean status output, listing exactly what was removed.

See [docs/how-to/clean-modules.md](../how-to/clean-modules.md) for details, and
[docs/explanation/clean-design.md](../explanation/clean-design.md) for why the local
registry (`/apps/local/`) is deliberately left alone in most cases.

---

## `interactive`

```bash
shelley interactive
```

Starts a REPL session. Available commands inside the REPL:

```
find <tool_name> [-v]
search <description>
build <tool_spec>
clean <tool>:<version> [-y]
help
quit / exit
```
