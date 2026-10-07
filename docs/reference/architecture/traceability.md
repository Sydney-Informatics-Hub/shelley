# Traceability: drivers × modules

Which current module serves each architecture driver, and where each defect lives.
Driver IDs and their meanings are defined in
[architecture-drivers.md](../../explanation/architecture-drivers.md#part-2-drivers-quality-attributes-and-priorities).
Module responsibilities are in [current-state.md §6](current-state.md#6-responsibility-table-as-is).

- **Versions:** [as-is](#matrix-as-is) (shelley `dev` @ `bb70383`) and [to-be](#to-be)
  (the agreed design in [target-state.md](target-state.md)), both 2026-10-07.
- **Legend:** ● serves the driver · ○ serves part of it · ✖ the defect or gap is located
  here · blank: not involved.

## Module key

| Key | Module / class |
|---|---|
| CLI | `client.cli` + `commands.interactive` (dispatch) |
| BLD | `commands.build` |
| CLN | `commands.clean` |
| FND | `commands.find` |
| SRC | `commands.search` |
| UPD | `commands.update` + `utils.update_check` |
| CMB | `CVMFSModuleBuilder` + registry functions (`builder/cvmfs_builder.py`) |
| GUT | `builder.guts_integration` |
| SET | `builder.shpc_settings` |
| PRM | `utils.perms` |
| GLB | `utils.globals` |
| LMD | `utils.modules` (Lmod loader) |
| GCH | `utils.cache` (Galaxy container cache) |
| MDS | `MetadataSource`, `RsecSource`, `ToolfinderSource` |
| STY | `utils.style` + `utils.render` |
| BAT | `utils.batch` |
| SCR | `scripts.*` (data refresh, out of scope) |

## Matrix (as-is)

| Driver | CLI | BLD | CLN | FND | SRC | UPD | CMB | GUT | SET | PRM | GLB | LMD | GCH | MDS | STY | BAT | SCR |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C1 search | ● | | | | ● | | | | | | | | ● | ● | ● | | ○ |
| C2 find | ● | | | ● | | | | | | | ● | | ● | ● | ● | | ○ |
| C3 build | ● | ● | | | | | ● | ○ | ● | ● | ● | ● | | | ● | | |
| C4 build -i | ● | ○ | | | | | ● | ● | | | | | | | | | |
| C5 batch | ● | ● | | | | | | | | | | | | | ● | ● | |
| C6 clean | ● | ○ | ● | ○ | | | ● | | | ● | ● | ● | | | ● | | |
| C7 REPL | ● | | | | | | | | | | | | | | ● | | |
| C8 update | ● | | | | | ● | | | | | | | | | ○ | | |
| C9 shared layout | | ● | ● | | | | ● | | ● | ● | ● | | | | | | |
| C10 read-only without Lmod/shpc/root | | | | ● | ● | | ○ | | | | | ● | ● | ● | | | |
| T1 wrong-version match | | | | ✖ | | | ✖ | | | | | | ✖ | | | | |
| T2 orphaned artefacts | | | ✖ | | | | ✖ | | | | | | | | | | |
| T3 test teardown (deprioritised) | | | | | | | | | | | | | | | | | |
| T4 prefix-glob installed flag (deprioritised) | | | | ✖ | | | | | | | | | | | | | |
| T5 cancelled `-i` destroys module (deprioritised) | | | | | | | ✖ | ✖ | | | | | | | | | |
| T6 offline misreport, persistent bad entry | | | | | | | ✖ | ✖ | | | | | | | | | |
| N1 report "network down" | | | | | | ○ | ✖ | ✖ | | | | | | | | | |
| N2 find and build agree | | | | ✖ | | | ✖ | | | | | | ✖ | | | | |
| K5 resource limits | | | | | | | ✖ | | | | | | ✖ | | | | |
| F1, F4, F5, PoC (R via EESSI) | | | | | | | | | | | | | | | | | |
| F7 package discovery | | | | | ○ | | | | | | | | | ○ | | | |
| E1 expose a second supplier | | | | | | | | | | | | | | | | | |

Notes on individual cells:

- **C10 / CMB ○:** the constructor is kept side-effect-free so `find` can construct it (`[code]` [cvmfs_builder.py:144-148](../../../shelley/builder/cvmfs_builder.py#L144-L148)), but `find` no longer uses it.
- **C6 / FND ○:** `clean` uses `find.list_installed_versions` (`[code]` [clean.py:10](../../../shelley/commands/clean.py#L10)).
- **N1 / UPD ○:** the update check already treats network failure as "no answer" and times out after 2 s (`[code]` [update_check.py:44](../../../shelley/utils/update_check.py#L44)); it does not report it.
- **F7 / SRC, MDS ○:** keyword search exists, but RSEC holds no Bioconductor records and no notion of a stack (`[doc]` [search-design.md:33](../../explanation/search-design.md)).

## Drivers no module serves

| Driver | Gap |
|---|---|
| T3 | Not located; deprioritised (dev machines only). The test layer has no teardown for modules a test creates outside the redirected roots |
| N1 | No module distinguishes "unreachable" from "absent"; both become `{}` or `[]` |
| N2 | No single catalogue: `find` reads the snapshot, `build` lists the mount |
| F1, F4, F5, PoC, E1 | No supplier other than Galaxy exists |
| F7 (stacks) | No stack concept in any module |

## Modules or members no driver justifies

| Item | Why no driver applies | Evidence |
|---|---|---|
| `ToolfinderSource` at runtime | Only `scripts/assess_*.py` use it | `[code]` grep |
| `list_cvmfs_versions` → `list_versions_with_paths` | No caller |
| `get_registry_tags` | No runtime caller; tests only | `[code]` [build.py:206](../../../shelley/commands/build.py#L206) |
| `ShelleyStyle.create_versions_table`, `create_tools_table`, `create_progress_bar`, `create_status_summary` | No caller | `[code]` grep |
| `/apps/shpc/views` | Kept only so a direct `shpc view` call works; no shelley driver | `[code]` [globals.py:81-83](../../../shelley/utils/globals.py#L81-L83) |
| pytest marker `network` | Declared, used by no test | `[code]` [conftest.py:11-14](../../../tests/conftest.py#L11-L14) |

## To-be

The agreed design ([target-state.md](target-state.md)), 2026-10-07.

| Key | Module |
|---|---|
| CMD | `client.commands` + `client.render` |
| SVC | `services` |
| PRV | `privilege` |
| CAT | `galaxy.catalogue.GalaxyCatalogue` |
| EXP | `galaxy.exposer.ShpcExposer` |
| REG | `galaxy.registry` (`RegistryClient`, `LocalRegistry`) |
| TAG | `tags` (+ vendored `VersionOrder`) |
| TX | `transaction.BuildTransaction` |
| TLS | `tools.shpc`, `tools.lmod`, `tools.net` |
| MDS | `search.*` |
| UPD | `commands.update` + `utils.update_check` |
| LAY | `utils.globals` + `utils.perms` |

| Driver | CMD | SVC | PRV | CAT | EXP | REG | TAG | TX | TLS | MDS | UPD | LAY |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C1 search | ● | ● | | ● | | | | | | ● | | |
| C2 find | ● | ● | | ● | | | ● | | | ● | | ● |
| C3 build | ● | ● | ● | ● | ● | ● | ● | ● | ● | | | ● |
| C4 build -i | ● | | | | ● | | | | | | | |
| C5 batch | ● | ● | ● | | | | | | | | | |
| C6 clean | ● | ● | ● | ● | ● | ● | ● | ● | ● | | | ● |
| C7 REPL | ● | | | | | | | | | | | |
| C8 update | ● | | | | | | | | ○ | | ● | |
| C9 shared layout | | | ● | | ● | | | | ● | | | ● |
| C10 read-only without root | | ● | | ● | | | ● | | | ● | | |
| T1 wrong version | | | | ● | | | ● | | | | | |
| T2 orphans | | | | | ● | | | ● | | | | |
| T3 test teardown (deprioritised) | | | | | | | | ○ | | | | |
| T4 prefix glob (deprioritised) | | | | ● | | | ● | | | | | |
| T5 cancelled -i (deprioritised) | | | | | ● | | | ● | | | | |
| T6 offline | | | | | ● | ● | | | ● | | | |
| N1 network down | ● | | | | ● | ● | | | ● | | | |
| N2 find = build | | ● | | ● | | | ● | | | | | |
| K5 resource limits | | | | ● | ● | | | | | | | |
| F7 discovery | | ○ | | | | | | | | ○ | | |
| F1, F4, F5, PoC, E1 | | ○ | | | | | | | | | | |

- **Drivers no module serves:** none in scope. F1, F4, F5, the PoC and E1 depend on the
  EESSI supplier (work in progress); `services` is where its catalogue/exposer pair
  plugs in.
- **Modules no driver justifies:** none.
