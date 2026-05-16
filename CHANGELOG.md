# Changelog

## Unreleased

## v0.2.0 — 2026-05-16

The accumulated work since v0.1.0: a real docs site under
`quartobot.github.io/quartobot/`, an MCP server for agentic authoring,
snapshot retention for `gh-pages`, Jupyter notebook scanning, the org
move to `quartobot/`, and a pile of correctness fixes around citation
keys, the validate gate, and the render-CI defaults.

### Added

- `quartobot mcp` — an MCP (Model Context Protocol) server exposing
  citation-resolution tools for agentic authoring workflows (Claude
  Desktop, Codex, Gemini Code Assist, Cursor). Three read-only tools
  register: `resolve_citation` wraps `manubot.cite.citekey_to_csl_item`,
  `scan_project` and `validate_project` wrap their CLI counterparts.
  Stdio transport only; no write tools. Ships as an opt-in extra so
  the base install is unchanged: `uv tool install 'quartobot[mcp]'`.
  Closes #71.
- `quartobot resolve --output -` streams CSL JSON to stdout instead of
  writing a file. The one-shot lookup shape for shell-tool agents and
  scripts (`quartobot resolve --output - doi:… | jq '.[0].title'`). The
  human-readable summary moves to stderr in stdout mode, and no cache
  write happens; cache reads still work when `--cache <path>` is set
  explicitly. Closes #73.
- `quartobot snapshots` — CLI subcommand and retention-policy module
  for the per-commit permalink directories on `gh-pages`. Ships with
  a composite action wired into the reusable render workflow so old
  snapshots are pruned automatically.
- Starlight docs site at `quartobot.github.io/quartobot/`. CI gates
  on a built-site link-check via `linkinator` so internal references
  don't ship broken.
- `scan` reads Jupyter notebooks (`.ipynb`) — markdown cells are
  walked, cite keys reported with `file:cellN:line` for the
  duplicate-locations view. Crawl knobs: `--no-recursive` keeps the
  walk shallow, render outputs and tool caches (`_site/`, `_book/`,
  `_freeze/`, `.quarto/`, `.git/`, `.ipynb_checkpoints/`,
  `node_modules/`, etc.) skipped at any depth.

### Changed

- Repo moved to the `quartobot` GitHub org; docs Pages URL is now
  `quartobot.github.io/quartobot/`. Closes #55, #62.
- `quartobot validate` no longer fails on a key cited several times in
  the same file — only cross-file duplicates count, and the failure
  message reports the actual file count per key. `quartobot scan`
  exits 0 in every case; duplicates are reported, not gated. Closes
  #63.

### Fixed

- `scan` and `resolve` strip a trailing `/` (and other pandoc-terminator
  punctuation) from `@url:` cite keys so the resolver-side `id` matches
  what pandoc-citeproc looks up. Previously `references.json` carried
  `url:.../path/` while citeproc looked up `url:.../path` and silently
  degraded the citation to `[?]`. Closes #61.
- `render-reusable.yml`: `quarto-version` default is now `release` (was
  `""`). A freshly-init'd workflow that omits or passes an empty
  `quarto-version` installs the latest stable Quarto instead of 404ing
  on `…/releases/download/v/quarto--linux-amd64.deb`. The
  `setup-quartobot` composite action also normalizes empty input to
  `release` defensively so any consumer still pinned to a pre-fix tag
  recovers. Closes #60.
- Docs internal links use relative paths so the Astro `base` resolves
  them correctly under `/quartobot/` instead of 404ing at site root.
  Closes #69.
- Install docs cover users without `uv` (pipx parallel path, "install
  uv first" guidance, PATH troubleshooting for Quarto pre-render
  subprocess). Closes #64.

### Fixed

- `render-reusable.yml`: `quarto-version` default is now `release` (was
  `""`). A freshly-init'd workflow that omits or passes an empty
  `quarto-version` installs the latest stable Quarto instead of 404ing
  on `…/releases/download/v/quarto--linux-amd64.deb`. The
  `setup-quartobot` composite action also normalizes empty input to
  `release` defensively so any consumer still pinned to a pre-fix tag
  recovers. (#60)
- `quartobot validate` no longer fails on a key cited several times in the
  same file — only cross-file duplicates count, and the failure message
  now reports the actual file count per key. `quartobot scan` exits 0 in
  every case; duplicates are reported, not gated. ([#63](https://github.com/quartobot/quartobot/issues/63))
- `scan` and `resolve` now strip a trailing `/` from `@url:` cite keys
  to match pandoc's cite-key parser, which treats it as terminator
  punctuation. Without this, the resolver wrote `id: url:.../path/`
  into `references.json` while pandoc-citeproc looked up
  `url:.../path` and silently degraded the citation to `[?]`. Closes
  #61.

### Architecture

- Settled on the `quartobot resolve` pre-render hook as the citation
  pipeline. Templates, examples, `quartobot init` scaffolding, and
  the composite CI actions all wire `project.pre-render: quartobot
  resolve --from-scan . --output references.json --id-mode citation-key`
  in `_quarto.yml`; pandoc-citeproc reads the resulting CSL JSON
  directly. See `docs/citation-pipeline.md` for the rationale.
- **Breaking:** `_extensions/seandavi/quarto-manubot-cite/` removed.
  There is no extension to `quarto add`. The on-ramp is
  `uv tool install git+https://github.com/quartobot/quartobot`.
- `examples/extension-minimal/` renamed to `examples/minimal/`.
- `quartobot validate`: dropped `extension installed`,
  `manubot-bibliography-cache`, `manubot-output-bibliography` checks;
  added `pre-render hook` and `references.json in bibliography`
  checks. Happy-path check count is now 5 (was 6).
- `setup-quartobot` composite action: dropped the `extension-source`
  input and the "Install quarto-manubot-cite extension" step; renamed
  the manubot install step to "Install quartobot CLI" with a
  `quartobot-spec` input.

## v0.1.0 — 2026-05-14

First useful release. Installs cleanly from git
(`uv tool install git+https://github.com/quartobot/quartobot`) and
will publish to PyPI on this tag once the trusted-publisher setup
on the PyPI side is complete.

### `quartobot` CLI

- `scan` — walks a Quarto project and groups manubot cite keys by
  prefix, with duplicate detection.
- `validate` — pre-flight static checks against `_quarto.yml` and
  the extension setup (six checks).
- `resolve` — pre-fetches citations via `manubot.cite` and writes
  CSL JSON. `--id-mode citation-key` writes the CSL `id` as the
  user's prose key (e.g. `doi:10.1371/…`), suitable for
  pandoc-citeproc matching without a filter.
- `init` — scaffolds the pattern into an existing Quarto project.

### Quarto extension

- `quarto add quartobot/quartobot@v0.1.0` installs `quarto-manubot-cite`,
  wiring `pandoc-manubot-cite` as a pandoc filter.

### CI building blocks

- Reusable render workflow (`render-reusable.yml`) callable from
  any consumer repo with a ten-line wrapper.
- Composite actions: `setup-quartobot`, `render-manuscript`.

### Templates

- `template/` — `quartobot-manuscript` GitHub template (Quarto
  Manuscripts + extension + CI for permalinks, version banners,
  PR previews).
- `template-book/` — book variant.

### Design

- `docs/citation-pipeline.md` proposes a pre-render-hook
  architecture as the successor to the filter. End-to-end
  validated in CI by `.github/workflows/test-prerender-e2e.yml`.
  Not yet committed publicly to the user-facing templates —
  pending manubot-team review.
