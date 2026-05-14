# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## quartobot

Manubot's manuscript-as-software pattern, implemented natively for the Quarto ecosystem.

**Status:** Design phase, Phase-1 scaffold in flight. Architecture decisions live in `DESIGN.md`; the roadmap is the open issues. Do not invent files into the scaffold directories below without an explicit task — the layout is the intent, not necessarily the current state.

## Directory layout

- `_extensions/seandavi/quarto-manubot-cite/` — the Quarto filter extension. `_extensions/` lives at the repo root because `quarto add seandavi/quartobot` expects it there. May eventually split to its own repo (`seandavi/quarto-manubot-cite`); for now ships from this one.
- `template/` — the `quartobot-manuscript` GitHub template (Quarto Manuscripts project + extension wiring + `.github/workflows/render.yml` for permalinks, banners, and PR previews). Will eventually be promoted to a standalone template repo.
- `examples/extension-minimal/` — smallest end-to-end demo of the extension on its own, without the template's CI/banner machinery.
- `paper/` — eventual home for `paper.md`, the JOSS submission (~1000 words). Voice guide for this file lives in the "JOSS paper specifically" section below.
- `docs/` — prior art, publication plan, conversation notes. Read these before making non-trivial design changes.

Note: an earlier draft of this file said the extension lived in `src/`. That was wrong — Quarto extensions install from `_extensions/` at the repo root. The `src/` directory was removed. (A later branch reintroduces `src/` for the `quartobot` Python CLI; that's a different artifact.)

## Commands

The repo now contains a Quarto extension, a manuscript template, a docs site, and (on follow-up branches) a Python CLI. What's tracked vs. what's planned:

- **Extension install:** `quarto add seandavi/quartobot` (the extension lives in the parent repo while the scaffold matures; will move to `seandavi/quarto-manubot-cite` once split — tracked at [#13](https://github.com/seandavi/quartobot/issues/13)).
- **Template adoption:** eventually `gh repo create my-paper --template seandavi/quartobot-manuscript`. The template currently lives at `template/` in this repo; promotion to its own repo is part of v0.1.
- **Render the docs site locally:** `quarto preview site/`.
- **Render the minimal example:** `cd examples/extension-minimal && quarto add ../.. --no-prompt && quarto render`.
- The Venice hackathon manuscript ([seandavi/2026-venice-spatial-hackathon-manuscript](https://github.com/seandavi/2026-venice-spatial-hackathon-manuscript)) runs the CI/permalink/banner half on a live 25-author preprint and is the reference implementation for the template's `.github/workflows/render.yml`.

## Contributing conventions

From `CONTRIBUTING.md`:

- Branches off `main`, named `<handle>/<short-description>` (e.g., `seandavi/version-banner-default`).
- No squash merges by default — preserve history with merge commits.
- CI must pass before merge (no CI exists yet; this kicks in once the template lands).
- Discuss design changes in an issue first — JOSS paper review will want the paper trail.

## What this is

Two artifacts shipping together:
1. `quarto-manubot-cite` — a thin Quarto extension wiring `pandoc-manubot-cite` (from the `manubot` Python package) into any Quarto project.
2. `quartobot-manuscript` — a GitHub template repo combining Quarto Manuscripts + the extension + CI for per-commit permalinks, version banners, and PR previews.

**Scope:** Not limited to manuscripts. Quarto covers websites, books, posters, slides, dashboards, courseware. The manubot pattern (versioned citations, immutable permalinks, collaborative PRs) applies to all of them. The manuscript template is v1; broader project types are explicit v2+ work.

## Key design decisions (already settled)

- Reuse `pandoc-manubot-cite` from the `manubot` package — do NOT rebuild the resolver.
- Bibliography: CSL JSON for auto-resolved entries + hand-curated `.bib` alongside. Both declared in `_quarto.yml`.
- Citation key syntax: manubot's exactly (`@doi:`, `@pmid:`, `@arxiv:`, `@isbn:`, `@url:`, `@wikidata:`, bare DOIs). No new syntax.
- Permalink: `/v/<full-sha>/` per manubot convention.
- Version banner: HTML-only, injected via CI `sed` into a Quarto include file. PDF/DOCX skip via `content-visible`.
- PR previews: sticky comment via `marocchino/sticky-pull-request-comment`, not HTML banners.

## Prior art

See `docs/prior-art.md`. The gap is real and documented. Key references:
- `pandoc-manubot-cite` — already ships in `pip install manubot`
- Quarto Manuscripts — first-party project type since Quarto 1.4
- [manubot/manubot#332](https://github.com/manubot/manubot/issues/332) — Anthony Gitter's 2022 integration request, opened after conversations with Sean Davis. This repo resolves it.

## Publication plan

JOSS first. See `docs/publication-plan.md`. Target co-authors: Anthony Gitter, Daniel Himmelstein, possibly Charles Teague / Mine Çetinkaya-Rundel (Posit/Quarto).

Weekend sequencing: CI template → Quarto extension → manuscript template → JOSS paper. ~4–6 weekends.

## Venice hackathon as proof of concept

[seandavi/2026-venice-spatial-hackathon-manuscript](https://github.com/seandavi/2026-venice-spatial-hackathon-manuscript) already runs the CI / permalink / banner half of the pattern on a live 25-author preprint. That's the source material for the template.

## Open questions

See `DESIGN.md#open-questions`. The biggest unresolved ones: naming (quartobot vs. quarto-manubot-pattern, [#1](https://github.com/seandavi/quartobot/issues/1)), and extend vs. fork the first-party Quarto Manuscripts template ([#3](https://github.com/seandavi/quartobot/issues/3)). The cache-file-location question is settled — `_freeze/manubot-cache.json` ([#8](https://github.com/seandavi/quartobot/issues/8)).

---

## Writing in Sean Davis's voice

All user-facing writing in this repo — README, JOSS paper, docs, release notes — should sound like Sean wrote it. This section is based on pre-AI writing samples (2016–2020 institutional strategy documents, grant cover letters, Bioconductor package documentation).

### How he actually writes

**Sentence length varies with the thought.** Some sentences are short. Others carry a full complex argument in one go, with subordinate clauses doing real work. The rhythm is not a formula — it follows what the sentence needs to say. Don't impose artificial brevity.

**Takes positions directly, without preamble.** "We must recognize that while we talk about service and support, such terminology makes an unnatural distinction between 'science' and 'support'." Not: "It is worth noting that the terminology of service and support may potentially create distinctions that could be seen as artificial."

**"That said" is a real connector.** He uses casual transitions inside formal writing. It reads as confident, not sloppy.

**Numbers and specifics are the evidence.** "There are at least 500 investigators who have used CCR high performance computing resources" — not "a large number of investigators." "~50–200 lines" not "a thin layer."

**Double negatives for emphasis.** "valuable and not-insignificant" is a real Sean construction. It acknowledges complexity without hedging.

**Idioms are used naturally.** "all things to all people," "front-and-center," "give-and-take" — he reaches for common idioms when they fit, rather than avoiding them as imprecise.

**Self-aware about clichés.** He'll say a thing, notice it sounds like a cliché, and then defend it: "That sounds trite, but it is an important point." This is more human than pretending the cliché isn't there.

**Institutional and political awareness shows through.** He writes about organizational dynamics, incentives, and trust explicitly, not as background assumptions. This is not boilerplate sensitivity — it's strategic thinking on the page.

**Formal register can drop in context.** Editorial asides, parentheticals, and direct address ("Tom, you may have noticed...") coexist with the more formal sections. Don't flatten everything to one register.

**Informational, not promotional.** Describes what something is and does. Lets methodology and specifics carry the interest. Does not pitch.

### AI patterns to strip before anything leaves this repo

**Vocabulary to delete:**
- pivotal, crucial, vital, key (as an adjective meaning "important"), groundbreaking, transformative
- showcase, highlight (verb used decoratively), underscore, emphasize (as padding)
- landscape (abstract noun), tapestry, ecosystem (when used metaphorically, not technically)
- testament, reminder, marker of
- vibrant, robust (unless measuring something), rich (figurative)
- delve, dive into, explore (as announcements)
- additionally, furthermore, moreover (as sentence openers — just start the next sentence)

**Constructions to rewrite:**
- "serves as / stands as / functions as" → use "is"
- "It's not just X, it's Y" → pick one claim and state it
- "Not only X but also Y" → rewrite as a direct statement
- "In order to" → "To"
- "Due to the fact that" → "Because"
- "At its core / fundamentally / what really matters is" → delete and say the thing
- Trailing -ing phrases that inflate without adding content: "...ensuring that researchers can collaborate effectively" → cut or make it a real sentence
- Em dash overuse — commas and periods do the job
- "challenges and future directions" as a formulaic section heading

**Structure to avoid:**
- Bold header followed immediately by a one-sentence paragraph that just restates the header
- Generic positive conclusion ("The future looks bright", "exciting times ahead", "we look forward to")
- Signposting announcements ("Let's explore", "Here's what you need to know", "Let's dive in")
- Rule of three when two would be more honest
- Any sentence that would appear unchanged in a press release

### JOSS paper specifically

The `paper/paper.md` (~1000 words) should read like a person who built the tool explaining why it exists, not like a grant reviewer summarizing it from the outside.

- Open with the gap, stated directly. One or two sentences. No wind-up.
- Describe what a user actually does: what they type, what happens.
- Cite manubot prominently. Frame this as adoption and extension, not competition.
- The Venice hackathon manuscript is the worked example — name it, link it, say it's a real 25-author preprint with the CI pattern already running. Specifics over vague claims.
- End on what's available now, not a vision statement.

### Voice check

Read the draft aloud. If any sentence sounds like it belongs in a NIH program announcement or a startup pitch deck, rewrite it. The test: would Sean say this in a talk slide note or a direct email? If not, it's not his voice.
