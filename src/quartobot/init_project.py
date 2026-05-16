"""Scaffold the quartobot pattern into an existing Quarto project.

`quartobot init` writes the files that make a vanilla Quarto project
adopt the quartobot pattern: a `_quarto.yml` wired with the
`quartobot resolve` pre-render hook, a seed `references.bib`, the
version-banner HTML template, a `.gitignore` augment, and a ten-line
GitHub Actions workflow that calls the upstream reusable workflow.

Conservative by default:

- Files that already exist are NEVER overwritten. `init` skips them and
  reports what it skipped.
- `_quarto.yml` is the one file where partial overlap is likely — for
  that path, if the file exists, init prints a YAML snippet the user
  should merge in manually.
- `.gitignore` gets new lines appended (idempotent).

The flow is intentionally pre-`usethis`: no interactive prompts, no
auto-merge. Once the CLI matures we can add `--force` for overwrites
and a `quartobot use-<thing>` family for piecewise scaffolding.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

# ---------------------------------------------------------------- templates


_QUARTO_YML_MANUSCRIPT = """\
project:
  type: default
  # Resolves @doi:, @pmid:, @arxiv:, @isbn:, @url:, @wikidata:, @pmcid:,
  # and bare DOIs before pandoc runs. The resolved CSL JSON lands in
  # references.json (gitignored — regenerated each render) and pandoc
  # citeproc reads it alongside hand-curated entries in references.bib.
  pre-render: quartobot resolve --from-scan . --output references.json --id-mode citation-key

bibliography:
  - references.bib
  - references.json

format:
  html:
    toc: true
    embed-resources: true
    include-before-body:
      - _version-banner.html
  pdf:
    documentclass: article
    keep-tex: true
"""

_QUARTO_YML_BOOK = """\
project:
  type: book
  # See the manuscript template for what the pre-render hook does.
  pre-render: quartobot resolve --from-scan . --output references.json --id-mode citation-key

book:
  title: "My quartobot book"
  author: "Your Name"
  date: today
  chapters:
    - index.qmd
  search: true
  page-navigation: true

bibliography:
  - references.bib
  - references.json

format:
  html:
    theme: cosmo
    toc: true
    include-before-body:
      - _version-banner.html
"""

_REFERENCES_BIB = """\
% Hand-curated entries live here. Auto-resolved entries written by
% `quartobot resolve` land in references.json (regenerated each render,
% ignored by git).
"""

# Embedded HTML banners. Lines are long because CSS is inlined for
# users who want to drop the file into a fresh project without
# wrangling a separate stylesheet. Lint exceptions tagged per-line.
# fmt: off
_VERSION_BANNER_TEMPLATE = (
    '<div class="version-banner" style="background:#fff7e0;border-bottom:2px solid #f0b400;padding:0.55rem 1rem;font-family:system-ui,-apple-system,\'Segoe UI\',sans-serif;font-size:0.92rem;text-align:center;color:#3a2c00;">\n'  # noqa: E501
    "  <strong>This version:</strong>\n"
    '  <a href="__VERSION_URL__" style="color:#3a2c00;text-decoration:underline;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;">__VERSION_SHA__</a>\n'  # noqa: E501
    "  &nbsp;&middot;&nbsp;\n"
    '  <a href="__VERSION_LATEST__" style="color:#3a2c00;">latest&nbsp;HTML</a>\n'
    "  &nbsp;&middot;&nbsp;\n"
    '  <a href="__VERSION_GH__" style="color:#3a2c00;">GitHub</a>\n'
    "</div>\n"
)

_VERSION_BANNER_DEV = (
    '<div class="version-banner" style="background:#eef2ff;border-bottom:2px solid #6366f1;padding:0.55rem 1rem;font-family:system-ui,-apple-system,\'Segoe UI\',sans-serif;font-size:0.92rem;text-align:center;color:#1e1b4b;">\n'  # noqa: E501
    "  <strong>Development build</strong> &middot; permalink set by CI on push to <code>main</code>\n"  # noqa: E501
    "</div>\n"
)
# fmt: on


def _render_workflow(project_type: str) -> str:
    """Return the ten-line workflow caller for the given project type."""
    return f"""\
