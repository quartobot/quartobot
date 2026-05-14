# quartobot

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-design%20phase-orange.svg)](DESIGN.md)

The manubot manuscript-as-software pattern, on Quarto.

> **Status:** design phase. Nothing to install yet. The architecture is
> settled in [`DESIGN.md`](DESIGN.md); the implementation is being scaffolded
> in [#7](https://github.com/seandavi/quartobot/issues/7) and adjacent issues.

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

Three artifacts ship together:

1. **`quarto-manubot-cite`** — a thin Quarto extension that wires
   [`pandoc-manubot-cite`](https://manubot.github.io/manubot/reference/manubot/pandoc/cite_filter/)
   into any Quarto project. Authors write `@doi:10.1371/journal.pcbi.1007128`,
   `@pmid:31479462`, `@arxiv:2104.10729`, `@isbn:…`, or bare DOIs in
   their prose, and citations resolve on next build.

   ```bash
   quarto add seandavi/quartobot
   ```

2. **`quartobot-manuscript`** — a GitHub template that combines Quarto
   Manuscripts, the extension, and a CI workflow that gives every commit
   an immutable permalink at `/v/<sha>/`, embeds that permalink in the
   rendered HTML, posts PR previews via sticky comment, and deploys
   HTML + PDF + DOCX to GitHub Pages.

   ```bash
   gh repo create my-paper --template seandavi/quartobot-manuscript
   ```

3. **`quartobot`** — a Python CLI for pre-render work
   `pandoc-manubot-cite` doesn't do: `quartobot scan` summarizes cite
   keys grouped by prefix with duplicate detection; `quartobot resolve`
   pre-fetches citations so CI never sees a Crossref hiccup;
   `quartobot validate` is the CI-lint surface (six static checks
   against `_quarto.yml` and the extension setup); `quartobot init`
   scaffolds the pattern into an existing Quarto project.

   ```bash
   pip install quartobot
   ```

Adoption commands aren't published yet — they describe what v0.1 will
look like. Track the [v0.1 milestone](https://github.com/seandavi/quartobot/milestone/1).

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
