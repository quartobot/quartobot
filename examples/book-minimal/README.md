# book-minimal

The smallest Quarto **book** project that exercises
`quarto-manubot-cite`. Mirrors the shape of
[`../extension-minimal/`](../extension-minimal/), but uses
`project: type: book` to demonstrate that the manubot pattern isn't
limited to manuscripts.

## Run it

```bash
cd examples/book-minimal/

# Once: install the extension and the resolver.
quarto add seandavi/quartobot
pip install 'manubot>=0.6,<0.7'

# Each render:
quarto render
open _book/index.html
```

## What you should see

- `_book/` directory with `index.html` (preface) and chapter pages
  (`chapters/intro.html`, `chapters/methods.html`,
  `chapters/discussion.html`), plus the standard Quarto book site
  assets (search index, sidebar, theme bundles).
- Each chapter's HTML carries its own bibliography section at the
  bottom listing only the cites that chapter references — Quarto
  book's idiomatic layout.
- `_freeze/manubot-cache.json` is populated incrementally as each
  chapter renders. On a clean second render, every cite is a cache
  hit and no network round-trip is needed.

## Per-chapter vs aggregated bibliography

Quarto book HTML output puts each chapter's references at the bottom of
that chapter. If you want a single aggregated references page,
that's currently a Quarto feature gap for book HTML — separate from
this extension. Track in
[seandavi/quartobot#34](https://github.com/seandavi/quartobot/issues/34).

## Why this isn't the template

The template (`../../template-book/` once that ships) adds: a version
banner, per-commit permalinks via CI, PR previews, gh-pages deploy.
All of that is the *pattern*. The example here is just the
*extension* on a book project type.

If you want the pattern, use the template. If you want to add manubot-
style citations to an existing Quarto book, this is the shape.

## See also

- [Manuscript-shape minimal example](../extension-minimal/)
- [Extension reference](../../_extensions/seandavi/quarto-manubot-cite/README.md)
- The book template (in progress, tracked at
  [#36](https://github.com/seandavi/quartobot/issues/36))
