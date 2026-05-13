# quartobot

The manubot manuscript-as-software pattern, ergonomically, on Quarto.

> **Status:** design phase. Nothing to install yet — we're writing down the
> pattern and the plan before we cut code. See [DESIGN.md](DESIGN.md).

## What this will be

Two artifacts that ship together:

1. A small **Quarto extension** (`quarto-manubot-cite`) that wires
   [`pandoc-manubot-cite`](https://manubot.github.io/manubot/reference/manubot/pandoc/cite_filter/)
   — already shipped inside the `manubot` Python package — into a Quarto
   project, so authors can write `@doi:10.x/y`, `@pmid:N`, `@arxiv:…`,
   `@biorxiv:…`, `@isbn:…`, etc., and have entries auto-resolved into a
   CSL JSON bibliography.
2. A **template repository** that bundles Quarto Manuscripts + the
   extension + a CI workflow that gives every commit an immutable
   permalink, embeds that permalink in the rendered HTML, posts PR
   previews on every pull request, and deploys to GitHub Pages.

Adoption: `gh repo create my-paper --template seandavi/quartobot-manuscript`
and you're writing prose against the same flow manubot pioneered, on top
of Quarto's full publishing stack (manuscripts, books, websites, slides).

## Origin

Manubot's [issue #332](https://github.com/manubot/manubot/issues/332)
("Quarto integration"), opened by [@agitter](https://github.com/agitter)
in April 2022, identifies exactly this opening. That issue grew out of
conversations between Sean Davis and the manubot team. This repo is the
work to resolve it.

## See also

- Design — [`DESIGN.md`](DESIGN.md)
- Prior art — [`docs/prior-art.md`](docs/prior-art.md)
- Publication plan — [`docs/publication-plan.md`](docs/publication-plan.md)
- Conversation notes — [`docs/conversation-notes.md`](docs/conversation-notes.md)
- Working example — [seandavi/2026-venice-spatial-hackathon-manuscript](https://github.com/seandavi/2026-venice-spatial-hackathon-manuscript)
  has the CI/permalink/banner half of the pattern already running on a
  25-author preprint.

## License

[MIT](LICENSE).
