# extension-minimal

The smallest Quarto project that exercises `quarto-manubot-cite`. Use
this if you want to try the extension on its own without adopting the
full `quartobot-manuscript` template.

## Run it

```bash
cd examples/extension-minimal/

# Once: install the extension and the resolver.
quarto add seandavi/quartobot
pip install 'manubot>=0.6,<0.7'

# Each render:
quarto render index.qmd
open index.html
```

## What you should see

- `references.json` written at the project root with one CSL JSON entry
  for the resolved DOI (`10.1371/journal.pcbi.1007128`).
- `_freeze/manubot-cache.json` written with the cached resolver response.
- The rendered HTML shows both `@doi:…` and `@quarto2024` citations
  rendered correctly in a numbered bibliography.

The second render should be ~instant — the cache covers both lookups.

## Why this isn't the template

The template (`../template/`) adds: a version banner, per-commit
permalinks via CI, PR previews, multi-format render (HTML + PDF + DOCX),
gh-pages deploy. All of that is the *pattern*. The example here is just
the *extension*.

If you want the pattern, use the template. If you want to add manubot-
style citations to an existing Quarto project, this is the shape.
