---
title: The book template
description: Quarto book + pre-render hook + CI for chapter-shaped works.
---

A GitHub template combining Quarto **books**, the
[`quartobot resolve` pre-render hook](/cli/#quartobot-resolve), and a CI
workflow that gives every commit an immutable permalink, embeds that
permalink in every chapter's HTML, posts PR previews via sticky
comment, and deploys the book site to GitHub Pages.

If you're writing a single document (paper, preprint, technical
report), see [the manuscript template](/template/) — same pattern,
single-document shape.

:::caution
The book template is currently scaffolded at
[`template-book/`](https://github.com/quartobot/quartobot/tree/main/template-book)
inside this repo. Promotion to its own template repo
(`quartobot/quartobot-book`) happens alongside the manuscript template
promotion at v0.1 release time. Until then, `gh repo create --template`
doesn't work — read the source instead.
:::

## What it gives you

- **Per-commit permalinks** at `https://<owner>.github.io/<repo>/v/<sha>/`.
  Every chapter's HTML carries the commit's snapshot URL in a banner so
  a downloaded chapter knows which version produced it.
- **PR previews** at `https://<owner>.github.io/<repo>/pr/<n>/`, with a
  sticky comment on the PR linking to the latest preview and the
  per-commit snapshots.
- **Auto-resolved citations** through the pre-render hook. Cite by
  `@doi:`, `@pmid:`, `@arxiv:`, `@isbn:`, etc. in any chapter; the
  resolver runs once per render across the whole project.
- **Multi-page HTML book site** — Quarto's book project type provides
  sidebar navigation, full-text search, per-chapter HTML pages, and a
  configurable theme.
- **Automatic preview teardown** when PRs close.

## What differs from the manuscript template

- **Output is `_book/`, not the project root.** Quarto books write to
  `_book/<chapter>.html` plus `_book/search.json`, `_book/site_libs/`,
  etc. The reusable workflow's `project-type: book` mode lifts the
  whole `_book/` directory into `public/v/<sha>/` recursively, so the
  deployed URL serves `/v/<sha>/index.html` directly.
- **Per-chapter bibliographies** are Quarto book's idiomatic HTML
  output — each chapter's references render at the bottom of that
  chapter. The manuscript template puts all references at the end of
  a single document.
- **No PDF output in v0.1.** Book PDF compilation is a separate concern
  (multi-chapter LaTeX layout, page-break tuning) deferred past v0.1.
  The template's `render.yml` sets `formats: "html"` and
  `tinytex: "false"` for a faster CI job.
- **Banner without PDF link.** Since the staging step doesn't produce
  a book PDF, the version banner template omits the `__VERSION_PDF__`
  substitution.

## CI architecture

`template-book/.github/workflows/render.yml` is a thin caller of the
[upstream reusable workflow](https://github.com/quartobot/quartobot/blob/main/.github/workflows/render-reusable.yml)
with `project-type: book`. The reusable workflow handles the
book-specific staging (whole `_book/` directory copy) and adapts the
sticky PR comment to omit the PDF column.

## The version banner

`_version-banner.html.template` is the HTML banner Quarto injects above
every chapter's title (via `format.html.include-before-body`). On
push-to-main builds, CI substitutes four placeholders:

| Placeholder            | Substitution                              |
|------------------------|-------------------------------------------|
| `__VERSION_SHA__`      | 7-character short SHA                     |
| `__VERSION_URL__`      | immutable per-commit permalink            |
| `__VERSION_LATEST__`   | `/` root of the gh-pages site             |
| `__VERSION_GH__`       | GitHub repo URL                           |

PR builds keep the committed dev placeholder; the PR-specific URLs are
posted in the sticky PR comment instead.

The book template's banner omits `__VERSION_PDF__` (which the
manuscript template uses) — book HTML output is a multi-page site,
not a single PDF.

## Why books?

Manubot was manuscript-shaped by design. Quarto books bring the same
manuscript-as-software affordances — versioned source, auto-resolved
citations, per-commit permalinks, PR-based collaboration — to longer
works: textbooks, reviews, theses, working notes, edited volumes,
courseware.

The book deliverable is also the cleanest demonstration that quartobot
isn't just porting manubot to a slightly different manuscript shape.
Same pattern, broader artifact.

## See also

- Template source: [`template-book/`](https://github.com/quartobot/quartobot/tree/main/template-book)
- [Minimal book example](https://github.com/quartobot/quartobot/tree/main/examples/book-minimal) — the smallest book exercising the pre-render hook without the template's CI/banner machinery
- [The manuscript template](/template/) — same pattern, single-document shape
- Roadmap: [v0.1 books support](https://github.com/quartobot/quartobot/issues/18)
