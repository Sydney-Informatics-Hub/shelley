# Shelley

**A bioinformatics tool finder and module builder for CVMFS-hosted containers on [BioShell](https://github.com/Sydney-Informatics-Hub/bioimage)**

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
| Explanation | [docs/explanation/install-design.md](docs/explanation/install-design.md) | Why shelley installs with uv |
| Explanation | [docs/explanation/search-design.md](docs/explanation/search-design.md) | Why the search is designed this way |
| Explanation | [docs/explanation/build-design.md](docs/explanation/build-design.md) | Why the build is designed this way |
| Explanation | [docs/explanation/clean-design.md](docs/explanation/clean-design.md) | Why the clean is designed this way |

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

- Python 3.10+
- Access to CVMFS repositories (typically `/cvmfs/singularity.galaxyproject.org/`)
- Lmod (for module management)
- Singularity/Apptainer (for container execution)

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
