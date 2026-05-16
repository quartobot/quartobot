# quartobot

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/quartobot/quartobot/blob/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/quartobot.svg)](https://pypi.org/project/quartobot/)
[![Docs](https://img.shields.io/badge/docs-quartobot.github.io-blue.svg)](https://quartobot.github.io/quartobot/)

Citation resolution and manuscript-as-software CI for Quarto.

```bash
uv tool install quartobot
```

Or from git for the unreleased main:

```bash
uv tool install git+https://github.com/quartobot/quartobot
```

Documentation: [quartobot.github.io/quartobot](https://quartobot.github.io/quartobot/).

## What it does

Authors write persistent-identifier cite keys directly in prose:

```markdown
We follow @doi:10.1371/journal.pcbi.1007128, with the dataset described
in @pmid:31479462 and methods inspired by @arxiv:2104.10729.
```

A Quarto `project.pre-render:` hook resolves each key to canonical
metadata before pandoc-citeproc runs, writes the result to a
`references.json` you can commit, and the manuscript renders the same
way on every machine — no `quartobot` install needed at render time,
no live Crossref / PubMed / arXiv hit per render. CI gets the same
behavior the author saw locally, and a network blip mid-render is no
longer a build failure.

Around that resolution step, quartobot ships a Python CLI:

- **`resolve`** is the pre-render hook itself — invoked by Quarto from
  `_quarto.yml`'s `project.pre-render:` line.
- **`scan`** and **`validate`** are CI-lint surfaces: cite-key inventory
  and static `_quarto.yml` checks.
- **`init`** scaffolds the pattern into an existing Quarto project —
  the pre-render hook wiring, the version-banner Quarto include, and
  a ten-line render workflow. Pairs with `quarto create project
  manuscript|book|website` for new projects.
- **`mcp`** starts a stdio MCP server so an agent in Claude Desktop,
  Codex, or Gemini Code Assist can call the same resolver as part of
  a drafting workflow.

Starting a new manuscript looks like:

```bash
uv tool install quartobot
quarto create project manuscript my-paper
cd my-paper && quartobot init
```

quartobot deliberately does not ship its own GitHub template repo —
Quarto's own `quarto create project` scaffolders cover the project
shape, and `quartobot init` layers the citation-resolution + CI on
top. The `template/` and `template-book/` directories in this repo
are worked-example references, not GitHub templates.

## Supported cite-key prefixes

`@doi:`, `@pmid:`, `@arxiv:`, `@isbn:`, `@url:`, `@wikidata:`,
`@pmc:`, plus hand-curated keys from a project `.bib`. Resolution
goes through [manubot](https://github.com/manubot/manubot)'s
`citekey_to_csl_item` — eight years of accumulated source-API quirks
behind a single function call. quartobot itself doesn't reimplement
resolution; it provides the Quarto integration, CI scaffolding, and
the agent-facing MCP surface.

## Why this exists

[manubot/manubot#332](https://github.com/manubot/manubot/issues/332)
("Quarto integration") was opened by Anthony Gitter in April 2022 after
a conversation with Sean Davis. Four years on, no PR, no assignee — but
Quarto Manuscripts shipped as a first-party project type, and the
integration turned out to be small once the resolver question was
settled. This repo is the work to close that issue.

## Working example

[seandavi/2026-venice-spatial-hackathon-manuscript](https://github.com/seandavi/2026-venice-spatial-hackathon-manuscript)
runs the CI / permalink / banner half of the pattern on a live
25-author preprint from the Bioconductor Spatial Hackathon. That's the
working reference the template is being lifted from.

## See also

- [Documentation site](https://quartobot.github.io/quartobot/) — install, CLI reference, MCP setup, templates, migration guides
- [Design](https://github.com/quartobot/quartobot/blob/main/DESIGN.md)
- [Citation pipeline](https://github.com/quartobot/quartobot/blob/main/docs/citation-pipeline.md) — why a pre-render hook, not a pandoc filter
- [Prior art](https://github.com/quartobot/quartobot/blob/main/docs/prior-art.md)
- [Contributing](https://github.com/quartobot/quartobot/blob/main/CONTRIBUTING.md)
- [Code of conduct](https://github.com/quartobot/quartobot/blob/main/CODE_OF_CONDUCT.md)
- [Changelog](https://github.com/quartobot/quartobot/blob/main/CHANGELOG.md)

## License

[MIT](https://github.com/quartobot/quartobot/blob/main/LICENSE).

---

*quartobot is an independent community project. It builds on Quarto but is not affiliated with or endorsed by Posit, PBC, the makers of Quarto.*
