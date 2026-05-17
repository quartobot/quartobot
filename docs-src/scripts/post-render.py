#!/usr/bin/env python3
"""Post-process a Quarto-rendered .md so Starlight will pick it up.

Quarto's gfm format strips YAML frontmatter and demotes it to an H1
title plus stray metadata in the body. Starlight needs the
frontmatter back. This script:

1. Reads the matching .qmd to recover `title:` and `description:`.
2. Strips the leading H1 Quarto generated from the title.
3. Rewrites Quarto's `::: {.callout-note}` → Starlight's `:::note`.
4. Prepends a proper Starlight frontmatter block to the .md.

Idempotent: running twice on the same output is a no-op.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def read_qmd_frontmatter(qmd_path: Path) -> dict[str, str]:
    """Parse the leading YAML block of a .qmd file.

    Returns a dict of the top-level scalar fields. Doesn't try to
    handle nested structure — only the flat fields Starlight needs
    (`title`, `description`).
    """
    text = qmd_path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return {}
    block = m.group(1)
    out: dict[str, str] = {}
    for line in block.splitlines():
        line = line.rstrip()
        if not line or line.startswith(" ") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def strip_leading_h1(md: str, expected_title: str) -> str:
    """Drop the first H1 heading Quarto emitted from the .qmd title.

    Quarto's gfm output starts with `# <title>` on the first line. We
    don't want it in the Starlight rendering because Starlight's
    layout already renders the title from frontmatter. Only drops the
    H1 if it matches the .qmd title — defensive against the case
    where the .qmd genuinely starts with its own H1.
    """
    pattern = re.compile(rf"^# {re.escape(expected_title)}\n\n", re.MULTILINE)
    return pattern.sub("", md, count=1)


def rewrite_callouts(md: str) -> str:
    """Quarto → Starlight callout syntax.

    Quarto emits GitHub-style alert callouts in gfm:

        > [!NOTE]
        >
        > body line 1
        > body line 2

    Starlight understands `:::note` (and `:::caution`, `:::tip`,
    `:::danger`). Translate the common ones.
    """
    type_map = {
        "NOTE": "note",
        "TIP": "tip",
        "IMPORTANT": "tip",
        "WARNING": "caution",
        "CAUTION": "caution",
    }
    pattern = re.compile(
        r"^> \[!(\w+)\]\n((?:>.*\n?)+)",
        re.MULTILINE,
    )

    def replace(match: re.Match[str]) -> str:
        kind = type_map.get(match.group(1), "note")
        body = match.group(2)
        # Strip leading `> ` (or just `>`) from each line.
        stripped = re.sub(r"^> ?", "", body, flags=re.MULTILINE)
        # Drop empty leading/trailing blank lines.
        stripped = stripped.strip("\n")
        return f":::{kind}\n{stripped}\n:::\n"

    return pattern.sub(replace, md)


def has_frontmatter(md: str) -> bool:
    return md.startswith("---\n") and "\n---\n" in md[4:]


def main(md_path: Path) -> int:
    qmd_path = Path("docs-src") / f"{md_path.stem}.qmd"
    if not qmd_path.exists():
        # Try relative to script location for direct invocation.
        qmd_path = md_path.parent.parent.parent.parent.parent / "docs-src" / f"{md_path.stem}.qmd"
    if not qmd_path.exists():
        print(f"error: matching .qmd not found for {md_path}", file=sys.stderr)
        return 1

    meta = read_qmd_frontmatter(qmd_path)
    title = meta.get("title", md_path.stem)
    description = meta.get("description", "")

    text = md_path.read_text(encoding="utf-8")

    if has_frontmatter(text):
        # Already post-processed; idempotent no-op.
        return 0

    text = strip_leading_h1(text, title)
    text = rewrite_callouts(text)

    frontmatter = f'---\ntitle: "{title}"\n'
    if description:
        frontmatter += f'description: "{description}"\n'
    frontmatter += "---\n\n"

    md_path.write_text(frontmatter + text, encoding="utf-8")
    print(f"post-processed {md_path}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: post-render.py <rendered.md>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(Path(sys.argv[1])))