# Renders on every push and PR via the upstream reusable workflow.
# Override inputs in the `with:` block below; see
#   https://github.com/quartobot/quartobot/blob/main/.github/workflows/render-reusable.yml
# for the full list.

name: Render

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

jobs:
  render:
    uses: quartobot/quartobot/.github/workflows/render-reusable.yml@main
    permissions:
      contents: write
      pull-requests: write
    with:
      project-type: {project_type}
"""


_PR_CLOSED_WORKFLOW = """\
name: Clean up PR preview

on:
  pull_request:
    types: [closed]

permissions:
  contents: write

concurrency:
  group: gh-pages-deploy
  cancel-in-progress: false

jobs:
  cleanup:
    runs-on: ubuntu-latest
    if: github.event.pull_request.head.repo.full_name == github.repository
    steps:
      - name: Check whether gh-pages branch exists
        id: branch
        run: |
          if git ls-remote --exit-code --heads origin gh-pages >/dev/null 2>&1; then
            echo "exists=true" >> "$GITHUB_OUTPUT"
          else
            echo "exists=false" >> "$GITHUB_OUTPUT"
          fi

      - name: Check out gh-pages
        if: steps.branch.outputs.exists == 'true'
        uses: actions/checkout@v4
        with:
          ref: gh-pages
          fetch-depth: 1

      - name: Remove PR preview directory
        if: steps.branch.outputs.exists == 'true'
        run: |
          pr="${{ github.event.pull_request.number }}"
          [ -d "pr/${pr}" ] && rm -rf "pr/${pr}" || exit 0

      - name: Commit and push
        if: steps.branch.outputs.exists == 'true'
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add -A
          if git diff --cached --quiet; then exit 0; fi
          git commit -m "Clean up preview for PR #${{ github.event.pull_request.number }}"
          git push
