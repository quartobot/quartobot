# Prior art

A short inventory of what already exists in this space, what it covers,
and what gap it leaves. Updated 2026-05-13. Open a PR if anything below
is wrong, missing, or out of date.

## Things to build on (we will reuse these directly)

### `pandoc-manubot-cite` ([docs](https://manubot.github.io/manubot/reference/manubot/pandoc/cite_filter/))

A pandoc filter shipped *inside* the `manubot` Python package
(`pip install manubot` gives you the `pandoc-manubot-cite` command).

- Resolves `@doi:`, `@pmid:`, `@arxiv:`, `@isbn:`, `@url:`,
  `@wikidata:`, `@zotero:`, plus bare DOIs (`@10.1371/...`).
- Writes resolved metadata to a CSL JSON bibliography file via the
  `manubot-output-bibliography` metadata key.
- Standard pandoc filter — runs anywhere pandoc runs, including inside
  a Quarto project (Quarto extensions *are* pandoc filters).
- Manubot is actively maintained: v0.6.1 was tagged July 2024.

**Gap it leaves:** no documented Quarto integration. No example showing
how to wire it into `_quarto.yml`. No Quarto extension that installs it
ergonomically. This is the gap a thin `quarto-manubot-cite` extension
fills.

### Quarto Manuscripts ([docs](https://quarto.org/docs/manuscripts/))

First-party Quarto project type, since Quarto 1.4.

- Project layout: `_quarto.yml` configured for manuscript output.
- CI workflow (`.github/workflows/publish.yml`) that renders to HTML +
  PDF + DOCX + JATS XML and deploys to gh-pages on push to main.
- Visual editor citation insert from DOI / Crossref / PubMed.

**Gap it leaves:** no per-commit immutable permalinks, no embedded
version banner, no PR preview comments, no auto-resolved citations
(visual editor insert is one-shot and interactive). This is the
template we want to *extend* with the missing pieces.

## Things in the same neighborhood (reference; we don't build on these directly)

### `pandoc-url2cite` ([blog post](https://phiresky.github.io/blog/2019/pandoc-url2cite/))

Pandoc filter that resolves URLs, DOIs, ISBNs to citations. Caches to
`citation-cache.json`. Predates `pandoc-manubot-cite` by ~2 years and
covers fewer identifier types. Light maintenance after 2021.

### `pandoc-doi2bib` ([dev.to write-up](https://dev.to/aeroreyna/using-doi-tags-as-references-with-pandoc-id3))

Smaller pandoc filter targeting `[@DOI:...]` keys specifically.
Subsumed by `pandoc-manubot-cite`.

### `bcdavasconcelos/citetools` ([GitHub](https://github.com/bcdavasconcelos/citetools))

Quarto/pandoc extension bundling several Lua filters for advanced
bibliography behaviors (consistent output across LaTeX/DOCX/HTML, etc.).
Doesn't auto-resolve identifiers — addresses different problems.

### `dialoa/recursive-citeproc` ([GitHub](https://github.com/dialoa/recursive-citeproc))

Pandoc/Quarto filter for self-citing BibTeX bibliographies. Niche and
orthogonal to auto-resolution.

### `bcdavasconcelos/cite-field` ([GitHub](https://github.com/bcdavasconcelos/cite-field))

Lua filter for printing arbitrary fields of a bibliographic entry
inline. Useful, unrelated.

### CiteDrive ([site](https://www.citedrive.com/en/quarto/))

Commercial reference-management web app with a Quarto integration.
Different angle: hand-curated references with cloud sync. Not an
auto-resolver.

### Quarto visual-editor citation insert

Built into Quarto via `pandoc --citeproc` and the visual editor's
"Insert Citation" dialog. Inserts from Zotero, DOI lookup, or
Crossref/DataCite/PubMed search; appends to bibliography. Interactive
only — not a pre-render auto-resolver, not invoked on every build.

## Existing scholarly Quarto templates (good examples; not the same artifact)

- [christopherkenny/nature](https://github.com/christopherkenny/nature) — Springer Nature submissions.
- [AaronGullickson/aog-article-quarto](https://github.com/AaronGullickson/aog-article-quarto) — scholarly PDF article template.
- [drganghe/quarto-academic-website-template](https://github.com/drganghe/quarto-academic-website-template) — academic website template.
- [jonjoncardoso/quarto-template-for-university-courses](https://github.com/jonjoncardoso/quarto-template-for-university-courses) — course websites.
- [joundso/repub](https://github.com/joundso/repub) — reproducible publishing template using Quarto.

None of these implement the full manubot pattern. Several would be
candidate adopters of the `quarto-manubot-cite` extension.

## Manubot itself (the upstream we are extending)

- [manubot/manubot](https://github.com/manubot/manubot) — Python package, ~470 stars, actively maintained.
- [manubot/rootstock](https://github.com/manubot/rootstock) — the canonical "Use this template" repo for manubot manuscripts.
- [Open collaborative writing with Manubot, PLOS Comp Bio 2019](https://doi.org/10.1371/journal.pcbi.1007128) — the foundational paper.
- [manubot/manubot#332](https://github.com/manubot/manubot/issues/332) — "Quarto integration" issue opened by Anthony Gitter in April 2022, in response to conversations with Sean Davis. **This repo is the work to resolve it.**
