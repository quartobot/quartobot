# Design

## What the pattern is

Manubot pioneered "manuscript as software": a manuscript lives in a git
repository, every commit is rendered into HTML/PDF/DOCX by CI, every
commit has an immutable permalink, citations are resolved automatically
from persistent identifiers (DOIs, PubMed IDs, arXiv IDs, ISBNs), and
collaboration happens through pull requests. The pattern is now eight
years old and has been used for hundreds of scholarly preprints; the
underlying paper is [Himmelstein et al. 2019](https://doi.org/10.1371/journal.pcbi.1007128).

The Quarto ecosystem now covers more of academic publishing than manubot
ever did — manuscripts, books, websites, slides, dashboards, blogs,
courseware — but the manubot pattern does not yet exist there natively.
Authors who want it must either accept manubot's full toolchain (which
is bespoke) or rebuild the pattern themselves on top of Quarto from
scratch.

This project closes that gap.

## What "the pattern" means concretely

Six components, in roughly the order an author encounters them:

1. **One source of truth in git.** Prose is markdown (`.qmd`),
   bibliography is plain text, figures are tracked. Everything an author
   needs to reproduce the document is in the repo.

2. **Citation by persistent identifier.** Authors paste a DOI, a PubMed
   ID, an arXiv ID, an ISBN, or a URL into their prose using
   `@doi:10.x/y` (or bare `@10.x/y`) and CI resolves it into a real
   bibliography entry on next build. No manual `.bib` curation.

3. **Multi-format render in CI.** HTML, PDF, DOCX (and JATS XML for
   submission) all built from the same source on every push.

4. **Immutable per-commit permalinks.** Every commit produces a snapshot
   at `https://<owner>.github.io/<repo>/v/<commit-sha>/`. The permalink
   is embedded in the rendered HTML so a downloaded file always knows
   which version it is.

5. **PR previews.** Every pull request gets its own rendered preview at
   `…/pr/<n>/` and a sticky comment with the links so reviewers don't
   need a local Quarto install.

6. **One-click adoption.** Authors don't have to assemble the workflow
   themselves — they click "Use this template," paste in their prose,
   and start writing.

## What already exists (so we don't rebuild it)

- **Quarto Manuscripts** (first-party Quarto project type, since 1.4)
  gives us #1 and most of #3. It ships a working `_quarto.yml`,
  `publish.yml` GitHub Action, and gh-pages deploy.
- **`pandoc-manubot-cite`**, shipped inside the `manubot` Python package
  itself, gives us #2 — it's a standard pandoc filter that resolves
  `@doi:`, `@pmid:`, `@arxiv:`, `@isbn:`, `@url:`, `@wikidata:`,
  `@zotero:`, and infers prefixes for bare identifiers. Output is CSL
  JSON. Manubot is actively maintained (v0.6.1, July 2024).
