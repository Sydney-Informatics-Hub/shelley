# Clean design

Why `shelley clean` removes what it removes. The code is `ShpcExposer.remove`
(`shelley/galaxy/exposer.py`); `services.clean_resolved` and `client/discovery.py` resolve
the request as the user before any `sudo` prompt.

## Clean is the exact inverse of a build

A shelley build never leaves an orphan, so neither does `clean`. It removes one installed
version of a tool all-or-nothing:

- it runs `shpc uninstall` for the version's module, then removes anything shpc keeps
  behind (wrapper scripts and container directories for that version);
- it removes shelley's own Lmod modulefile link;
- if that was the tool's last installed version, it removes all of the tool's
  directories, including its local registry entry, and prunes empty parent directories.

All of this runs inside the same transaction a build uses. If `shpc uninstall` fails,
every change is undone and the error is reported: a version is never half-removed. The
test `test_build_then_clean_leaves_no_trace` checks that a build followed by a clean
leaves the shared roots byte-for-byte as they were.

`clean` only targets versions that are installed, meaning they have a modulefile link.
Files left without a link are a 0.4.0 bug artefact, not something `clean` looks for; the
next build of that tool tidies its local registry entry
([ADR 0006](decisions/0006-local-registry-holds-authored-entries-only.md)).

## Why per-version marker directories exist

shpc reads one unversioned `container.yaml` per tool:
`/apps/local/quay.io/biocontainers/<tool>/container.yaml`. Its `tags` map lists every
version the entry knows about, so on its own it cannot say which tags shelley added.

So whenever a build writes a local entry (the version is absent upstream, or its aliases
were curated with `-i`), it also writes a marker directory,
`/apps/local/quay.io/biocontainers/<tool>/<version>/aliases.yaml`. shpc ignores it: its
filesystem registry only looks for files named `container.yaml`. The marker records
whether the version was upstream when it was built (`in_upstream`).

When other versions of the tool stay installed, `clean` uses the marker to decide what to
do with the entry:

- **Marker says `in_upstream: false`:** shelley added this tag, so it is removed from
  `container.yaml` along with the marker.
- **Marker says `in_upstream: true`:** the version is still upstream and only its aliases
  were curated, so the tag stays and only the marker goes.
- **No marker:** the entry is left alone.

## Why marker directories also snapshot that version's aliases

`aliases` is one field shared by every tag in a `container.yaml`, and aliases differ a
lot between versions (`star-fusion` 1.0.0 only has `STAR`; newer builds also have
`salmon`). Building a second locally curated version overwrites the field with that
version's aliases. The marker's `aliases.yaml` keeps each version's own list, so it can
still be recovered after a later build has overwritten the shared field.
