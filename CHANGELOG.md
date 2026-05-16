# Changelog

## Unreleased

### Fixed

- `scan` now strips a trailing `/` from `@url:` cite keys to match
  pandoc's cite-key parser, which treats it as terminator punctuation.
  Without this, the resolver wrote `id: url:.../path/` into
  `references.json` while pandoc-citeproc looked up `url:.../path` and
  silently degraded the citation to `[?]`. Closes #61.

### Architecture

- Settled on the `quartobot resolve` pre-render hook as the citation
  pipeline. Templates, examples, `quartobot init` scaffolding, and
  the composite CI actions all wire `project.pre-render: quartobot
  resolve --from-scan . --output references.json --id-mode citation-key`
  in `_quarto.yml`; pandoc-citeproc reads the resulting CSL JSON
  directly. See `docs/citation-pipeline.md` for the rationale.
- **Breaking:** `_extensions/seandavi/quarto-manubot-cite/` removed.
  There is no extension to `quarto add`. The on-ramp is
  `uv tool install git+https://github.com/seandavi/quartobot`.
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
(`uv tool install git+https://github.com/seandavi/quartobot`) and
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

- `quarto add seandavi/quartobot` installs `quarto-manubot-cite`,
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
