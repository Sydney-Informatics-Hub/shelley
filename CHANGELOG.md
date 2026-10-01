# Changelog

All notable changes to shelley are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Development tooling now uses [ruff](https://docs.astral.sh/ruff/) for linting and
  formatting, replacing the unused `black` and `flake8` in the `dev` extra. CI enforces
  `ruff check` and `ruff format --check` on every pull request. The codebase was
  reformatted once to match; see `docs/how-to/developer-setup.md`.

### Removed

- `print_about()` and `ShelleyStyle.create_about_panel()` from `shelley.utils`. They were
  unused and raised `NameError` if called.

## [0.3.0] - 2026-07-31

Multi-user module builds.

### Fixed

- **`shelley build` now produces modules every user on the machine can load.** shelley
  never told `shpc` where to install, so it inherited shpc's default of
  `module_base: $HOME/shpc/modules`. Because the build re-execs under `sudo -E`, which
  preserves `HOME`, root wrote the modules and wrapper scripts into the *invoking user's*
  home directory — unreadable and untraversable by anyone else, leaving the modulefile
  symlink under `/apps/Modules/modulefiles` pointing into an inaccessible tree.
  Artifacts now land under `/apps/shpc` and `/apps/local` as documented.
- Build artifacts are readable and executable by all users: directories `0755`, files
  `0644`, wrapper scripts `0755`, never group- or other-writable. Enforced by a
  `umask 022` set before anything forks, plus an explicit `chmod` pass over the subtrees
  each build touched. A restrictive umask in the invoking shell no longer leaks into
  `/apps`.
- `/apps/shpc` and `/apps/local` are created on first build. Previously nothing created
  them, and the one line referencing `/apps/shpc` targeted a path that did not exist.
- The sudo probe now covers all three build roots, not just
  `/apps/Modules/modulefiles`, so a first run on a fresh machine escalates correctly.
- `shelley find` no longer reports a module as installed when its modulefile symlink does
  not resolve to a readable file — which is the case for every module built by an earlier
  version into a home directory.
- **The sudo re-exec now re-runs the shelley that is actually running**, via
  `sys.executable -m shelley`, instead of resolving `shelley` on `PATH`. A PATH lookup can
  find a *different installation*: with a system-wide shelley present, running a checkout
  handed the privileged half of the build to the system copy, so the process that actually
  installs could be an older version. The symptom was baffling — the unprivileged half
  printed the new version's output while the build behaved like the old one, writing to
  `$HOME/shpc` anyway. Requires the new `shelley/__main__.py`.

### Changed

- Every `shpc` invocation is pinned to a shelley-managed settings file at
  `/apps/shpc/settings.yml` via `--settings-file`. This is the highest-precedence layer in
  shpc's resolution chain, so a per-user `~/.singularity-hpc/settings.yml` can no longer
  redirect a shared build. The file is partial — shpc still merges its own defaults
  underneath — and is regenerated only when stale.
- `/apps/local` is declared in that settings file rather than registered with
  `shpc config add registry`, which would have expanded the override file into a frozen
  snapshot of every site default.

### Added

- `SHELLEY_SHPC_BASE`, `SHELLEY_LOCAL_REGISTRY` and `SHELLEY_LMOD_MODULES_PATH` override
  the build roots (defaults `/apps/shpc`, `/apps/local`,
  `/apps/Modules/modulefiles`). They are forwarded explicitly across the sudo re-exec, so
  the elevated child agrees with the parent. Note that `SHELLEY_SHPC_BASE` is effectively
  write-once: a generated `module.lua` bakes in absolute paths, so changing it after
  modules exist invalidates them.

### Removed

- The `chown -R $SUDO_USER:$SUDO_USER` over the shpc base. Handing the tree to a single
  account is what made builds single-user, and it let one unprivileged user rewrite
  modules everyone else executes.

### Migration

Modules built with 0.2.0 or earlier live under the original builder's home directory and
cannot be salvaged — `module.lua` bakes in absolute wrapper and container paths, so they
cannot be moved or chmodded into working order. Find them with
`find /apps/Modules/modulefiles -type l -lname '/home/*'` and rebuild those tools.

## [0.2.0] - 2026-07-22

Pinned version for BioShell launch.

### Added

- `shelley find <tool> -v` — lists every individual container build (one row per
  `--hash`) with the date modified, install status and the full CVMFS container path.
- [EXPERIMENTAL] `shelley build <tool> -i` (`--interactive`) — opens an interactive session to
  curate the aliases a module exposes (deselect, rename, and add) for both
  upstream and local builds.
- Update check — on startup shelley compares its version against the `main`
  branch and prints upgrade instructions when a newer release is available. The
  result is cached for a day and fails silently on any network error.
- `shelley update` — upgrades shelley in place. It detects whether the install is
  system-wide (`/opt/uv/tools`) or per-user and runs the matching
  `uv tool upgrade shelley` for you.

### Changed

- Merged the `versions` command into `find`. Run `shelley find <tool> -v`
  (or `--verbose`) to see the full, paginated list of container versions.

### Removed

- `versions` command. Use `shelley find <tool> -v` instead.

### Fixed

- `shpc` and `singularity` are now loaded when required i.e. during `shelley build`.

## [0.1.0] - 2026-07-03

First tagged release.

### Added

- `find` — look up a bioinformatics tool by name and show its description and
  recent buildable container versions.
- `search` — find tools by function/description across the RSEC and toolfinder
  corpora.
- `versions` — list available container versions for a tool, newest first.
- `build` — generate Lmod modules for CVMFS-hosted containers, individually or
  in batch from a file.
- `interactive` — guided REPL for exploring and installing tools.
- `--version` flag on the CLI.
- Installation guide covering system-wide (`uv tool install` into `/opt`),
  per-user, and `uvx` (experimental) paths.

[Unreleased]: https://github.com/Sydney-Informatics-Hub/shelley/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/Sydney-Informatics-Hub/shelley/releases/tag/v0.3.0
[0.2.0]: https://github.com/Sydney-Informatics-Hub/shelley/releases/tag/v0.2.0
[0.1.0]: https://github.com/Sydney-Informatics-Hub/shelley/releases/tag/v0.1.0
