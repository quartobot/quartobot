---
title: Getting started
description: Three paths from zero to a quartobot project.
---

## Three paths in

Pick the one that matches where you are.

### I'm starting a new manuscript

```bash
uv tool install quartobot
quarto create project manuscript my-paper
cd my-paper
quartobot init
```

Optional: `quartobot use github-ci` to scaffold the GitHub Actions
render workflow + version banner + permalink CI.

`quarto create project` lays out a manuscript-shaped Quarto project
(`index.qmd`, `_quarto.yml`, the directory layout pandoc expects);
`quartobot init` layers the citation-resolution pre-render hook and a
seed `references.bib` on top. `use github-ci` is the opt-in
manuscript-as-software CI on top of that.

Same pattern for books and websites — substitute `book` or `website`
for `manuscript` in the `quarto create` line.

### I have an existing Quarto project

```bash
uv tool install quartobot
quartobot init
git add . && git commit -m "Adopt the quartobot citation pipeline"
git push
```

`quartobot init` wires the `quartobot resolve` pre-render hook into
`_quarto.yml`, declares `references.bib` + `references.json` under
`bibliography:`, and seeds an empty `references.bib`. Three files,
idempotent — run it again and nothing breaks. For the GitHub Actions
render workflow + version banner, follow up with
`quartobot use github-ci`.

### I just want auto-resolved citations

```bash
uv tool install quartobot
```

Then in your `_quarto.yml`:

```yaml
project:
  pre-render: quartobot resolve --from-scan . --output references.json --id-mode citation-key

bibliography:
  - references.bib
  - references.json
```

And in your prose:

```markdown
The pattern is described in @doi:10.1371/journal.pcbi.1007128.
```

That's the minimum. No filter, no `quarto add`, no extension. The hook
runs before pandoc on every render; pandoc-citeproc reads
`references.json` and `references.bib` together.

## Prerequisites

- **Quarto ≥ 1.4** — `quarto --version`. [Install](https://quarto.org/docs/get-started/).
- **Python ≥ 3.10** — for the `quartobot` CLI. `uv tool install` handles this for you if you don't have Python.
- **A GitHub repo** — for the CI / Pages parts. The pre-render hook
  works without a GitHub repo or CI; first render needs network for
  Crossref/PubMed/etc., subsequent renders skip the network call when
  `references.json` already has the entry.

## See also

- [First manuscript (15 min)](../first-manuscript/) — the same flow as a guided end-to-end walk-through if you'd rather follow one path than pick between three.
- [Install reference](../install/) — every install method, when to use which.
- [CLI reference](../cli/) — including the `quartobot resolve` pre-render hook.
