"""Scaffold the GitHub Actions render workflow + version banner.

`quartobot use github-ci` writes the manuscript-as-software machinery
that used to ride along with `quartobot init`: a ten-line
`.github/workflows/render.yml` that calls the upstream reusable
workflow, the version-banner Quarto include (template + dev
placeholder), and a PR-preview cleanup workflow.

Idempotent. Files already on disk are reported as `skipped-exists`,
not overwritten. The one place this command leaves work for the
user is `_quarto.yml`: if it exists but doesn't declare the banner
include, the command prints the snippet to merge in.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from quartobot.init_project import (
    Action,
    _write_if_missing,
    detect_project_type,
)

# ---------------------------------------------------------------- templates


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


_BANNER_INCLUDE_SNIPPET = """\
# Add to your existing _quarto.yml so the version banner renders at
# the top of the HTML output. PDF/DOCX outputs skip the include
# automatically.

format:
  html:
    include-before-body:
      - _version-banner.html
"""


# ---------------------------------------------------------------- outcome type


@dataclass
class UseOutcome:
    """The aggregate result of a `quartobot use github-ci` run."""

    actions: list[Action] = field(default_factory=list)
    project_type: str = "manuscript"
    manual_merge_snippet: str | None = None


# ---------------------------------------------------------------- helpers


def _banner_already_included(project: Path) -> bool:
    """True if `_quarto.yml` already declares the banner include.

    A loose YAML walk — anywhere `_version-banner.html` shows up under
    an `include-before-body` (or `include-in-header`) list counts. If
    the file is missing or unparsable, returns False so the snippet
    still gets printed (or, when `_quarto.yml` is absent, suppressed
    by the caller).
    """
    yml = project / "_quarto.yml"
    if not yml.exists():
        return False
    try:
        loaded = yaml.safe_load(yml.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return False
    if not isinstance(loaded, dict):
        return False

    def _walk(node: object) -> bool:
        if isinstance(node, dict):
            return any(_walk(v) for v in node.values())
        if isinstance(node, list):
            return any(_walk(item) for item in node)
        if isinstance(node, str):
            return "_version-banner.html" in node
        return False

    return _walk(loaded)


# ---------------------------------------------------------------- top-level


def apply_github_ci(
    project: Path,
    project_type: str = "auto",
) -> UseOutcome:
    """Scaffold the GitHub Actions CI + version banner into `project`.

    Args:
        project: Path to an existing Quarto project root.
        project_type: `"auto"` (detect from `_quarto.yml`),
            `"manuscript"`, or `"book"`. `"auto"` defaults to
            `"manuscript"` when there's nothing to detect from.

    Returns:
        `UseOutcome` describing each file action and an optional
        manual-merge snippet for the banner include.
    """
    if project_type == "auto":
        detected = detect_project_type(project)
        ptype = detected if detected != "unknown" else "manuscript"
    else:
        ptype = project_type

    outcome = UseOutcome(project_type=ptype)

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

    # If `_quarto.yml` exists and doesn't already wire the banner
    # include, print the snippet for manual merge. If `_quarto.yml`
    # doesn't exist at all, the user hasn't run `quartobot init` yet
    # and we stay quiet on the merge front — running init first is
    # the documented path.
    yml = project / "_quarto.yml"
    if yml.exists() and not _banner_already_included(project):
        outcome.manual_merge_snippet = _BANNER_INCLUDE_SNIPPET

    return outcome


def format_outcome(outcome: UseOutcome, *, project: Path) -> str:
    """Pretty-print a UseOutcome."""
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
    lines.append("  1. Commit the new files and push to GitHub.")
    lines.append("  2. The render workflow fires on push to main and on PRs.")
    lines.append("  3. After the first push, CI swaps the dev banner for a")
    lines.append("     per-commit permalink + 'latest' link.")
    return "\n".join(lines)


__all__: Sequence[str] = (
    "UseOutcome",
    "apply_github_ci",
    "format_outcome",
)
