# quarto-manubot-cite

A Quarto extension that wires `pandoc-manubot-cite` into any Quarto
project, so authors can cite by persistent identifier
(`@doi:10.1371/journal.pcbi.1007128`, `@pmid:31479462`, `@arxiv:2104.10729`,
`@isbn:9780262035613`, bare DOIs, and the rest of manubot's vocabulary)
and have entries auto-resolved into the bibliography on next build.

This is a thin wrapper. The resolver itself is
[manubot](https://github.com/manubot/manubot)'s — we don't reimplement it.

## Prerequisites

- Quarto ≥ 1.4
- `pandoc-manubot-cite` on `PATH`. Install with:
  ```bash
  pip install manubot
  ```
  Manubot ships the filter as an entry point; once installed, the binary
  is discoverable by pandoc.

## Install

```bash
quarto add seandavi/quartobot
```

(While the extension lives in the parent `quartobot` repo, that's the
install path. It will move to `seandavi/quarto-manubot-cite` after the
first tagged release. See [#13](https://github.com/seandavi/quartobot/issues/13).)

## Use

Add the filter to your `_quarto.yml`:

```yaml
filters:
  - quarto-manubot-cite

# Where pandoc-manubot-cite writes the resolved CSL JSON.
manubot-output-bibliography: references.json

# Where the bibliography cache lives.
manubot-bibliography-cache: _freeze/manubot-cache.json

# Don't fail the render on a single unresolved citation — warn and continue.
manubot-fail-on-errors: false

# Both files are merged at render time. Hand-curated entries live in
# references.bib; auto-resolved entries land in references.json.
bibliography:
  - references.bib
  - references.json
```

Then cite in your `.qmd`:

```markdown
The manubot pattern is described in @doi:10.1371/journal.pcbi.1007128.
A related approach using URL keys appears in @pmid:31479462.
The Quarto book covers cross-format publishing [@quarto2024].
```

On render, `pandoc-manubot-cite` resolves each persistent-identifier key
against the relevant API (Crossref, NCBI, arXiv, Wikidata, etc.), writes
the resulting CSL JSON entries to `references.json`, and caches the
metadata at `_freeze/manubot-cache.json` so subsequent renders don't
re-fetch.

## Citation key vocabulary

The full table from manubot, for quick reference:

| Prefix | Source | Example |
|---|---|---|
| `@doi:` | Crossref / DataCite | `@doi:10.1371/journal.pcbi.1007128` |
| `@pmid:` | NCBI PubMed | `@pmid:31479462` |
| `@pmcid:` | NCBI PubMed Central | `@pmcid:PMC6735409` |
| `@arxiv:` | arXiv | `@arxiv:2104.10729` |
| `@isbn:` | Books (multiple resolvers) | `@isbn:9780262035613` |
| `@url:` | Web pages | `@url:https://manubot.org` |
| `@wikidata:` | Wikidata | `@wikidata:Q56458094` |
| `@zotero:` | Zotero web items | `@zotero:https://www.zotero.org/groups/.../items/ABCD1234` |
| bare DOI | DOI prefix-inferred | `@10.1371/journal.pcbi.1007128` |

See manubot's
[`pandoc-manubot-cite` reference](https://manubot.github.io/manubot/reference/manubot/pandoc/cite_filter/)
for the authoritative behavior, including normalization rules and prefix
inference.

## How the two bibliographies interact

Declaring both `references.bib` (hand-curated) and `references.json`
(auto-resolved) under `bibliography:` lets pandoc citeproc merge them.
Hand-curated entries you author with stable BibTeX keys (`@quarto2024`,
`@himmelstein2019`) sit alongside the auto-resolved DOI/PMID entries.

Precedence and dedup semantics are tracked in
[#10](https://github.com/seandavi/quartobot/issues/10) — the practical
guidance is to use auto-resolved keys (`@doi:…`) by default and reach for
hand-curated entries only when you need to override metadata the
resolver got wrong.

## Configuration reference

These metadata keys are read by `pandoc-manubot-cite` from your document
or `_quarto.yml`. Defaults shown are manubot's, not ours:

- `manubot-output-bibliography` — path to write the resolved CSL JSON.
- `manubot-bibliography-cache` — path to the persistent cache (read at
  startup, written incrementally as citations resolve).
- `manubot-fail-on-errors` — `false` by default. Set to `true` to make
  unresolved citations fail the render.
- `manubot-infer-citekey-prefixes` — `true` by default. Lets you write
  bare `@10.1371/...` instead of `@doi:10.1371/...`.
- `manubot-requests-cache-path` — path for the HTTP request cache
  (separate from the bibliography cache).
- `manubot-log-level` — `WARNING` by default.

See [manubot's reference](https://manubot.github.io/manubot/reference/manubot/pandoc/cite_filter/)
for the full list.

## Failure mode

By default, `pandoc-manubot-cite` warns on unresolved citations and exits
0 — your render continues with the unresolved citation key intact in the
output. That's deliberate: a Crossref or PubMed hiccup shouldn't fail
your build. Set `manubot-fail-on-errors: true` in CI if you want the
opposite.

## See also

- [manubot](https://github.com/manubot/manubot) — the upstream package.
- [Himmelstein et al. 2019](https://doi.org/10.1371/journal.pcbi.1007128) —
  the foundational manubot paper. Cite it if you use this extension.
- The [quartobot DESIGN doc](../../../DESIGN.md) — pattern-level decisions.

## License

[MIT](../../../LICENSE).
