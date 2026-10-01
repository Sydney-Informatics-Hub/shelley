# How to install shelley

`shelley` ships preinstalled on [BioShell](https://github.com/AustralianBioCommons/BioShell)
VM images. This guide covers installing or updating it yourself.

There is a single install mechanism — `uv tool install` — which places `shelley`
on the system PATH. No virtual environment activation is ever required. For the
reasoning behind using `uv` (and not `pip`, `pipx`, or conda), see
[../explanation/install-design.md](../explanation/install-design.md).

## Which path is for you?

| You are… | Do this |
|---|---|
| On a BioShell VM with shelley already baked in | Nothing — just run `shelley …` (see the [tutorial](../tutorials/getting-started.md)) |
| Installing/updating on a workstation or VM manually | [Prerequisites](#prerequisites) → [Install shelley](#install-shelley) (with `sudo`) |
| Baking shelley into a BioShell image (Ansible/Packer) | Same steps, run as root — see the `sudo` asides below |
| Wanting a newer shelley than the one baked in, just for yourself | [Install a newer version for yourself](#install-a-newer-version-for-yourself-per-user) |
| A developer working on shelley | [developer-setup.md](developer-setup.md) |
| Running once, outside BioShell | [Run without installing (uvx)](#run-without-installing-uvx-experimental) |

The install is **path-dependent by design**: `uv` lives at `/opt/uv`, the tool
environment at `/opt/uv/tools/shelley`, and the `shelley` executable at
`/usr/local/bin/shelley`. This makes shelley available to every user on the VM.
(uv treats every entry in its tool directory as a managed environment, so it must
be a dedicated directory like `/opt/uv/tools` — pointing it at a populated `/opt`
makes uv fail on the unrelated software already there.)

## Prerequisites

- Linux (Ubuntu 22.04+ or compatible)
- `python3`, `curl`, and `git` (via the system package manager)

### Install `uv` (system-wide)

Install `uv` into `/opt/uv` so all users can invoke it. The installer will not
create the directory, so make it first:

```bash
sudo mkdir -p /opt/uv
curl -LsSf https://astral.sh/uv/install.sh | sudo env UV_INSTALL_DIR=/opt/uv sh
```

This places `uv` and `uvx` directly under `/opt/uv/`, along with an environment
file that puts them on the PATH. Source it rather than restarting the shell, so
the step also works unattended under Ansible:

```bash
source /opt/uv/env        # sh, bash, zsh
source /opt/uv/env.fish   # fish
```

Verify:

```bash
uv --version
```

> **Ansible/Packer:** the provisioner runs as root, so drop every `sudo` above.

`uv` manages its own Python interpreter and does not modify your system Python.

## Install shelley

Install shelley into the system tool location and link its executable onto the
PATH:

```bash
sudo env UV_TOOL_DIR=/opt/uv/tools UV_TOOL_BIN_DIR=/usr/local/bin \
  /opt/uv/uv tool install git+https://github.com/Sydney-Informatics-Hub/shelley
```

`UV_TOOL_DIR=/opt/uv/tools` places the isolated tool environment at
`/opt/uv/tools/shelley/` (uv appends the package name);
`UV_TOOL_BIN_DIR=/usr/local/bin` links the executable to `/usr/local/bin/shelley`,
where all users can invoke it.

> `sudo` resets `PATH` (sudoers `secure_path`), so `uv` on your PATH is not
> visible to it — call uv by its absolute path `/opt/uv/uv`. Ansible/Packer,
> running as root, can drop `sudo` but should use the same absolute path.

Verify:

```bash
shelley --help
```

> **Ansible/Packer:** run the exact same command without `sudo` (the provisioner
> is already root). The canonical Ansible role and validation tasks live in the
> [BioShell repository](https://github.com/Sydney-Informatics-Hub/BioShell).

### Install a specific branch

To get the latest development version or a specific branch, append `@branch_name`:

```bash
sudo env UV_TOOL_DIR=/opt/uv/tools UV_TOOL_BIN_DIR=/usr/local/bin \
  /opt/uv/uv tool install git+https://github.com/Sydney-Informatics-Hub/shelley@branch_name
```

### Upgrade

The simplest way to upgrade is to run:

```bash
shelley update
```

This detects whether shelley is installed system-wide or per-user and runs the
correct `uv tool upgrade` for you (invoking `sudo` for a system-wide install).
The equivalent manual command for a system-wide BioShell install is:

```bash
sudo env UV_TOOL_DIR=/opt/uv/tools UV_TOOL_BIN_DIR=/usr/local/bin /opt/uv/uv tool upgrade shelley
```

> **Developer note:** `shelley update` will only work if shelley has been installed via `uv`.
> This will fail if you are working on e.g. a local branch and running `uv run shelley`. 

### Uninstall

```bash
sudo env UV_TOOL_DIR=/opt/uv/tools UV_TOOL_BIN_DIR=/usr/local/bin /opt/uv/uv tool uninstall shelley
```

## Install a newer version for yourself (per-user)

If a VM already has shelley baked in but you want to test a newer version — or
shelley isn't baked in yet and you only need it for your own account — install it
per-user. This needs **no `sudo`**: omit the `UV_TOOL_DIR`/`UV_TOOL_BIN_DIR`
overrides and uv installs into `~/.local` instead of the system location.

```bash
uv tool install git+https://github.com/Sydney-Informatics-Hub/shelley@dev
```

`@dev` pulls the latest development branch; once releases exist you can pin a tag
(e.g. `@v0.1.0`). This install is persistent and full-featured, including `build`.

Once installed, upgrade it later with `shelley update` (no `sudo` needed for a
per-user install).

If `shelley` is not found afterwards, add `~/.local/bin` to your PATH:

```bash
uv tool update-shell   # modifies ~/.bashrc / ~/.zshrc; reopen your shell after
```

Because `~/.local/bin` precedes `/usr/local/bin` on the PATH, your per-user shelley
**shadows** the baked-in system one without touching it — both coexist:

```bash
which -a shelley   # ~/.local/bin/shelley wins; /usr/local/bin/shelley remains
```

To remove it and fall back to the baked-in version:

```bash
uv tool uninstall shelley
```

## Run without installing (uvx, experimental)

If you are outside BioShell and only need shelley briefly, `uvx` runs it from a
cached, path-independent environment under `~/.local` without a persistent
install:

```bash
uvx --from git+https://github.com/Sydney-Informatics-Hub/shelley shelley find fastqc
```

> **Experimental — read-only commands only.** This path supports `find`
> (including `find -v`) and `search`. It does **not** support `build`, which needs the
> system `shpc`/Singularity layout that only a full VM install provides.

## Python version

`uv` creates a sandboxed Python environment that does not affect your system
Python. shelley requires Python 3.11 or later; uv selects the highest compatible
version it finds, or downloads one automatically. To pin a specific version, add
`--python`:

```bash
sudo env UV_TOOL_DIR=/opt/uv/tools UV_TOOL_BIN_DIR=/usr/local/bin \
  /opt/uv/uv tool install "git+https://github.com/Sydney-Informatics-Hub/shelley" --python 3.11
```
