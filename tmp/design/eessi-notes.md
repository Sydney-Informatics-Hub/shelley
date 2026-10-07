# EESSI notes (design work, not docs)

Moved out of the glossary on 2026-10-07: EESSI integration is work in progress (hand-configured on the dev VM; BioShell PR to follow). Phase 4 will start from here. Evidence labels as in the glossary.

## Terms

Defined from EESSI's documentation and the mounted repository.

| Term | Definition | Evidence |
|---|---|---|
| **EESSI** | European Environment for Scientific Software Installations, distributed as the CVMFS repository `software.eessi.io` | `[runtime]` `/cvmfs/software.eessi.io/README.eessi` |
| **EESSI version** | A dated release of the whole stack under `versions/<YYYY.MM>/`. Present: `2023.06`, `2025.06`, `2026.06` | `[runtime]` `ls /cvmfs/software.eessi.io/versions` |
| **Initialisation** | Either source `versions/<v>/init/bash`, or `module load EESSI/<v>` from `/cvmfs/software.eessi.io/init/modules`. Either one sets `MODULEPATH` to that version's modules for the detected CPU target | `[runtime]` README.eessi; `init/modules/EESSI/2025.06.lua` |
| **Filesystem layer** | "The bottom layer … responsible for distributing the software stack" (CVMFS) | `[doc]` <https://www.eessi.io/docs/filesystem_layer/> |
| **Compatibility layer** | "The middle layer … ensures that our scientific software stack is compatible with different client operating systems", built with Gentoo Prefix. Lives at `versions/<v>/compat/linux/<arch>/` | `[doc]` <https://www.eessi.io/docs/compatibility_layer/>; `[runtime]` |
| **Software layer** | "The top layer … provides the actual scientific software installations", built with EasyBuild and exposed through Lmod | `[doc]` <https://www.eessi.io/docs/software_layer/> |
| **CPU target** (software subdirectory) | A CPU-optimised build tree `versions/<v>/software/linux/<arch>/<vendor>/<microarch>/`, named after archspec targets, with a `generic` fallback. Chosen at initialisation by `eessi_archdetect.sh`; can be forced with `EESSI_SOFTWARE_SUBDIR_OVERRIDE`. This VM (AMD EPYC Rome) resolves to `x86_64/amd/zen2` in all three versions | `[doc]` <https://www.eessi.io/docs/software_layer/cpu_targets/>; `[runtime]` `init/modules/EESSI/2025.06.lua:22`, archdetect output |
| **Accelerator target** | GPU-specific subtree (`accel/`), selected separately; `defaults/nvidia` is a symlink to `/dev/null` on this VM | `[runtime]` `init/modules/EESSI/2025.06.lua:104-119`; `ls defaults` |
| **Toolchain** | The compiler and library set a package is built with. `foss` = GCC, Open MPI, FlexiBLAS (OpenBLAS + LAPACK), ScaLAPACK, FFTW. `gfbf` is listed by EasyBuild but its contents were not stated on the page read. Documented versioning is `<year>{a,b}`; EESSI 2026.06 uses `2026.1`, which does not match that scheme | `[doc]` <https://docs.easybuild.io/common-toolchains/>; `[runtime]` |
| **Toolchain-suffixed module name** | `<Name>/<version>-<toolchain>-<toolchain version>[-<version suffix>]`, e.g. `R/4.5.2-gfbf-2025b`, `R-bundle-Bioconductor/3.22-foss-2025b-R-4.5.2`. The pattern is observed; EESSI's statement of it has not been read yet | `[runtime]` module listing |
| **Extension** | A package bundled inside a module and listed under "Included extensions" in its help, e.g. the R module includes `Rcpp`, `devtools`, `shiny` | `[runtime]` `R/4.5.2-gfbf-2025b.lua` |
| **Bundle** | A module whose purpose is a set of extensions, e.g. `R-bundle-CRAN`, `R-bundle-Bioconductor`. Contents not yet verified for DESeq2 or Seurat | `[runtime]` names only |
| **Module conflict** | EESSI's R modulefile declares `conflict("R")` | `[runtime]` `R/4.5.2-gfbf-2025b.lua` |
| **`host_injections`** | A top-level directory of the repository. Its purpose has not been read from EESSI docs yet | `[runtime]` `ls /cvmfs/software.eessi.io` |

R-related modules for `x86_64/amd/zen2` `[runtime]`:

| EESSI version | Module names | `R` | `R-bundle-CRAN` | `R-bundle-Bioconductor` | `RStudio-Server` |
|---|---|---|---|---|---|
| 2023.06 | 673 | 4.2.2, 4.3.2, 4.4.1 | 2023.12, 2024.06 | 3.16, 3.18 | 2024.09.0 (R 4.4.1) |
| 2025.06 | 642 | 4.4.2, 4.5.1, 4.5.2 | 2024.11, 2025.10, 2025.11 | 3.20, 3.22 | 2024.12.0 (R 4.4.2) |
| 2026.06 | 273 | 4.6.1 | 2026.07 | — | — |

---


## Findings to carry into Phase 4

- EESSI's `R` modulefile declares `conflict("R")`, so it collides with BioShell's `R/4.3.3` modulefile name `[runtime]`.
- The PoC criterion says `r/4.6.0`; EESSI has `R/4.6.1-gfbf-2026.1` (2026.06), and no `R-bundle-Bioconductor` in 2026.06 yet `[runtime]`.
- EESSI ships `RStudio-Server` modules (2023.06, 2025.06), relevant to requirements tension 2 `[runtime]`.
- `software.eessi.io` is not on `MODULEPATH` on this VM `[runtime]`.