- The CI pieces for #4 and #5 — versioned permalinks, embedded version
  banner, sticky PR preview comments — are already running in
  [seandavi/2026-venice-spatial-hackathon-manuscript](https://github.com/seandavi/2026-venice-spatial-hackathon-manuscript)
  on a real 25-author preprint. They need to be lifted out of that
  bespoke repo and into a clean template.

What is *missing* is the wiring: nobody has documented that
`pandoc-manubot-cite` works inside a Quarto project, nobody has
published a Quarto extension that installs it ergonomically, and nobody
has packaged Quarto Manuscripts + the extension + the CI pattern as a
single one-click template.

See [`docs/prior-art.md`](docs/prior-art.md) for a fuller inventory.

## What we will build

Two artifacts that ship together:

### 1. `quarto-manubot-cite` — Quarto extension

A thin Quarto extension that:

- Declares `pandoc-manubot-cite` as a filter and writes the right
  `_quarto.yml` snippets when added to a project.
- Documents the citation-key vocabulary (`@doi:`, `@pmid:`, `@arxiv:`,
  …) for Quarto users.
- Provides sensible defaults for CSL JSON output, caching, and
  rate-limit/contact metadata.
- Optionally bundles a small `quartobot scan` CLI for offline cache
  warm-up and dry-run validation of unresolved keys.

Install path: `quarto add seandavi/quarto-manubot-cite`. ~50–200 lines
plus tests and docs. Reuses `manubot.cite` for all resolvers.

### 2. `quartobot-manuscript` — Template repository

A GitHub template that combines:

- Quarto Manuscripts project layout (`_quarto.yml`, `index.qmd`, sample
  sections, `references.bib`/`references.json`).
- The `quarto-manubot-cite` extension wired up.
- A CI workflow (`.github/workflows/render.yml`) that gives every
  commit an immutable permalink, embeds it in the rendered HTML,
  publishes PR previews with sticky comments, and deploys HTML + PDF +
  DOCX to GitHub Pages.
- A README walking a new author through the three steps from
  "use this template" to "click the rendered URL."

Adoption is `gh repo create my-paper --template seandavi/quartobot-manuscript`.

A second template variant for Quarto **books** is plausible v2 work —
the pattern is identical, only the project type differs.

## Key design decisions (and why)

| Decision | Choice | Why |
|----------|--------|-----|
| Bibliography format for auto-resolved entries | **CSL JSON**, alongside any hand-curated `references.bib` | CSL JSON's `id` field accepts arbitrary strings, so `@doi:10.1038/foo` can be both the citation key and the BibTeX-equivalent entry id. BibTeX keys forbid `/` and `:` and would require key transformation, which defeats the manubot point. |
| Citation key normalization | Lowercase prefix, identifier preserved as-is (`@doi:10.X/y`, not `@DOI:10.X/y`) | Matches manubot's own convention; lets us reuse `manubot.cite` directly. |
| Resolver implementation | Reuse `manubot.cite` (already in the `manubot` Python package) | Tested, maintained, covers all the identifier types, has good error handling and rate-limit awareness. We get this for free. |
| Caching | Build-time cache at `_freeze/quartobot-cache.json` (or whatever Quarto convention picks up) | Once an entry is resolved, builds stay offline. CI never re-fetches if `.json` is already present. |
| Permalink format | `/v/<full-sha>/` per the manubot convention | Long-form SHA so the snapshot URL contains a verifiable identifier. Short SHA shown to humans in the banner. |
| Version banner placement | Title-adjacent callout in HTML only; PDF/DOCX skip via `content-visible when-format="html"` | Quarto's right-side TOC is generated from headings; injecting arbitrary content there requires templates we don't want to maintain. |
| PR preview links | Sticky PR comment from `marocchino/sticky-pull-request-comment` | The HTML doesn't need a PR-aware banner — the comment is the right surface. Keeps the HTML simple. |
| License | MIT | OSI-approved, matches Quarto and manubot, JOSS-friendly. |

## Open questions

- **Naming.** `quartobot` is sticky and signals lineage; `quarto-manubot-pattern`
  is neutral and descriptive. The first round of co-author conversation
  (especially with the manubot team) will probably settle this.
- **Scope of the v1 template.** Manuscript only, or also book? The
  pattern transfers, but each project type has its own defaults to
  settle. I'd ship the manuscript template first and add a book variant
  driven by demand.
- **Relationship to the existing Quarto Manuscripts template.** Should
  `quartobot-manuscript` *extend* the first-party template (so we
  inherit upstream improvements), or *fork* it (so we have control over
  defaults)? Probably extend.
- **Citation cache location and versioning.** Manubot caches under
  `output/`; Quarto's conventions point at `_freeze/`. Pick one and
  document.
- **Whether the Python CLI is needed at all.** The whole resolver may
  just be `pandoc-manubot-cite` declared as a filter. A separate
  `quartobot scan` CLI is only worth it if there's offline cache
  warm-up or pre-render validation that's awkward to express otherwise.
- **What happens when the resolver fails mid-build.** Crossref
  occasionally hiccups; PubMed has stricter rate limits. The build
  should degrade gracefully — warn, skip, mark as `[citation pending]`
  in the rendered output, but not fail the whole render.

## Out of scope (for now)

- Living reviews / dashboards / slides templates. Pattern transfers but
  not a v1 deliverable.
- Replacing or competing with manubot. The framing is adoption, not
  displacement.
- A reference-management UI. CiteDrive and Zotero exist; we're not in
  that business.
- Hosting infrastructure. GitHub Pages does the job for free; we leave
  it there.
