# Architecture evaluation: scenarios

How the current design and the agreed target design
([target-state.md](../reference/architecture/target-state.md)) behave in seven concrete
scenarios agreed with Fred on 2026-10-07. The scenarios test the ranked quality
attributes in [architecture-drivers.md](architecture-drivers.md#25-quality-attributes-ranked).
A poor result for the target design would send the design back for another round.

**How to read the scores:**
- *Effort* is the cost to make the scenario behave well from where each design stands:
  S ≤ 1 unit of 1.5 h, M = 2–4 units, L > 4 units.
- *Blast radius* is one user, all users on a VM, or every image.
- *Rubric* deltas use the scores in
  [architecture-drivers §1.2](architecture-drivers.md#12-rubric-scores) and the to-be
  scores from the design rounds. Pairs are as-is → to-be, in the order cohesion /
  encapsulation / testability / least astonishment.

## Summary

| # | Scenario | As-is: what the user sees | To-be: what the user sees | Blast radius as-is → to-be | Effort as-is → to-be |
|---|---|---|---|---|---|
| S1 | Version that does not exist | sudo password, then an error | Error with the available versions, no password | one user → one user | S → none |
| S2 | GitHub unreachable during a build | "Success", but no tool command; a false "not in upstream" warning; persists after recovery | "Couldn't reach GitHub (…): the request timed out after 10 s. Try again in a few seconds." Nothing written | **all users on the VM → one user** | M → none |
| S3 | Galaxy mount absent or slow | `find` lists versions; `build` fails after the password | `build` fails before the password with "Galaxy CVMFS is not mounted"; `find` unchanged | one user → one user | S → none |
| S4 | Tag published after the last snapshot | `find` omits it; a bare `build` may install a different "latest" than `find` showed | `find` omits it (≤ 2 weeks); a bare `build` installs exactly what `find` showed; `build tool/<new tag>` works | one user → one user | M → none (accepted limit) |
| S5 | Build fails or is cancelled on a shared training VM | Module deleted (T5) or orphaned (T2) for every account, and baked into the image if snapshotted | Undone; a previous install is restored | **every image → one user** | L → none |
| S6 | Test suite without CVMFS, shpc or network; then CI with CVMFS mounted | 273 tests pass in about 5 s via about 190 patches; `cvmfs` tests skipped | Fakes per seam; the same catalogue contract tests run against a fixture and, in CI with CVMFS, against the live mount | dev only → dev only | M → S |
| S7a | Add EESSI as a second supplier | No seam: about 10 modules | Catalogue plus exposer pair: 2–3 modules | every image (BioShell) in both | L → M |
| S7b | Add `data.galaxyproject.org` reference data | No seam: about 6 modules | A catalogue only: 1–2 modules | one user → one user | M → S |

The target design improves or matches the current one in every scenario. The one limit
it accepts (S4: `find` lags the mount by up to two weeks) is recorded in
[ADR 0003](decisions/0003-single-source-of-versions.md). S7b exposes a vocabulary gap,
discussed below.

## Walk-throughs

### S1: a version that does not exist (`shelley build samtools/9.9`)

- **As-is:**
  1. The sudo re-exec runs first ([build.py:93-124](../../shelley/commands/build.py#L93-L124)).
  2. The root child bootstraps `/apps`, loads the Lmod build modules, and lists all 125k
     mount entries.
  3. `search_tool_version` raises "Version '9.9' not found … Available versions: …", with
     every short version, A to Z ([cvmfs_builder.py:831-838](../../shelley/builder/cvmfs_builder.py#L831-L838)).
- **To-be:** `services.resolve` runs as the user against the snapshot, and raises
  `TagNotFound` listing versions newest-first by the conda rule. No sudo prompt.
- **Classes involved:** `commands.build`, `CVMFSModuleBuilder` → `services`,
  `GalaxyCatalogue`, `Tag`, `client.render`.
- **Rubric:** `commands.build` LA 2 → `services` LA 3.

### S2: GitHub unreachable during a build

- **As-is** (reproduced, `[runtime]`): the upstream lookup returns `{}`, so the tag is
  treated as not upstream. Alias discovery fails silently. The build reports success
  with a warning saying the tag "is not in the upstream shpc-registry", which is false.
  The module has no tool command, and the local entry it wrote keeps breaking rebuilds
  after the network returns. Every user on the VM gets that module.
- **To-be:** `RegistryClient.fetch` raises `NetworkUnavailable` in `plan`, before any
  write ([ADR 0004](decisions/0004-fail-fast-when-network-unavailable.md)).
- **Classes involved:** `CVMFSModuleBuilder`, `guts_integration` → `ShpcExposer`,
  `RegistryClient`, `net`.
- **Rubric:** builder enc 1 → exposer enc 3; LA 2 → 3.

### S3: the Galaxy mount is absent or slow

- **As-is:**
  - `find` reads only the snapshot, so it shows versions as available.
  - `build` prompts for the password, then raises "CVMFS not available at …"
    ([cvmfs_builder.py:205-206](../../shelley/builder/cvmfs_builder.py#L205-L206)).
  - A slow mount stretches the 125k-entry listing; the client allows 5–10 s per request
    with 1 retry `[runtime]`.
- **To-be:** `GalaxyCatalogue.verify` stats one path before elevating, and raises
  `MountUnavailable`. A slow mount costs one `stat`, not a full listing.
- **Not yet observed:** exactly what a user sees when the Stratum 1 is unreachable (hang,
  then I/O error?). Integration question Q5 is deferred to a spike on a disposable VM.
- **Rubric:** builder test 2 → catalogue test 3 (the mount is a constructor argument).

### S4: a tag published after the last snapshot

- **As-is:** `find` cannot show it. A bare `build` lists the live mount and may choose it,
  or, by its own rule, a different tag from `find`'s top row (T1).
- **To-be:**
  - `find` cannot show it for up to two weeks (fortnightly refresh).
  - A bare `build` installs the snapshot's latest, the same as `find`.
  - `build tool/<new tag>` misses in the snapshot, falls back to one live listing, and
    builds it ([ADR 0003](decisions/0003-single-source-of-versions.md)).
- **Rubric:** `commands.find` LA 1 → 3.

### S5: a failed or cancelled build on a shared training VM

Training VMs have several `userNN` accounts and are prepared, then snapshotted (BioShell
user guide, per the requirements context). Whether trainees have sudo is unverified;
trainers building on `tdevNN` before the snapshot certainly do.

- **As-is** (`[runtime]`, spike A): cancelling `-i` on an installed tag deletes the module
  and wrappers and leaves a dangling link. A failure after `shpc install` leaves orphans.
  Either one is captured into the image and copied to every VM launched from it.
- **To-be:** `plan` runs before any write; `apply` runs in `BuildTransaction`, and a
  rebuild moves the old install aside first
  ([ADR 0005](decisions/0005-plan-then-apply-with-compensating-transaction.md)).
- **Classes involved:** `CVMFSModuleBuilder` → `ShpcExposer`, `BuildTransaction`.
- **Rubric:** builder coh 1 → exposer coh 2; LA 2 → 3.

### S6: the test suite without CVMFS, shpc or network; then CI with CVMFS

Fred has opened an issue to mount CVMFS in GitHub Actions.

- **As-is:**
  - 273 tests pass offline in about 5 s, isolating side effects with about 190
    `monkeypatch`/`patch` sites aimed at module attributes.
  - The 25 `cvmfs` tests skip without the mount.
  - With CVMFS in CI, those tests also need shpc and Singularity; one is a documented
    failure without shpc on `PATH` ([data-sources.md](../reference/data-sources.md#shpc-must-be-on-path)).
- **To-be:**
  - Services are tested with `FakeShpc`, `FakeRegistry` and a fixture-backed
    `GalaxyCatalogue`.
  - One catalogue contract suite runs against a small fixture tree offline, and, with
    CVMFS in CI, against the live mount.
  - The `shpc` and `network` markers stay separate from `cvmfs`.
- **Effort:** M as-is (patches are coupled to call order) → S to-be (the seams exist).

### S7a: EESSI as a second supplier (work in progress)

- **As-is:** EESSI shares nothing with the shpc build path. It would need branches in
  `find`, `build`, `clean`, `search` and the cache module, and a sibling of the builder.
- **To-be:**
  - an `EESSICatalogue` (walks `modules/all/<Name>/` for the detected CPU target);
  - an exposer that makes the module tree visible to Lmod, with no transaction;
  - a name-to-pair lookup in `services`.

  At that point a `typing.Protocol` per role is extracted
  ([ADR 0001](decisions/0001-split-discovery-from-exposure.md)).
- **Blast radius:** every image in both designs, because exposure is likely a `MODULEPATH`
  change made in BioShell, and the module name clash `conflict("R")` vs BioShell's
  `R/4.3.3` affects every user. This is integration question E-Q1/E-Q2.

### S7b: `data.galaxyproject.org` reference data

What the mount provides (`[runtime]`, 2026-10-07):
- `byhand/`: 258 genome and database directories;
- `managed/`: 18 kinds of pre-built index and database (BWA-MEM, Bowtie2, HISAT2, STAR,
  Salmon, Kraken2, GTDB-Tk, …);
- `managed/location/`: 24 Galaxy `.loc` manifests, tab-separated (key, build, display
  name, path), e.g. 47 BWA-MEM indices; `builds.txt` names each genome build.

There is no build step, and the manifests are a ready-made catalogue, so no snapshot is
needed.

- **As-is:** the mount is configured by the image but not read by shelley. Adding "find
  the hg38 BWA index" would mean a new command or a branch in `find`, alongside the
  Galaxy-specific cache module.
- **To-be:** a `GalaxyDataCatalogue` that parses the `.loc` files, plus a `services`
  function and a renderer. There is **no exposer**: the user needs a path. A Lmod module
  exporting variables like `$BWA_INDEX` would be an option for later.
- **What it shows:**
  1. The design's "supplier = catalogue *plus* exposer" pairing needs relaxing: a
     catalogue-only supplier must be allowed. That is a one-line change to
     [target-state §9](../reference/architecture/target-state.md#9-adding-a-second-supplier-to-be),
     not a redesign.
  2. The agreed glossary meaning of *supplier* ("delivers runnable software") does not
     cover reference data. The vocabulary needs a decision.

## Conclusion

The target design holds up across all seven scenarios. Its largest gains are where the
blast radius was widest: S2 (all users on a VM) and S5 (every image) both drop to one
user. Both follow-ups from S7b are settled (Fred, 2026-10-07): *supplier* now covers reference
data, and catalogue-only suppliers are allowed ([glossary](../reference/architecture/glossary.md#agreed-vocabulary),
[target-state §9](../reference/architecture/target-state.md#9-adding-a-second-supplier-to-be)).
`data.galaxyproject.org` is a latent supplier (driver E2), like EESSI.
