---
title: "Tutorial: your first manuscript in 15 minutes"
description: End-to-end — from an empty directory to a rendered manuscript with resolved citations and a per-commit permalink on GitHub Pages.
---

This tutorial walks one path. By the end you will have a Quarto
manuscript with citations resolved automatically from DOIs and
PubMed IDs, rendering itself on every push, deployed to GitHub Pages
with a `/v/<commit-sha>/` immutable permalink for each commit.

Budget: 15 minutes if you have Quarto, `uv`, and `gh` already on
your machine. First render takes longer because Quarto installs
TinyTeX the first time it sees a PDF format. After that, every
render is fast.

You will not learn *why* the design choices are this way — that's
the [Design](../design/) and
[Citation pipeline](https://github.com/quartobot/quartobot/blob/main/docs/citation-pipeline.md)
pages' job. This tutorial is doing, not understanding.

## Before you start

You need:

- **Quarto ≥ 1.4** — `quarto --version`. [Install Quarto](https://quarto.org/docs/get-started/) if needed.
- **`uv`** — `uv --version`. [Install uv](https://docs.astral.sh/uv/getting-started/installation/) if needed; it handles the Python install for you transparently.
- **`gh`** (the GitHub CLI) — `gh --version`. [Install gh](https://cli.github.com/) if needed.
- **A GitHub account** authenticated with `gh auth login`.

That's it. No separate Python install, no manubot install, no
Quarto extensions to add.

## 1. Install quartobot

```bash
uv tool install quartobot
```

This puts `quartobot` on your user `PATH` so Quarto's pre-render
subprocess can find it without venv activation. Confirm:

```bash
quartobot --version
```

You should see `quartobot, version 0.2.0` (or later).

## 2. Create the project

Use Quarto's own scaffolder for the project shape:

```bash
quarto create project manuscript my-paper
cd my-paper
```

Quarto writes a manuscript-shaped directory: an `index.qmd`, a
`_quarto.yml`, and the layout pandoc expects for a single-document
manuscript.

## 3. Wire in citation resolution

Layer the citation pipeline on top:

```bash
quartobot init
```

`init` adds three things and only three things: a pre-render hook
line in `_quarto.yml` (so `quartobot resolve` runs before pandoc on
every render), a seed `references.bib` you can hand-curate any
references that aren't on a registrar, and `.gitignore` entries for
Quarto outputs and the generated `references.json`.

That's the minimum. If all you want is citations resolved from
`@doi:` and friends, stop here.

## 4. Write a paragraph

Open `index.qmd` and replace the body with:

```markdown
The manubot pattern [@doi:10.1371/journal.pcbi.1007128] runs scholarly
manuscripts as git repositories that build themselves on every commit,
resolve citations from persistent identifiers, and hand out
immutable permalinks per commit. The GTEx Consortium's pilot analysis
[@pmid:23685459] shipped a 168-author preprint using a similar
collaborative-PR pattern; both are early examples of treating a
paper as software rather than a Word document.
```

Two cite keys, two registrars. Nothing else to configure.

## 5. Render locally

```bash
quarto render
```

First render installs TinyTeX (Quarto handles this; takes 1–2
minutes). On the second render and after, it's seconds.

The pre-render hook fires before pandoc runs. It:

1. Scans `index.qmd` for cite keys.
2. Calls each registrar (Crossref for the DOI, PubMed for the PMID)
   to resolve canonical metadata.
3. Writes the resulting CSL JSON to `references.json`.
4. Hands control back to pandoc, which reads `references.json` and
   formats the citations.

Open `_output/index.html` (or `index.pdf`). The citations show as
formatted references with author names, journal, year. No empty
`[?]` placeholders.

Re-run `quarto render`. Now it's near-instant — the pre-render hook
sees `references.json` already exists with both keys cached, skips
the network round-trip, and pandoc renders straight through.

## 6. Add the publish-on-every-commit CI

If you want every push to your GitHub repo to render the manuscript,
deploy it to GitHub Pages, embed a "this version: `<sha>`" banner in
the rendered HTML, and post a sticky preview comment on each PR —
add the second layer:

```bash
quartobot use github-ci
```

This scaffolds `.github/workflows/render.yml` (the trigger), the
PR-preview cleanup workflow, the version-banner Quarto include, and
prints a YAML snippet to merge into your `_quarto.yml` so the banner
appears in the rendered HTML.

Skip this step entirely if you already have CI you're happy with,
or if you plan to publish via `quarto publish`. The citation
pipeline from step 3 works the same either way.

Add the snippet that `quartobot use github-ci` printed to your
`_quarto.yml`. It will look roughly like:

```yaml
format:
  html:
    include-in-header:
      - _version-banner.html
```

## 7. Push to GitHub

```bash
gh repo create my-paper --source=. --public --push
```

`gh` creates the repo, pushes your commit, and gives you the URL.

The render workflow fires on push. Watch it land:

```bash
gh run watch
```

When the workflow finishes, GitHub Pages serves your manuscript at
`https://<your-handle>.github.io/my-paper/`. Every commit also
deploys to a versioned subdirectory: `https://<your-handle>.github.io/my-paper/v/<sha>/index.html`.
The version banner in the rendered HTML links you between them.

## 8. Open a pull request

Make a change. Push to a branch. Open a PR.

```bash
git checkout -b add-context
# edit index.qmd, add another sentence with another citation
git add index.qmd
git commit -m "Add context paragraph"
git push -u origin add-context
gh pr create --fill
```

Within a couple of minutes a sticky comment lands on the PR with a
link to a preview render. Reviewers see exactly what your branch
renders to without checking it out locally.

When you merge the PR, `quartobot use github-ci`'s cleanup workflow
removes the preview directory from gh-pages; the merge commit gets
its own `/v/<sha>/` permalink alongside the latest.

## You now have

- A manuscript that builds itself on every push.
- Citations resolved from registrars at render time, cached so CI
  never sees a network blip mid-render.
- An immutable `/v/<sha>/` URL for every commit anyone can cite.
- PR previews via sticky comment.
- A version banner in the rendered HTML pointing at "this version"
  and "the latest version" of the paper.

## Where to next

- [CLI reference](../cli/) — every command, every flag.
- [MCP server](../mcp/) — wire `quartobot resolve_citation` into
  Claude Desktop, Codex, or Gemini Code Assist so an agent can
  resolve citations while you draft.
- [Migrating from manubot](../migrating-from-manubot/) — if you have
  a manubot manuscript and want to translate the layout.
- [Design](../design/) — the architecture decisions and prior art.