"""


_GITIGNORE_LINES = [
    "# quartobot",
    "_book/",
    "_freeze/",
    ".quarto/",
    "references.json",
    "*_files/",
    "**/*.quarto_ipynb",
]


# ---------------------------------------------------------------- outcome types


ActionStatus = Literal["written", "skipped-exists", "appended", "manual-merge"]


@dataclass(frozen=True)
class Action:
    """One file write (or non-write) the init flow attempted."""

    path: Path
    status: ActionStatus
    detail: str | None = None


@dataclass
class InitOutcome:
    """The aggregate result of an init run."""

    actions: list[Action] = field(default_factory=list)
    project_type: str = "manuscript"
    manual_merge_snippet: str | None = None


# ---------------------------------------------------------------- helpers


def detect_project_type(project: Path) -> str:
    """Read `_quarto.yml`; return `"manuscript"`, `"book"`, or `"unknown"`.

    A missing or unparsable `_quarto.yml` returns `"unknown"` — init
    treats that as the manuscript default.
    """
    yml = project / "_quarto.yml"
    if not yml.exists():
        return "unknown"
    try:
        loaded = yaml.safe_load(yml.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return "unknown"
    if not isinstance(loaded, dict):
        return "unknown"
    proj = loaded.get("project")
    if isinstance(proj, dict) and proj.get("type") == "book":
        return "book"
    return "manuscript"


def _write_if_missing(path: Path, content: str) -> Action:
    if path.exists():
        return Action(path=path, status="skipped-exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return Action(path=path, status="written")


def _ensure_gitignore(project: Path) -> Action:
    """Append missing lines to `.gitignore`. Idempotent."""
    gi = project / ".gitignore"
    existing = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
    existing_set = set(existing)
    to_add = [line for line in _GITIGNORE_LINES if line not in existing_set]
    if not to_add:
        return Action(path=gi, status="skipped-exists", detail="all lines present")
    if existing and existing[-1] != "":
        existing.append("")  # leading blank separator
    new_lines = existing + to_add + [""]
    gi.write_text("\n".join(new_lines), encoding="utf-8")
    return Action(
        path=gi,
        status="appended",
        detail=f"added {len(to_add)} line(s)",
    )


# ---------------------------------------------------------------- top-level


def init_project(
    project: Path,
    *,
    project_type: str = "auto",
) -> InitOutcome:
    """Scaffold quartobot files into `project`.

    Args:
        project: Path to an existing Quarto project root (or empty dir).
        project_type: `"auto"` (detect from existing `_quarto.yml`),
            `"manuscript"`, or `"book"`. `"auto"` defaults to
            `"manuscript"` when there's nothing to detect from.

    Returns:
        `InitOutcome` describing each file action.
    """
    if project_type == "auto":
        detected = detect_project_type(project)
        ptype = detected if detected != "unknown" else "manuscript"
    else:
        ptype = project_type

    outcome = InitOutcome(project_type=ptype)

    # _quarto.yml — never overwrite. If absent, write the appropriate
    # default. If present, print a snippet for manual merge.
    yml_path = project / "_quarto.yml"
    if yml_path.exists():
        outcome.actions.append(
            Action(
                path=yml_path,
                status="manual-merge",
                detail="merge the pre-render block manually",
            )
        )
        outcome.manual_merge_snippet = _quarto_yml_snippet_for_manual_merge()
    else:
        content = _QUARTO_YML_BOOK if ptype == "book" else _QUARTO_YML_MANUSCRIPT
        outcome.actions.append(_write_if_missing(yml_path, content))

    # Other files — write only if missing.
    outcome.actions.append(_write_if_missing(project / "references.bib", _REFERENCES_BIB))
    outcome.actions.append(
        _write_if_missing(
            project / "_version-banner.html.template",
            _VERSION_BANNER_TEMPLATE,
        )
    )
    outcome.actions.append(_write_if_missing(project / "_version-banner.html", _VERSION_BANNER_DEV))
    outcome.actions.append(
        _write_if_missing(
            project / ".github" / "workflows" / "render.yml",
            _render_workflow(ptype),
        )
    )
    outcome.actions.append(
        _write_if_missing(
            project / ".github" / "workflows" / "pr-closed.yml",
            _PR_CLOSED_WORKFLOW,
        )
    )

    # .gitignore is the only file where we modify-in-place.
    outcome.actions.append(_ensure_gitignore(project))

    return outcome


def _quarto_yml_snippet_for_manual_merge() -> str:
    """Return the YAML lines to add to an existing `_quarto.yml`."""
    return """\
# Add to your existing _quarto.yml. The pre-render line goes under
# `project:` next to your existing `type:` value.

project:
  pre-render: quartobot resolve --from-scan . --output references.json --id-mode citation-key

bibliography:
  - references.bib
  - references.json

format:
  html:
    include-before-body:
      - _version-banner.html
"""


def format_outcome(outcome: InitOutcome, *, project: Path) -> str:
    """Pretty-print an InitOutcome."""
    glyphs = {
        "written": "+",
        "appended": "~",
        "skipped-exists": "·",
        "manual-merge": "!",
    }
    lines: list[str] = []
    lines.append(f"Project type: {outcome.project_type}")
    lines.append("")
    for action in outcome.actions:
        try:
            relative = action.path.relative_to(project)
        except ValueError:
            relative = action.path
        glyph = glyphs.get(action.status, "?")
        line = f"  {glyph} {relative}  [{action.status}]"
        if action.detail:
            line += f" — {action.detail}"
        lines.append(line)
    lines.append("")
    if outcome.manual_merge_snippet:
        lines.append(outcome.manual_merge_snippet)
    lines.append("Next steps:")
    lines.append("  1. Confirm `quartobot` is on PATH: `quartobot --version`")
    lines.append("     (install with `uv tool install git+https://github.com/quartobot/quartobot`)")
    lines.append("  2. Add citations to your prose: @doi:..., @pmid:..., etc.")
    lines.append("  3. quarto render")
    return "\n".join(lines)


__all__: Sequence[str] = (
    "Action",
    "InitOutcome",
    "detect_project_type",
    "format_outcome",
    "init_project",
)
