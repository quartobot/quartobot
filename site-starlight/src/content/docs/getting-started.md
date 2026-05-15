---
title: Getting started
description: Three paths from zero to a quartobot project.
---

:::note
quartobot is pre-v0.1. Install today is via the git URL below;
PyPI publishing follows the v0.1 tag. Track progress on the
[v0.1 milestone](https://github.com/seandavi/quartobot/milestone/1).
:::

## Three paths in

Pick the one that matches where you are.

### I'm starting a new manuscript

```bash
gh repo create my-paper --template seandavi/quartobot-manuscript
cd my-paper
git push
```

CI takes care of rendering and deploying. Open the Pages URL from
your repo settings.

### I have an existing Quarto project

```bash
uv tool install git+https://github.com/seandavi/quartobot
quartobot init
git add . && git commit -m "Adopt the quartobot pattern"
git push
```

`quartobot init` wires the `quartobot resolve` pre-render hook into
`_quarto.yml`, seeds a `references.bib`, drops in the version banner
template, and writes a ten-line `render.yml` that calls the upstream
reusable workflow. Idempotent — run it again and nothing breaks.

### I just want auto-resolved citations

```bash
uv tool install git+https://github.com/seandavi/quartobot
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
- **Python ≥ 3.10** — for the `quartobot` CLI.
- **A GitHub repo** — for the CI / Pages parts. The pre-render hook
  works without a GitHub repo or CI; first render needs network for
  Crossref/PubMed/etc., subsequent renders skip the network call when
  `references.json` already has the entry.

## See also

- [Install reference](/install/) — every install method, when to use which
- [CLI reference](/cli/) — including the `quartobot resolve` pre-render hook
- [Template walkthrough](/template/)
