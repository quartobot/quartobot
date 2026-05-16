---
title: Install
description: Every install method for the quartobot CLI, when to use which.
---

Five ways to get `quartobot` on your machine, in roughly descending
order of how often you'll want each.

## Recommended: `uv tool install` from GitHub

```bash
uv tool install git+https://github.com/quartobot/quartobot
```

This puts `quartobot` on your user `PATH` (typically `~/.local/bin` or
similar) so commands like `quartobot init`, `scan`, `validate`, and
`resolve` work from any project directory without a venv activation
dance.

[uv](https://docs.astral.sh/uv/) manages the underlying Python and
dependencies in an isolated environment behind the scenes. You don't
need to maintain a virtualenv yourself.

Pin a specific ref:

```bash
uv tool install git+https://github.com/quartobot/quartobot@<branch-or-tag-or-sha>
```

Upgrade later:

```bash
uv tool upgrade quartobot
```

Uninstall:

```bash
uv tool uninstall quartobot
```

## One-shot: `uvx`

Run `quartobot` without installing it persistently. Useful for trying
it out, scripted one-off jobs, or pinning a specific version in CI
without polluting the host install.

```bash
uvx --from git+https://github.com/quartobot/quartobot quartobot --help
uvx --from git+https://github.com/quartobot/quartobot quartobot resolve --from-scan .
```

The `--from` flag is required because the package name and the command
name are the same. Without it, `uvx` would look for a PyPI package
literally named `quartobot`.

## `pip install` (post-v0.1 tag)

Once `v0.1.0` ships to PyPI, the registry path works too:

```bash
pip install quartobot
```

The trade-off: `pip install` into a system Python isn't recommended
on modern Linux distros (you'll likely hit
[PEP 668](https://peps.python.org/pep-0668/) "externally-managed-environment"
errors). Use `uv tool install` instead, or `pipx install quartobot`,
or install into a project venv with `uv pip install quartobot`.

## For repo development

Clone and install editable:

```bash
git clone https://github.com/quartobot/quartobot.git
cd quartobot
uv pip install -e .
```

For the full dev environment (lint, type-check, test):

```bash
uv sync --extra dev
uv run pytest
uv run ruff check src tests
uv run mypy
```

## Requirements

- **Python ≥ 3.10.** `uv tool install` manages this automatically.
- **Quarto ≥ 1.4** if you're rendering documents. [Install Quarto.](https://quarto.org/docs/get-started/)
- **No system manubot install needed.** `quartobot` declares manubot
  as a dependency; `uv tool install` brings it along.

## Verify

```bash
quartobot --version
quartobot --help
```

If `quartobot --version` works but the freshly-installed command
isn't picked up by a new shell, the install directory (typically
`~/.local/bin`) isn't on your `PATH`. `uv tool update-shell` adds
it; a login reload then picks it up.
