# quartobot

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-v0.1%20in%20flight-orange.svg)](DESIGN.md)

The manubot manuscript-as-software pattern, on Quarto.

> **Status:** v0.1 in flight. CLI commands ship; the Quarto extension
> and the manuscript template ship. An architecture pivot is under
> discussion in [`docs/citation-pipeline.md`](docs/citation-pipeline.md)
> that would collapse the extension into a single pre-render hook
> calling the CLI directly — read the design doc before non-trivial
> work, and watch the [v0.1 milestone](https://github.com/seandavi/quartobot/milestone/1)
> for tagging.

## What this is

Manubot has, for eight years, run scholarly manuscripts as a git repository
that builds itself on every commit, resolves citations from DOIs and
PubMed IDs automatically, hands out an immutable permalink per commit, and
collaborates through pull requests. The pattern is published
([Himmelstein et al. 2019](https://doi.org/10.1371/journal.pcbi.1007128))
and has been used for hundreds of preprints.

Quarto now covers more of scholarly publishing than manubot ever did —
manuscripts, books, websites, slides, dashboards, courseware — but the
manubot pattern does not yet exist there natively. That's the gap this
repo closes.

The shipping surface is a Python CLI and (optionally) a GitHub template:

1. **`quartobot`** — a Python CLI. `quartobot resolve` pre-fetches
   citations through manubot's resolver library, so CI never sees a
   Crossref hiccup mid-render. `quartobot scan` summarizes cite keys
   grouped by prefix with duplicate detection. `quartobot validate`
   is the CI-lint surface (static checks against `_quarto.yml`).
   `quartobot init` scaffolds the pattern into an existing Quarto
   project. Authors write `@doi:10.1371/journal.pcbi.1007128`,
   `@pmid:31479462`, `@arxiv:2104.10729`, `@isbn:…`, or bare DOIs in
   their prose, and citations resolve.

   ```bash
   pip install quartobot          # once v0.1 tags
   uv pip install -e .            # from this repo, today
   ```

2. **`quartobot-manuscript`** — a GitHub template that combines Quarto
   Manuscripts, the CLI's pre-render hook, and a CI workflow that
   gives every commit an immutable permalink at `/v/<sha>/`, embeds
   that permalink in the rendered HTML, posts PR previews via sticky
   comment, and deploys HTML + PDF + DOCX to GitHub Pages.

   ```bash
   gh repo create my-paper --template seandavi/quartobot-manuscript
   ```

Under the current (filter-based) architecture, a Quarto extension
`quarto-manubot-cite` also ships at `quarto add seandavi/quartobot`.
The pivot proposal in `docs/citation-pipeline.md` collapses that
extension into a one-line pre-render hook calling the CLI — the
extension shrinks to optional wiring, the CLI becomes the load-bearing
surface. PyPI publishing and the standalone template repo are part of
the v0.1 tag.

## Why this exists

[manubot/manubot#332](https://github.com/manubot/manubot/issues/332)
("Quarto integration") was opened by Anthony Gitter in April 2022 after a
conversation with Sean Davis. Four years later, no PR, no assignee — but
`pandoc-manubot-cite` shipped inside the `manubot` package and Quarto
Manuscripts shipped as a first-party project type. The integration is
small once you stop trying to rebuild the resolver. This repo is the work
to resolve that issue.

## Working example

[seandavi/2026-venice-spatial-hackathon-manuscript](https://github.com/seandavi/2026-venice-spatial-hackathon-manuscript)
runs the CI / permalink / banner half of the pattern on a live 25-author
preprint from the Bioconductor Spatial Hackathon. That's the working
reference the template is being lifted from.

## See also

- Design — [`DESIGN.md`](DESIGN.md)
- Prior art — [`docs/prior-art.md`](docs/prior-art.md)
- Publication plan — [`docs/publication-plan.md`](docs/publication-plan.md)
- Conversation notes — [`docs/conversation-notes.md`](docs/conversation-notes.md)
- Contributing — [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Code of conduct — [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)

## License

[MIT](LICENSE).
