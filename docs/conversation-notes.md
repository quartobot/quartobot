# Conversation notes

The thinking that produced [`DESIGN.md`](../DESIGN.md), distilled from a
working session between Sean Davis and a Claude assistant on
2026-05-13.

> **Architecture update.** The citation pipeline decision recorded
> below — `pandoc-manubot-cite` declared as a Quarto filter — was
> subsequently revisited and replaced. The settled architecture is
> the `quartobot resolve` pre-render hook described in
> [`citation-pipeline.md`](citation-pipeline.md), settled 2026-05-14.
> The filter-era passages below are kept for the design trail.

## Origin chain

- Sean and Anthony Gitter discussed Quarto–manubot integration
  in 2022.
- Anthony opened [manubot/manubot#332](https://github.com/manubot/manubot/issues/332)
  in April 2022 in response.
- Four years later: no PR, no assignee, no implementation.
  `pandoc-manubot-cite` shipped inside `manubot` in the meantime,
  Quarto Manuscripts shipped as a first-party project type, but nobody
  bridged them.
- The Venice 2026 Bioconductor Spatial Hackathon writeup happened to
  need exactly this combination of features (versioned permalinks +
  multi-format render + PR previews + auto-resolved citations) on a
  25-author preprint, and a working prototype of the CI / permalink
  half emerged during that build.
- Pulling that prototype out into a reusable artifact, plus wiring up
  `pandoc-manubot-cite`, is what this repo is.

## Decisions reached during the session

- **Two artifacts, one repo for now.** A thin Quarto extension
  (`quarto-manubot-cite`) plus a template repo
  (`quartobot-manuscript`). The template depends on the extension; the
  extension stands alone.
- **Reuse `pandoc-manubot-cite` directly** rather than rebuilding the
  resolver. Manubot's resolvers are already mature, well-cached, and
  cover all the identifier types we'd want.
- **CSL JSON for the auto-resolved bibliography**, alongside any
  hand-curated `.bib` for entries authors want to control directly.
  Quarto/pandoc accept multiple bibliography files of different formats
  natively.
- **Keep manubot's prefix syntax verbatim** (`@doi:`, `@pmid:`,
  `@arxiv:`, `@isbn:`, `@url:`, `@wikidata:`, `@zotero:`, plus bare
  identifiers). No new syntax. Compatibility with existing manubot
  manuscripts is a feature.
- **Permalink pattern: `/v/<full-sha>/`** matching manubot's URL
  convention. Snapshots immutable, latest at `/`, PR previews at
  `/pr/<n>/`.
- **Version banner is HTML-only**, injected via a CI-generated include
  file substituted by `sed`. PDF/DOCX skip via `content-visible`. PR
  builds use the existing sticky-comment workflow rather than building
  PR-aware HTML banners.
- **JOSS first**, methods/commentary paper later if the pattern gets
  adopted across project types beyond manuscripts.
- **Co-author the manubot team** explicitly. This is collaboration,
  not displacement, and Anthony Gitter literally opened the integration
  issue at Sean's prompting.

## Open questions left for follow-up

- Final name. `quartobot` is sticky and signals lineage; the manubot
  team may prefer something neutral like `quarto-manubot-pattern`.
- Whether the v1 template should *extend* or *fork* Quarto's first-party
  Quarto Manuscripts template. Probably extend, to inherit upstream
  improvements.
- Whether to ship a separate Python CLI, or whether
  `pandoc-manubot-cite` declared as a Quarto filter is sufficient on
  its own.
- Cache file naming and location. Manubot uses `output/`; Quarto uses
  `_freeze/`. Pick one and document.
- Graceful degradation when a resolver call fails mid-build (Crossref
  hiccup, PubMed rate limit, network out). The build should warn-and-skip
  rather than fail.
- Second template variant for Quarto **books** is plausible v2 work.
  Pattern is identical, only the project type differs.

## Things explicitly ruled out

- Building a new citation resolver from scratch. `pandoc-manubot-cite`
  exists, works, and is maintained.
- Replacing manubot or competing with it. Adoption framing only.
- A reference-management UI. Out of scope; CiteDrive and Zotero exist.
- Templates for every Quarto project type before the manuscript template
  has real users. Sketch the generality, ship one concrete artifact,
  expand on demand.
- Self-hosting the rendered output. GitHub Pages is good enough and free.

## What changed our minds during the session

The biggest update: we had assumed building a citation auto-resolver
would be the headline contribution. The web search turned up
`pandoc-manubot-cite` already inside `manubot`, fully shipped, and the
issue from Anthony asking exactly for the Quarto integration we were
sketching. That collapsed the package side of the work and made the
template / pattern side the actual contribution. Lower technical risk,
higher social legitimacy, and the manubot maintainer has already
explicitly invited it.

---

## Follow-up — 2026-05-13 (scope clarification)

A second working session surfaced an important framing correction:

**"Manubot equivalent" undersells the scope.** Manubot is explicitly manuscript-centric. Quarto is not — it covers websites, posters, books, slides, dashboards, courseware. The quartobot value proposition is bringing manubot's versioning + citation management to *all of these*, not just to manuscripts. The manuscript template is the concrete v1 deliverable, but the scope claim in the JOSS paper should be the full Quarto publishing surface.

This matters for the JOSS framing: the "statement of need" can open with Quarto's breadth, note that the manubot pattern exists only for a narrow manuscript workflow, and claim the broader surface as the contribution. Reviewers unfamiliar with Quarto will need that framing to understand why this isn't just "manubot + Quarto = done."

The Venice hackathon manuscript (already live, already getting community PRs) is the worked example in the paper — it demonstrates the CI / permalink / versioning half on a real multi-author document.
