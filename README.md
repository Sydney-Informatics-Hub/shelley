# Shelley

[![CI](https://github.com/Sydney-Informatics-Hub/shelley/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Sydney-Informatics-Hub/shelley/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Sydney-Informatics-Hub/shelley)](https://github.com/Sydney-Informatics-Hub/shelley/releases/latest)
[![Python](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2FSydney-Informatics-Hub%2Fshelley%2Fmain%2Fpyproject.toml)](pyproject.toml)
[![License](https://img.shields.io/github/license/Sydney-Informatics-Hub/shelley)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23093273.svg)](https://doi.org/10.5281/zenodo.23093273)

**A bioinformatics tool finder and module builder for CVMFS-hosted containers on [BioShell](https://github.com/Sydney-Informatics-Hub/bioimage)**

<img width="1055" height="386" alt="image" src="https://github.com/user-attachments/assets/c57d2ad1-fe5e-42d2-a09d-10aea743f531" />

Shelley helps researchers using [BioShell](https://github.com/AustralianBioCommons/BioShell) virtual machine images on Nectar research cloud platforms discover, query, and deploy bioinformatics software from CVMFS (CernVM File System) repositories. It provides both interactive and programmatic interfaces for finding tools, building Lmod modules, and managing containerised workflows.

## Features

- **Tool Discovery**: Find bioinformatics tools by name or search by description
- **Container Management**: Query available container versions from CVMFS
- **Module Building**: Automatically generate Lmod modules for tools, individually or in batch
- **Module Cleanup**: Cleanly uninstall a specific tool version
- **Interactive CLI**: Guided REPL for exploring and installing tools

## Quick Start

### Installation

`shelley` ships with [BioShell](https://github.com/AustralianBioCommons/BioShell).

To install or update shelley manually:

| Goal | Guide |
|---|---|
| Install/update on a workstation, VM, or BioShell image | [docs/how-to/install.md](docs/how-to/install.md) |
| Developer environment | [docs/how-to/developer-setup.md](docs/how-to/developer-setup.md) |

### Basic Usage

```bash
# Find a specific tool
shelley find fastqc

# Search by function (in development)
shelley search "quality control"

# List all available versions
shelley find samtools -v

# Build an Lmod module
shelley build samtools

# Build a specific version
shelley build samtools/1.21

# Uninstall a specific version
shelley clean samtools:1.21

# Interactive mode
shelley interactive
```

## Documentation

| Type | File | What it covers |
|---|---|---|
| Tutorial | [docs/tutorials/getting-started.md](docs/tutorials/getting-started.md) | First-time walkthrough |
| Tutorial | [docs/tutorials/nfcore-rnaseq.md](docs/tutorials/nfcore-rnaseq.md) | Run an nf-core RNA-seq pipeline using CVMFS containers |
| How-to | [docs/how-to/install.md](docs/how-to/install.md) | Install/update on a VM or BioShell image |
| How-to | [docs/how-to/find-and-search.md](docs/how-to/find-and-search.md) | find, search |
| How-to | [docs/how-to/build-modules.md](docs/how-to/build-modules.md) | build and batch operations |
| How-to | [docs/how-to/clean-modules.md](docs/how-to/clean-modules.md) | Uninstall a specific tool version |
| How-to | [docs/how-to/maintain-corpus.md](docs/how-to/maintain-corpus.md) | Update data artifacts |
| How-to | [docs/how-to/developer-setup.md](docs/how-to/developer-setup.md) | Dev environment and tests |
| Reference | [docs/reference/cli.md](docs/reference/cli.md) | All CLI commands |
| Reference | [docs/reference/data-sources.md](docs/reference/data-sources.md) | Data artifacts and schemas |
| Reference | [docs/reference/architecture/glossary.md](docs/reference/architecture/glossary.md) | Domain terms used in the code, docs and architecture diagrams |
| Reference | [docs/reference/architecture/current-state.md](docs/reference/architecture/current-state.md) | As-is class, package, deployment, sequence and lifecycle diagrams |
| Reference | [docs/reference/architecture/target-state.md](docs/reference/architecture/target-state.md) | To-be (agreed) class, package, sequence and lifecycle diagrams |
| Reference | [docs/reference/architecture/traceability.md](docs/reference/architecture/traceability.md) | Which modules serve each architecture driver |
| Explanation | [docs/explanation/install-design.md](docs/explanation/install-design.md) | Why shelley installs with uv |
| Explanation | [docs/explanation/search-design.md](docs/explanation/search-design.md) | Why the search is designed this way |
| Explanation | [docs/explanation/build-design.md](docs/explanation/build-design.md) | Why the build is designed this way |
| Explanation | [docs/explanation/clean-design.md](docs/explanation/clean-design.md) | Why the clean is designed this way |
| Explanation | [docs/explanation/architecture-design.md](docs/explanation/architecture-design.md) | Architecture review: summary, artefacts, open decisions and risks (start here) |
| Explanation | [docs/explanation/architecture-drivers.md](docs/explanation/architecture-drivers.md) | Review of the as-is design, and the ranked drivers for the target design |
| Explanation | [docs/explanation/architecture-evaluation.md](docs/explanation/architecture-evaluation.md) | How the current and target designs behave in seven scenarios |
| Explanation | [docs/explanation/decisions/0001-split-discovery-from-exposure.md](docs/explanation/decisions/0001-split-discovery-from-exposure.md) | ADR 0001: Split discovery from exposure |
| Explanation | [docs/explanation/decisions/0002-tag-value-object-with-conda-ordering.md](docs/explanation/decisions/0002-tag-value-object-with-conda-ordering.md) | ADR 0002: A `Tag` value object with conda version ordering |
| Explanation | [docs/explanation/decisions/0003-single-source-of-versions.md](docs/explanation/decisions/0003-single-source-of-versions.md) | ADR 0003: One source of versions: the snapshot plus a live check |
| Explanation | [docs/explanation/decisions/0004-fail-fast-when-network-unavailable.md](docs/explanation/decisions/0004-fail-fast-when-network-unavailable.md) | ADR 0004: Fail fast when the network is unavailable |
| Explanation | [docs/explanation/decisions/0005-plan-then-apply-with-compensating-transaction.md](docs/explanation/decisions/0005-plan-then-apply-with-compensating-transaction.md) | ADR 0005: Plan, then apply inside an undoing transaction |
| Explanation | [docs/explanation/decisions/0006-local-registry-holds-authored-entries-only.md](docs/explanation/decisions/0006-local-registry-holds-authored-entries-only.md) | ADR 0006: The local registry holds shelley-authored entries only |
| Explanation | [docs/explanation/decisions/0007-resolve-before-elevating.md](docs/explanation/decisions/0007-resolve-before-elevating.md) | ADR 0007: Resolve before elevating, and pass the tag with a hidden flag |

## Architecture

Shelley is organised as a modular Python package:

```
shelley/
├── client/          # CLI entry point (thin routing)
├── commands/        # One module per user-facing command
├── builder/         # CVMFS module building functionality
├── script/          # Run-once to generate cached data
├── search/          # Tool metadata search sources
└── utils/           # Shared utilities, cache, rendering, style
```

## Requirements

- Python 3.11+
- Access to CVMFS repositories (typically `/cvmfs/singularity.galaxyproject.org/`)
- Lmod (for module management)
- Singularity (for container execution)

## License

Copyright (C) 2026 Frederick Jaya, Mitchell O'Brien, Georgie Samaha.

shelley is free software: you can redistribute it and/or modify it under the
terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version. See [LICENSE](LICENSE) for the full text.

## Acknowledgements

This project was completed as part of the BioCLI project, supported by the
Australian BioCommons through funding from Bioplatforms Australia and the
Australian Government's National Collaborative Research Infrastructure Strategy
(NCRIS).

We thank [Vanessa Sochat](https://orcid.org/0000-0002-4387-3819) for
[Singularity Registry HPC (shpc)](https://github.com/singularityhub/singularity-hpc)
and for guidance on [container-guts](https://github.com/singularityhub/guts), on
which shelley builds.

We'd also like to thank Eden Zhang (SIH) for developing the shelley ascii;
Johan Gustafsson (Australian BioCommons), Mike Lynch, Senhui Guo, and Sebastian
Haan (SIH) for valuable discussion around installation and tool metadata.
