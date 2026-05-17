# quartobot docs build orchestrator.
#
# Most pages under site/src/content/docs/ are authored as plain
# markdown and Astro renders them directly. A small set of flagship
# pages — currently just `first-manuscript` — live in docs-src/ as
# .qmd and get rendered through Quarto before Astro sees them. Those
# pages can carry live `quartobot` CLI output and citations resolved
# through the quartobot pre-render hook — the docs site uses
# quartobot to render its own docs.
#
# Quickstart:
#   just setup          # one-time: create a python env with jupyter + bash_kernel
#   just                # render docs and start the Astro preview
#   just build          # render docs and build the static site
#   just qmd            # render only the .qmd sources (fast iteration)
#   just clean          # remove generated files

# Path to the python env Quarto uses for `{bash}` / `{python}` chunks.
# `just setup` creates this; CI workflows install jupyter directly.
# Must be absolute — Quarto runs from docs-src/, so a relative path
# would resolve against the wrong cwd.
quarto_python := env_var_or_default(
    "QUARTO_PYTHON",
    justfile_directory() / ".venv-quarto" / "bin" / "python",
)

# Default: render docs and start the Astro preview server.
default: preview

# One-time setup: create a python venv with jupyter + bash_kernel so
# Quarto can execute `{bash}` chunks. Requires `uv`.
setup:
    uv venv .venv-quarto --python 3.12
    uv pip install --python .venv-quarto/bin/python jupyter bash_kernel pyyaml
    .venv-quarto/bin/python -m bash_kernel.install --user

# Render the .qmd sources through Quarto into Starlight's content
# collection. Quarto's gfm output strips YAML frontmatter and renders
# callouts as GitHub alert syntax; the post-render script rewrites
# both for Starlight.
qmd:
    QUARTO_PYTHON={{quarto_python}} bash -c 'cd docs-src && quarto render'
    python3 docs-src/scripts/post-render.py site/src/content/docs/first-manuscript.md

# Build the full static site (Quarto-rendered pages + plain markdown).
build: qmd
    cd site && npm ci
    cd site && npm run build

# Render docs and start the Astro preview server.
preview: qmd
    cd site && npm ci
    cd site && npm run dev

# Remove generated files. The .qmd sources stay in docs-src/.
clean:
    rm -f site/src/content/docs/first-manuscript.md
    rm -rf docs-src/references.json docs-src/_freeze docs-src/.quarto
    rm -rf site/dist
