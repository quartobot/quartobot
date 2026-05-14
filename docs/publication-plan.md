# Publication plan

## Framing

The contribution is **the pattern, not the resolver**. Citation
auto-resolution is mostly a packaging story (`manubot.cite` already
exists inside the `manubot` package); the new claim is that the
manubot manuscript-as-software pattern can be — and now is — implemented
ergonomically on top of Quarto's full publishing surface.

Frame as **adoption, not displacement**: explicit credit to manubot,
explicit citation to Himmelstein et al. 2019, explicit reference to
`manubot.cite` as the reused infrastructure.

## Co-authors (target list)

- **Sean Davis** — author / maintainer.
- **Anthony Gitter** — opened [manubot/manubot#332](https://github.com/manubot/manubot/issues/332)
  in response to conversations with Sean. Co-author on the manubot
  PLOS paper. The closest thing to "blessing" we can have.
- **Daniel Himmelstein** — first author of the manubot paper, primary
  manubot maintainer.
- One or two **Quarto / Posit** people if interest aligns — Charles
  Teague (Quarto lead), Mine Çetinkaya-Rundel (Quarto Manuscripts).
  Co-authorship signals that the bridge is built with the Quarto
  community, not against it.
- One **early adopter from outside manuscripts** if the methods-paper
  scope (books, websites) gets developed — someone running a living
  review or a continuously-revised book.

Minimum viable author list for the JOSS paper: Sean + 1–2 manubot
people. Everything beyond that is upside.

## Venue strategy

### Stage 1 — JOSS paper for the artifact

Target: [Journal of Open Source Software](https://joss.theoj.org).

- Reviews the software, not novel results.
- ~1000-word paper (`paper/paper.md`) with: statement of need, summary,
  software description, features, integration with manubot/Quarto,
  example use (Venice writeup as worked example).
- Permanent DOI via Zenodo on tagged release.
- Turnaround: weeks, not months.
- Cite manubot prominently throughout. Cite Quarto. Cite Issue #332 as
  the explicit invitation.

Sequencing: ship the package + template to PyPI / Quarto extension
registry first, get them green, then submit. JOSS reviewers will spot-check
install and example.

### Stage 2 — Methods / commentary paper for the broader pattern

Target: depending on framing —

- **F1000Research** or **Journal of Open Research Software** for a
  workflow paper: "manuscripts, books, websites — versioned scholarly
  publishing as a Quarto pattern."
- **Patterns** (Cell Press) if we have ≥2 demonstrated use cases beyond
  the manuscript template.
- **Nature Computational Science** or **Nature Methods** as a
  commentary if we want to make the broader claim about how academic
  publishing should work in the era of Quarto. Higher-risk venue.

Stage 2 is opportunistic — write it only if adoption stories from the
template start coming in.

## Sequencing (target: 4–6 weekends to JOSS submission)

1. **Weekend 1** — Pull the CI / banner / permalink pattern out of the
   Venice repo into a clean GitHub Actions workflow file living in the
   template.
2. **Weekend 2** — Build the `quartobot resolve` CLI command and its
   pre-render hook wiring. ~50–200 lines + tests + a working
   `_quarto.yml` example. Calls `manubot.cite` directly.
3. **Weekend 3** — Assemble the `quartobot-manuscript` template,
   wiring the pre-render hook + workflow + example manuscript with
   mixed `@doi:`, `@pmid:`, and hand-key citations.
4. **Weekend 4** — Polish: README, contributing guide, example
   walkthrough, tagged release. Tag co-authors on the design doc and
   the planned paper before going further.
5. **Weekend 5** — Draft `paper/paper.md` for JOSS. Cycle once with
   co-authors.
6. **Weekend 6** — Submit to JOSS via their GitHub PR flow.

## Adjacent badges (post-JOSS)

- **rOpenSci** or **PyOpenSci** software peer review — orthogonal
  badge, well-respected, slower. Worth pursuing once stable.
- **Bioconductor / EuroBioc / posit::conf talk** — visibility, not
  citation, but the audience is exactly the user base.
- **Anthropic / Quarto extension registry / awesome-quarto** lists —
  cheap and increase reach.

## What not to do

- **Don't** position as competing with manubot. The framing is "manubot's
  pattern, available to a broader ecosystem." This matters socially and
  for citation network.
- **Don't** wait for the perfect venue. JOSS exists exactly for tools
  in this category. Manubot itself is a JOSS-adjacent + PLOS Comp Bio
  publication; a JOSS DOI is enough to make this citable and
  tenure-counted.
- **Don't** ship templates for every Quarto project type before the
  manuscript template has actual users. Sketch the generality, deliver
  the concrete one, expand on demand.
- **Don't** invent a new citation key syntax. Reuse manubot's exactly,
  for compatibility and for the social story.
