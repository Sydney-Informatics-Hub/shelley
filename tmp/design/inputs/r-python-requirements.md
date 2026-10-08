# BioShell R & Python environment management — requirements (draft v0.3)

Captured 2026-10-07 from a requirements Q&A with Fred. Context: `claude/bioshell-context-r-python.md`.

## Iteration 1 scope (v0.2)
- **In:** R only, with multiple versions through Lmod, RStudio Server, the terminal and Nextflow. Supplier: EESSI; its R-bundle-CRAN / R-bundle-Bioconductor modules are the only stacks.
- **Deferred (v0.3, 2026-10-07):** SIH-curated stacks (F3/F8) and trainer-built stacks (F6).
- **Deferred to a later iteration:** Posit Package Manager, Python version and stack management, and Jupyter (Python and R kernels). Their requirements below are kept for later and marked *(deferred)*.
- **What this changes:** R packages come from EESSI's R-bundle-CRAN / R-bundle-Bioconductor modules, or are compiled from source against EESSI R. Source builds are slow, but the six-monthly release cadence can absorb that. Tension 1 (EESSI vs PPM binaries) is parked.

## Problem
- BioShell ships one apt R (4.3.3, so Bioconductor 3.18 at best) and the system Python. The `R` module is only a label. There is no way to change versions.
- Galaxy Singularity CVMFS works well for CLI tools, but it does not give users one R session where `library(DESeq2); library(Seurat)` works in RStudio.
- Headline need: **`module load r/4.6.0` → RStudio → `library(DESeq2); library(Seurat)` works.**

## Users and modes
- Consumers: interactive analysis (RStudio, Jupyter, terminal), Nextflow pipelines, training workshops. Batch HPC is out of scope.
- Deployment: both single-user research VMs (with sudo) and multi-account training images (`userNN` from `/etc/skel`, then snapshotted).
- Scope: BioShell only (Nectar and Nirin). Portability to other HPC or laptops is not required.

## Functional requirements
| # | Requirement | Notes |
|---|---|---|
| F1 | Many R versions selectable via Lmod (`module load r/<ver>`) | "Whatever upstream has" |
| F2 | *(deferred)* Python versions selectable; PyPI/uv ecosystem | No conda requirement |
| F3 | *(deferred)* SIH-published curated stacks (shared, versioned) | Stated as "curated only", but see F5 and F6 |
| F4 | A selected stack works in RStudio Server, the terminal and Nextflow | Jupyter (Python and R kernels) *deferred*; Jupyter is currently classic Notebook with no IRkernel |
| F5 | Off-menu packages: research VMs can install freely; training is locked | Mode-dependent |
| F6 | *(deferred)* Trainers compose workshop stacks via shelley on a dev VM before the snapshot | Future: SIH curated domain stacks (single-cell, spatial omics) |
| F7 | shelley: package discovery (`search DESeq2` → stacks), stack activation (module + RStudio + kernel), admin build tooling | |
| F8 | *(deferred)* Published stacks are immutable and kept indefinitely | |

## Non-functional and constraints
- Turnaround for new stacks/packages: the **next image release** (six-monthly) is acceptable. This removes the 5-minute constraint.
- Storage: CVMFS (lazy-loaded) and/or a container per stack. The root disk has about 16 GB free, so stacks are not baked into the image.
- CVMFS publishing: no SIH/BioCommons Stratum 0 yet, but one is possible (unused `bcws.test.aarnet.edu.au` var).
- Network: egress available (Nectar-style; Nirin through proxies). Air-gapped operation is **not** required.
- Supply candidates: **EESSI as a direct supplier** (iteration 1); public Posit Package Manager (free) *(deferred)*. No licence budget is assumed.
- GPU stacks: design for them, build in a later phase.
- Ownership: a small SIH team.
- No-go: Galaxy CVMFS CLI-tool delivery must stay as-is.

## First deliverable
- Design plus a PoC. PoC success criterion: `module load r/4.6.0` in RStudio Server, then `library(DESeq2); library(Seurat)` works.

## Tensions to resolve in the design
1. *(Parked with PPM deferral)* **EESSI R vs public PPM binaries.** PPM Linux binaries are built for the distro (Ubuntu 24.04) system libraries. EESSI's R runs on its own compatibility layer and toolchain. Combining them likely means compiling from source (slow for Seurat/DESeq2 dependency trees) or using EESSI's fixed R-bundle-Bioconductor modules. Also check how quickly EESSI ships new R versions (is R 4.6 available?). The PoC should test both paths: EESSI R, and Posit/rig-style Ubuntu R builds with PPM binaries.
2. **Module load ≠ RStudio session.** Open-source RStudio Server launches `rsession` itself, not from the user's shell, and has no per-user R version picker (that is a Workbench feature). Options include a wrapper set as `rsession-path` that reads the user's selected module, restarting rserver with `rsession-which-r` (feasible with sudo, not on training accounts), or running RStudio inside a per-stack container.
3. **"Curated only" vs trainer-built and free research installs.** In practice this is a layered model: SIH base stacks, then trainer/user layers.
4. **Indefinite retention × many versions.** Unbounded growth. Store built libraries on CVMFS rather than re-resolving from PPM snapshots later, and define naming and immutability rules.
5. **The Stratum 0 is on the critical path** for the CVMFS storage choice. The PoC can use local `/apps` first.
6. **Release cadence mismatch.** Image bumps are in Jan/Jul; Bioconductor releases are in Apr/Oct. Consider shifting image bumps about 1 month after each Bioconductor release.

7. **Without PPM, how fresh can EESSI's R be?** Does EESSI ship R 4.5/4.6, and do its R-bundle-Bioconductor modules include Seurat and DESeq2 at usable versions? If not, a source build against EESSI R is the fallback, and its build time and failure rate are what the PoC needs to measure.

## Open questions (not yet answered)
- Where do research-mode personal libraries live (`/mnt/data` vs home), and are they keyed per R version or per stack?
- Do trainee accounts have sudo? Is a training VM single- or multi-user?
- How do trainer-built stacks get into the snapshot (local `/apps`), and are they ever promoted to CVMFS?
- PoC timebox and target date; how this interacts with the shelley capacity of about 1.5 days/week.
- Module naming: `r/4.6.0` vs the existing `R/4.3.3`. Stack naming, e.g. `r-stack/scrna-2026.10`?


Solution design: Claude Doc "BioShell R environments — solution design" (https://claude.ai/code/artifact/7bd6d25a-2193-499a-8dae-600eff014f15).