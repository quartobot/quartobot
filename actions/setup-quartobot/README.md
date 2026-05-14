# setup-quartobot

Composite action: installs everything needed to render a Quarto project
using the manubot citation pattern.

```yaml
- uses: actions/checkout@v4
- uses: seandavi/quartobot/actions/setup-quartobot@v0.1
  with:
    project: "."          # where _quarto.yml lives (default: .)
    python-version: "3.12"
    manubot-spec: "manubot>=0.6,<0.7"
    quarto-version: ""    # empty = latest stable
    tinytex: "true"       # set "false" to skip TeX install
```

## What it does

1. `actions/setup-python@v5` with pip cache.
2. `pip install '<manubot-spec>'` — installs `pandoc-manubot-cite` on `PATH`.
3. `quarto-dev/quarto-actions/setup@v2` with TinyTeX by default.
4. `quarto add <extension-source>` inside `<project>` — installs the
   `quarto-manubot-cite` filter extension.

## When to skip TinyTeX

If you render HTML only and want a faster CI job, set `tinytex: "false"`.
TinyTeX is required for PDF rendering and adds ~30 seconds to the job.

## Pinning

For reproducible CI, pin everything explicitly:

```yaml
with:
  python-version: "3.12"
  manubot-spec: "manubot==0.6.1"
  quarto-version: "1.5.57"
  extension-source: "seandavi/quartobot@v0.1"
```

## See also

- [`render-manuscript`](../render-manuscript/) — the matching render step.
- [Extension documentation](https://github.com/seandavi/quartobot/tree/main/_extensions/seandavi/quarto-manubot-cite).
