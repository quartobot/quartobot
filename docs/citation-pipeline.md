# Citation pipeline: filter vs. pre-render

**Status:** Proposal, written 2026-05-14 after a live walkthrough turned
up two UX gotchas that share a single root cause. Not yet a settled
decision — the contributing convention is that design changes go through
an issue first, and this one warrants Anthony Gitter and Daniel
Himmelstein on the thread before any code moves.

## The problem, concretely

A user walking through the v0.1 minimal example today has to:

1. Apply a `sed` patch to `manubot/pandoc/util.py` to bypass a hardcoded
   pandoc version check that breaks on the pandoc 3.x bundled with
   Quarto ≥ 1.4 ([#32](https://github.com/seandavi/quartobot/issues/32)).
2. Either install manubot at the system Python, or invoke
   `uv run quarto render` instead of bare `quarto render`, because the
   Lua filter shells out to `pandoc-manubot-cite` and that binary needs
   to be on PATH at render time (no issue filed yet, but
   [[project-local-render-path]] memory captures the live finding).

Both of these are predictable consequences of one architectural choice:
we use `pandoc-manubot-cite` as a pandoc filter, declared in
`_quarto.yml`. That binary is an external-process Python filter — the
shape Quarto's own docs steer away from.

## What Quarto says

Two passages from the Quarto docs are operative here. The pre-render
script page describes the seam we're not currently using:

> The project metadata and render list will be re-computed after any
> pre-render scripts have executed, allowing them to modify this
> project data.

> Pre-render scripts can generate additional qmd files or ipynb files
> that should be rendered.

That is the "produce inputs the standard pipeline then consumes" use
case, which is what citation resolution amounts to once you stop
thinking of it as AST work.

The filter page is more pointed than I'd remembered. It recommends Lua
filters specifically because of:

> No external dependencies, High performance (no serialization or
> process execution overhead), Access to the Pandoc and Quarto
> libraries of Lua helper functions.

And it notes:

> Pandoc's built-in citation processing is implemented as a filter.

That last sentence is the important one. Citeproc is *already* the
filter for citation work; we don't have to build one or wrap one. We
have to populate the bibliography it reads. The current architecture
inserts a second filter (`pandoc-manubot-cite`) ahead of citeproc to do
network resolution mid-render. The Quarto-shaped way to do that work
is before the render starts.

Sources:
- [Project Scripts](https://quarto.org/docs/projects/scripts.html)
- [Filters](https://quarto.org/docs/extensions/filters.html)

## Proposed architecture

1. **Pre-render hook.** `_quarto.yml` declares `pre-render:` calling
   `quartobot resolve --from-scan . --output references.json`. The
   hook walks the project, calls manubot's Python API
   (`citekey_to_csl_item`) for every persistent-identifier cite key it
   finds, and writes CSL JSON with `id` set to the original key
   (`doi:10.1371/...`, not manubot's short hash). Network work happens
   here, once, before pandoc ever runs.
2. **Built-in citeproc.** The standard pandoc citation filter, already
   in every Quarto install, reads `references.json` exactly as it
   would any other bibliography file. `[@doi:10.1371/...]` in the
   prose matches the entry by `id`. No custom filter on our side.
3. **Manubot stays as a Python library dependency**, never as a CLI
   dependency. We never invoke `pandoc-manubot-cite`. We never invoke
   `pandoc` from manubot's side. The pandoc 3.x version-check code
   path is unreachable from us. PATH never matters at render time
   because `quartobot` is the only binary we need, and it runs at
   pre-render, where the project's venv is in scope.

Both gotchas dissolve. Not by patching the failing component but by
deleting it.

**Verified live, 2026-05-14.** The walkthrough at `~/Documents/quartobot-walkthrough`
was switched to this architecture and rendered four cite keys (two
DOIs, one PMID, one arXiv) through `uv run quarto render` with no
filter in the chain and no citeproc warnings. `quartobot resolve`
gained a `--id-mode citation-key` flag that writes the CSL `id` as
the user's prose key. Independently, `python -c "import
manubot.cite.citekey; assert 'manubot.pandoc.util' not in
sys.modules"` confirms the pandoc 3.x version-check module is not
even loaded under this architecture — unreachable, not merely
avoided.

The extension itself shrinks to: wire the pre-render hook into
`_quarto.yml` (so `quarto add seandavi/quartobot` is still the on-ramp),
declare the bibliography slot, and ship the version-banner include. The
Lua filter goes away. The `_extensions/seandavi/quarto-manubot-cite/`
directory may even want a rename, since we're no longer a manubot
pandoc filter — we're the quartobot pre-render wiring.

## Citation plugin architecture

The pre-render seam opens a door the filter never could. The first
instinct is to frame this as "manubot covers journal-shaped citations
(`doi:`, `pmid:`, `arxiv:`, `isbn:`, `url:`, `wikidata:`), so plugins
add the prefixes it doesn't have." That framing is wrong, and getting
it right matters both for the architecture and for the JOSS paper.

**Manubot already recognizes 1,677 prefixes.** It ships a Bioregistry-
backed CURIE handler at `manubot/cite/curie/` that covers `rrid`,
`ror`, `swh`, `geo`, `clinicaltrials`, `uniprot`, `ensembl`, `pdb`,
`ncbigene`, `ncbitaxon`, and so on. The bioregistry itself bundles
~480 KB of registry data with `uri_format` templates for each one. So
the prefix *space* isn't the gap.

The gap is depth. Here is `Handler_CURIE.get_csl_item` in full:

```python
def get_csl_item(self, citekey):
    from ..url import get_url_csl_item
    url = self.get_url(accession=citekey.standard_accession)
    return get_url_csl_item(url)
```

It constructs a landing-page URL from the `uri_format` template and
falls through to Zotero-style URL scraping. There is no domain-aware
metadata fetcher behind it. `@rrid:AB_2143816` does not get back
"Anti-CD3 antibody, BD Biosciences, RRID:AB_2143816" — it gets
whatever HTML the SciCrunch landing page happens to scrape into CSL,
which for most of these is thin or empty. Compare to manubot's seven
first-class handlers (`arxiv`, `doi`, `isbn`, `pmc`, `pubmed`, `url`,
`wikidata`), each of which hits the source's native API and knows the
quirks of that registrar (DOI content negotiation across
Crossref/DataCite/mEDRA, arXiv's versioned-ID legacy formats,
PubMed's eUtils rate limits). Those total ~1,190 lines of resolver
code and represent eight years of accumulated bug-fixes for specific
API behavior. They are the load-bearing IP of manubot, and the
project's own design line ("do not rebuild the resolver") points
directly at them.

So the CURIE space is wide but shallow. **The plugin architecture's
job is to deepen specific prefixes, not to add new ones.** A plugin
for `rrid:` hits SciCrunch's antibody/tool registry API and returns
proper CSL. A plugin for `bioc:` reads Bioconductor's `DESCRIPTION`
files and returns package metadata with authors and versions. A
plugin for `clinicaltrials:` hits the NCT API. Each one replaces the
shallow `Handler_CURIE` fallback for that specific prefix with a
real, source-aware resolver. The prefixes manubot has already chosen
to handle deeply (the seven first-class ones) stay with manubot — we
defer to its Python API for them, no exceptions.

The dispatch order at pre-render time:

1. **Plugin registry** — third-party resolver registered for this
   prefix? Use it.
2. **Manubot's seven deep handlers** — built-in to manubot, called
   via `citekey_to_csl_item`.
3. **Manubot's CURIE fallback** — generic landing-page scrape for any
   bioregistry prefix we don't have a plugin for. Thin, but better
   than nothing.

The interface a plugin implements is the same shape manubot already
uses internally — a `Handler`-equivalent ABC with `inspect`,
`standard_prefix`, and `get_csl_item`. Registered via Python entry
points (`[project.entry-points.'quartobot.resolvers']`) so
`pip install quartobot-rrid` makes the prefix deep without any
quartobot-side change. Plugin discovery happens once at pre-render
time; the rendered document never knows which resolver produced
which entry.

Two design questions need answers before any plugin ships:

1. **Which plugins are quartobot-blessed vs. community.** I'd start
   with all of them as community plugins and only bless ones that
   prove durable. Life-sciences-shaped plugins (`rrid:`, `bioc:`,
   `swhid:`, `clinicaltrials:`) are the most obvious first batch
   because that's where the shallow-CURIE pain is loudest.
2. **Caching and rate-limit policy.** Plugins shouldn't each
   reinvent request caching. The quartobot-side wrapper handles the
   cache layer — plugins implement resolution, we handle persistence.
   Manubot's own caching is one-shot anyway; richer policy is a
   downstream improvement either way.

**The political framing is friendlier under this version of the
proposal than under the first one.** Manubot's `_local_handlers` is
already a list of import paths; the plugin system is the obvious
extension of that existing pattern. The interface contract is one
manubot itself could adopt upstream — make `_local_handlers`
externally extensible, and the plugin system is portable back. We
are not adding new prefixes manubot doesn't have. We are not
competing in the resolver space at all. We are riding *below*
manubot's existing dispatch with deep implementations for prefixes
manubot has explicitly chosen to handle generically. Anything that
proves durable as a quartobot plugin is a natural upstream PR.

## Tradeoffs

**In-render resolution as a fallback disappears.** Today, a user can
clone a repo and run bare `quarto render` and get a working document,
because `pandoc-manubot-cite` resolves missing entries mid-render
(slowly, with a network call, sometimes failing). The pre-render
architecture requires that `quartobot resolve` actually run. Mitigations:

- Make the pre-render hook self-installing. `quartobot init` writes
  the `pre-render:` line into `_quarto.yml`. Anyone who follows the
  template gets it for free.
- `quartobot validate` refuses stale state — if `references.json` is
  older than `paper.qmd`, fail loud.
- Document the bare-render failure mode explicitly. Today's failure
  mode is "patch a third-party package or fail mid-render with a
  KeyError"; the new failure mode would be "run `quartobot resolve`
  or get a clearly missing bibliography." The second is a better
  failure.

**Political framing for the JOSS paper and the manubot team.** The
current language ("reuse `pandoc-manubot-cite` from the manubot
package — do not rebuild the resolver") is in `CLAUDE.md` and in the
publication plan for exactly the right reason: this project's pitch
to JOSS reviewers and to Daniel Himmelstein is adoption and extension,
not displacement. The pre-render architecture keeps that framing as
long as we're clear about what we're doing and what we're not:

- We are not rebuilding the resolver. Manubot stays a dependency. Its
  Python API is the engine for all built-in prefixes.
- We are not replacing `pandoc-manubot-cite` with a clone. We're
  declining to use it as a pandoc filter, in favor of using its
  underlying library as a pre-render call. Different seam, same code
  doing the network work.
- We are riding *below* manubot's existing dispatch with deep
  resolvers for prefixes manubot has explicitly chosen to handle
  generically via its CURIE fallback. The plugin interface mirrors
  manubot's own `Handler` ABC — something manubot itself could adopt
  upstream by making `_local_handlers` externally extensible.

That's a defensible story. It is worth running past Daniel before any
code moves.

## What stays, what changes

| Component | Today | Proposed |
|---|---|---|
| `pandoc-manubot-cite` as filter | Required at render time | Not used |
| Manubot Python library | Required | Required (unchanged) |
| `_quarto.yml` `filters:` entry | `quarto-manubot-cite` Lua bridge | Not present |
| `_quarto.yml` `pre-render:` entry | Not present | `quartobot resolve …` |
| `quartobot resolve` | Optional pre-render acceleration | Required, canonical |
| `quartobot validate` | Project shape checks | Adds staleness check |
| `quartobot init` | Writes filter line | Writes pre-render line |
| pandoc 3.x patch ([#32]) | Required workaround in CI and locally | Unreachable, can delete |
| PATH for `pandoc-manubot-cite` | Required at render time | Irrelevant |
| `_extensions/seandavi/quarto-manubot-cite/` | Lua filter bridge | Pre-render wiring (maybe renamed) |

[#32]: https://github.com/seandavi/quartobot/issues/32

## Sequencing — v0.1 vs. v0.2

Two reasonable answers:

**Hold for v0.2.** Ship v0.1 on the current filter architecture (the
sed patch works, the CLI ships, the JOSS paper can be drafted around
what exists). Open a v0.2 design issue with this doc as the
seed. Get Gitter/Himmelstein input before any code moves. The cost
is leaving the two gotchas in place through v0.1's lifetime —
unpleasant but survivable, since `quartobot doctor` (the parallel
proposal) can paper over both for now.

**Pivot now, before v0.1 tags.** v0.1 hasn't tagged yet. Once we tag,
the filter architecture is what early users adopt and we own the
migration burden. Pivoting before the tag means v0.1 ships the
healthier architecture and the JOSS paper describes what we actually
recommend, not a transitional state.

I lean toward the second, conditional on Daniel's reaction not being
"please don't." The work isn't large — `quartobot resolve` already
exists and already does most of what the pre-render hook needs to do.
The extension's filter wiring is small enough that ripping it out and
replacing it with a pre-render declaration is a few hours of work, not
a sprint. The risk isn't engineering effort, it's social: getting the
framing right with the manubot team before we publish anything that
reads as a replacement.

## Open questions

- **Prefix canonicalization vs. prose fidelity.** Manubot canonicalizes
  some prefixes (`pmid:` → `pubmed:`). The current `--id-mode citation-key`
  implementation prefers the user's input key over manubot's canonical
  form, because the prose is what citeproc will look for. Edge: if the
  same document uses both `pmid:X` and `pubmed:X`, we'd want either
  two CSL entries (one per prose form) or an explicit alias mechanism.
  Surfaced 2026-05-14 in the live trial; minimal-impact in practice
  but worth a designed answer.
- **References.bib merge story.** The minimal example pairs
  `references.json` (auto-resolved) with `references.bib` (hand-
  curated). Pandoc happily reads both in `bibliography:`, so this is
  more a docs question than a code one — but worth thinking through
  for v0.1 (idempotency of `quartobot resolve` against a project that
  already has a `.bib`, behavior of `quartobot validate` when both
  exist, etc.).
- **Migration for existing v0.1 adopters** (the Venice hackathon
  manuscript runs the current pattern). If we pivot, what does the
  upgrade path look like — a `quartobot migrate` command, a README
  walkthrough, or both?
- **Plugin discovery mechanism.** Python entry points is the obvious
  answer for Python plugins; the harder question is whether a
  plugin could be a separate Quarto extension instead, so non-Python
  users can write them.
- **What `quarto add seandavi/quartobot` does in the new world.** If
  the extension shrinks to a pre-render wiring + a bibliography slot
  declaration, is it still a Quarto extension, or is it really a
  Python package with a one-line `_quarto.yml` snippet to copy in?
  Affects the install story.
- **Where the plugin registry lives.** A `quartobot-plugins`
  monorepo, a curated `awesome-quartobot` list, or the bare PyPI
  prefix-matching convention? Each has different governance
  implications.
- **JOSS framing of the plugin architecture.** The paper is ~1000
  words. Plugins might warrant a paragraph; they might warrant a
  sentence. Depends on whether any plugins ship by paper-submission
  time.
