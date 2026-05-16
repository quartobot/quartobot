---
title: The manuscript template
description: Quarto manuscript + pre-render hook + CI for permalinks, PR previews, and gh-pages deploy.
---

A GitHub template combining Quarto, the
[`quartobot resolve` pre-render hook](/cli/#quartobot-resolve), and a CI
workflow that gives every commit an immutable permalink, embeds that
permalink in the rendered HTML, posts PR previews via sticky comment,
and deploys HTML + PDF + DOCX to GitHub Pages.

If you're writing a longer work (textbook, review, edited volume, thesis),
see [the book template](/book/) — same pattern, different project shape.

:::caution
The template is currently scaffolded at
[`template/`](https://github.com/quartobot/quartobot/tree/main/template)
inside this repo. Promotion to its own template repo
(`quartobot/quartobot-manuscript`) is tracked at
[#13](https://github.com/quartobot/quartobot/issues/13). Until then,
`gh repo create --template` doesn't work — read the source instead.
:::

## What it gives you

- **Per-commit permalinks** at `https://<owner>.github.io/<repo>/v/<sha>/`.
  The HTML version banner embeds the commit's snapshot URL so a downloaded
  file knows which version it is.
- **PR previews** at `https://<owner>.github.io/<repo>/pr/<n>/`, with a
  sticky comment on the PR linking to the latest preview and the
  per-commit snapshots.
- **Auto-resolved citations** through the pre-render hook.
- **Multi-format output** — HTML, PDF, DOCX from one source on every push.
- **Automatic preview teardown** when PRs close.

## CI architecture

`template/.github/workflows/render.yml` is a ten-line caller of the
[upstream reusable workflow](https://github.com/quartobot/quartobot/blob/main/.github/workflows/render-reusable.yml).
Bug fixes to the upstream workflow flow to every consumer pinned at
`@v0.1` automatically.

Detach to fully copied-out workflows with `quartobot detach` (tracked at
[#25](https://github.com/quartobot/quartobot/issues/25)) when that ships,
or manually copy the reusable workflow into your repo as a starting
point for a forked pipeline.

## The version banner

`_version-banner.html.template` is the HTML banner Quarto injects above
the title (`format.html.include-before-body`). On push-to-main builds,
CI substitutes five placeholders:

| Placeholder            | Substitution                                    |
|-----------------------|--------------------------------------------------|
| `__VERSION_SHA__`     | 7-character short SHA                            |
| `__VERSION_URL__`     | immutable per-commit permalink                   |
| `__VERSION_PDF__`     | direct PDF link for that snapshot                |
| `__VERSION_LATEST__`  | `/` root of the gh-pages site                    |
| `__VERSION_GH__`      | GitHub repo URL                                  |

PR builds keep the committed dev placeholder; the PR-specific URLs are
posted in the sticky PR comment instead. PDF and DOCX skip the banner
entirely.

## See also

- Template source: [`template/`](https://github.com/quartobot/quartobot/tree/main/template)
- [Working example](https://github.com/seandavi/2026-venice-spatial-hackathon-manuscript)
  — a 25-author preprint that has been running the CI half of this pattern
  in production.
- [Extend vs fork Quarto Manuscripts template](https://github.com/quartobot/quartobot/issues/3)
  — open question.
