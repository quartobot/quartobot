"""MCP server exposing read-only citation tools over stdio.

This is an opt-in extra (`uv tool install 'quartobot[mcp]'`). The
top-level `from mcp.server.fastmcp import FastMCP` is the load-bearing
import: it raises ImportError on a base install, which the CLI's
`mcp` subcommand catches and turns into a one-line install hint
instead of a traceback.

Three tools register, all thin wrappers over functions that already
exist in the package — no parallel resolver logic, no parallel scan
code. That's the durability story: if `manubot.cite` or
`quartobot.scan` or `quartobot.validate` move, there is exactly one
shim site here to update.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

server = FastMCP("quartobot")


def _occurrence_to_dict(occ: Any) -> dict[str, Any]:
    """Render a `CiteOccurrence` as a JSON-serializable dict.

    Kept narrow on purpose — only the fields an agent needs to point
    a human back at the source location.
    """
    out: dict[str, Any] = {"key": occ.key, "file": str(occ.file), "line": occ.line}
    if occ.cell is not None:
        out["cell"] = occ.cell
    return out


def _check_to_dict(check: Any) -> dict[str, Any]:
    """Render a validate `Check` as a JSON-serializable dict."""
    return {"name": check.name, "passed": check.passed, "detail": check.detail}


@server.tool()
def resolve_citation(cite_key: str) -> dict[str, Any]:
    """Resolve a manubot-style citation key to CSL JSON.

    Args:
        cite_key: A persistent-identifier key — `doi:10.1371/...`,
            `pmid:31479462`, `arxiv:2104.10729`, `isbn:...`, `url:...`,
            `wikidata:Q...`, or `pmc:...`. A leading `@` and a trailing
            pandoc-terminator punctuation (`/`, `.`, `,`, `;`, `:`,
            `!`, `?`) are tolerated.

    Returns:
        The CSL JSON entry for the resolved citation, or a dict with
        an `error` key plus the normalized `cite_key` if the resolver
        couldn't reach the source API or the key is unrecognized.
        The success shape mirrors manubot's own output so downstream
        pandoc-citeproc consumers don't need special handling.
    """
    from manubot.cite import citekey_to_csl_item

    from quartobot.scan import strip_pandoc_trailing

    normalized = strip_pandoc_trailing(cite_key.lstrip("@"))
    try:
        return dict(citekey_to_csl_item(normalized))
    except Exception as e:
        return {"error": str(e), "cite_key": normalized}


@server.tool()
def scan_project(path: str, recursive: bool = True) -> dict[str, Any]:
    """Scan a Quarto project for citation keys.

    Args:
        path: Project root, or a single file.
        recursive: Descend into subdirectories. Defaults to True.

    Returns:
        A summary with `files_scanned`, `by_prefix` (cite keys grouped
        by `doi:`, `pmid:`, ... and `(hand-curated)` for keys with no
        recognized prefix), `repetitions` (keys cited more than once
        anywhere — informational, not a gate signal), and `duplicates`
        (keys appearing in more than one file — the case
        `validate_project`'s no-duplicate-cites check actually fails
        on). Each occurrence carries `file`, `line`, and optionally
        `cell` for Jupyter notebooks.
    """
    from quartobot.scan import scan_path

    result = scan_path(Path(path), recursive=recursive)
    return {
        "files_scanned": result.files_scanned,
        "by_prefix": {
            label: [_occurrence_to_dict(o) for o in occs]
            for label, occs in result.by_prefix.items()
        },
        "repetitions": {
            key: [_occurrence_to_dict(o) for o in occs] for key, occs in result.repetitions.items()
        },
        "duplicates": {
            key: [_occurrence_to_dict(o) for o in occs] for key, occs in result.duplicates.items()
        },
    }


@server.tool()
def validate_project(path: str) -> dict[str, Any]:
    """Run the static pre-flight checks against a Quarto project.

    Args:
        path: Project root — the directory where `_quarto.yml` lives.

    Returns:
        A summary with `passed` (overall boolean across every check),
        `checks` (the full list, each `{name, passed, detail}`), and
        `failures` (the subset that did not pass). Useful for an
        agent that wants to confirm its edits don't break the
        manuscript's CI gate.
    """
    from quartobot.validate import validate_project as _validate_project

    outcome = _validate_project(Path(path))
    return {
        "passed": outcome.passed,
        "checks": [_check_to_dict(c) for c in outcome.checks],
        "failures": [_check_to_dict(c) for c in outcome.failures],
    }


def run() -> None:
    """Run the MCP server over stdio.

    Called by `quartobot mcp`. Returns when the client disconnects.
    """
    server.run()


__all__ = ["resolve_citation", "run", "scan_project", "server", "validate_project"]
