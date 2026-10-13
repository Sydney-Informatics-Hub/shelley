# Clean design

Design choices for `shelley clean`. For how to remove a module, see [../how-to/clean-modules.md](../how-to/clean-modules.md).
For the paths involved, see [../reference/data-sources.md](../reference/data-sources.md).

## Clean is the inverse of a build

A `shelley build` should not leave a artefacts (e.g. `/apps/Modules/modulefiles/...`), so `clean` must not leave one either (see [build-design.md](build-design.md)). When cleaning an installed
version, shelley:

- runs `shpc uninstall` for the version's module;
- removes the version's wrapper and container directories if shpc leaves them behind
  (`shpc uninstall` can remove the module directory and keep the wrappers);
- removes shelley's Lmod modulefile link;
- if that was the tool's last installed version, removes all five of the tool's
  directories, including its local registry entry, and then any parent directories this
  leaves empty. Pruning stops at the shared layout itself (the build roots and shpc's
  bases), which every tool uses.

## A tool version must be supplied to clean

This is to protect against accidentally deleting an unintended version in production. 
There have been bugs where shelley gets the latest version wrong in tools with uncommon
ways of versioning (e.g. seqtk/r93 incorrectly assigned as latest when it should be vX.X.X)

**Rejected: make `clean` find and remove orphans, or add a separate cleanup tool.** That
treats the symptom instead of preventing it, and it would mean guessing which files
under `/apps` shelley wrote. This would have unintended side effects.

## Why clean resolves and confirms before `sudo`

`clean` is destructive, so the user's process does all the checking before the password
prompt:

- **An explicit version is required.** `shelley clean samtools` is an error that lists
  the installed tags, so a clean never removes a version the user did not name.
- **The version must match exactly one installed tag**, by full tag or by version, never
  by prefix. Otherwise `clean` lists the installed tags to choose from.
- **The user confirms** (default No) unless `-y` is given. Declining removes nothing.

Only then does `clean` re-run itself under `sudo`, passing the resolved tag as
`--resolved-tag tool:tag`, as a build does. The root subprocess re-checks the value (a tool
name and tag, never a path) and that the tag is still installed, before removing
anything.

## shelley creates versioned tool subdirectories

shpc reads one unversioned `container.yaml` per tool:
`/apps/local/quay.io/biocontainers/<tool>/container.yaml`. Its `tags` map lists every
version the entry knows about, and builds merge upstream's tags into it, so the entry
alone cannot say which tags shelley added.

So whenever a build creates a local entry for a version (the version is absent upstream,
or its aliases were curated with `-i`), it also writes a marker directory,
`/apps/local/quay.io/biocontainers/<tool>/<version>/aliases.yaml`. shpc ignores it,
because its filesystem registry looks only for files named `container.yaml`. The marker
records whether the version was upstream when it was built (`in_upstream`).

When other versions of the tool stay installed, `clean` uses the marker to decide what to
do with the entry:

| Marker | What `clean` does | Why |
|---|---|---|
| `in_upstream: false` | Removes the tag from `container.yaml`, and the marker | shelley added this tag, so removing it undoes the build that added it |
| `in_upstream: true` | Keeps the tag; removes only the marker | The tag is upstream's, and only its aliases were curated |
| No marker | Leaves the entry alone | shelley did not add this tag |

`test_clean_keeps_a_curated_tag_that_is_still_upstream` covers the second row.

When the last installed version goes, the whole entry goes with the tool's other
directories, so no marker bookkeeping is needed.

## Why marker directories also snapshot that version's aliases

`aliases` is one field shared by every tag in a `container.yaml`, and aliases differ a lot
between versions: `star-fusion 1.0.0` exposes `STAR`, while newer versions also bundle
`salmon`. Building a second locally authored version overwrites the field with that
version's aliases. The marker's `aliases.yaml` keeps each version's own list, so it is
not lost when a later build overwrites the shared field. shelley does not read it back
itself; it is the record to use when rebuilding or re-curating that version by hand.
