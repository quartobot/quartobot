"""Scan a Quarto project for cite keys.

Walks `.qmd` and `.md` files, extracts cite keys (`@<key>` syntax),
classifies each as a persistent-identifier prefix (`doi:`, `pmid:`,
`arxiv:`, etc.), a bare DOI (`10.x/y`), or a hand-curated key, and
groups the results.

This is a heuristic scan, not a pandoc-grade parse. Frontmatter,
fenced code blocks, and inline code spans are skipped. The
authoritative parse happens at render time inside `pandoc-manubot-cite`.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path

#: Manubot citation-key prefixes documented in
#: https://manubot.github.io/manubot/reference/manubot/pandoc/cite_filter/
KNOWN_PREFIXES: frozenset[str] = frozenset(
    {"doi", "pmid", "pmcid", "arxiv", "isbn", "url", "wikidata", "zotero"}
)

#: Directories never worth descending into when scanning a Quarto project.
EXCLUDED_DIRS: frozenset[str] = frozenset(
    {
        "_site",
        "_freeze",
        "_output",
        ".quarto",
        ".git",
        ".venv",
        "node_modules",
        "__pycache__",
    }
)

#: File extensions scanned for citations.
SCANNED_SUFFIXES: frozenset[str] = frozenset({".qmd", ".md"})

# A cite key begins with @, must be preceded by start-of-line or non-word
# character (so email addresses don't match), and starts with a letter or
# digit (digit-leading allows bare DOIs like @10.1371/...). The character
# class after the leading character covers the manubot identifier syntax,
# including URLs with query strings (`?`, `&`, `=`, `#`, `%`, `+`, `~`).
# Sentence-ending punctuation (`.`, `,`, `;`, `:`, `!`, `?`, `)`) is
# stripped from each match post-hoc; see _TRAILING_PUNCT below.
_CITE_KEY_RE = re.compile(r"(?<![A-Za-z0-9_])@[A-Za-z0-9][A-Za-z0-9_:./?&=#%+~-]*")

_PREFIX_RE = re.compile(r"^@([a-z]+):(.+)$")
_BARE_DOI_RE = re.compile(r"^@(10\.\d+/.+)$")

# Inline code spans in pandoc markdown can be delimited by any run of
# backticks; closing must match the opening run length. The regex
# captures the opening run and requires the same count to close, so
# both single-backtick (`@x`) and multi-backtick (``@x``) spans are
# stripped before the cite-key scan. Inline code is single-line in
# pandoc, so we don't enable re.DOTALL.
_INLINE_CODE_RE = re.compile(r"(`+).+?\1")

# Trailing punctuation the regex greedily includes from sentence-final
# positions (`@doi:10.1/foo.` at end of sentence). Stripped from every
# match. Do not include `-` or `_` — those can legitimately end a key.
_TRAILING_PUNCT = ".,;:!?)"


@dataclass(frozen=True)
class CiteOccurrence:
    """A single cite key seen in a file."""

    key: str
    """The full cite key as it appeared in source (e.g. `@doi:10.1371/foo`)."""
    file: Path
    """Absolute or relative path to the source file."""
    line: int
    """1-based line number."""
    prefix: str | None
    """One of KNOWN_PREFIXES, or None for hand-curated / unknown."""
    identifier: str
    """The identifier portion (after the prefix), or the whole key minus `@`."""


@dataclass
class ScanResult:
    """The result of scanning a path."""

    occurrences: list[CiteOccurrence] = field(default_factory=list)
    files_scanned: int = 0

    @property
    def unique_keys(self) -> set[str]:
        """Return the set of distinct cite keys seen."""
        return {occ.key for occ in self.occurrences}

    @property
    def by_prefix(self) -> dict[str, list[CiteOccurrence]]:
        """Group occurrences by prefix label.

        Hand-curated keys (no recognized prefix) are grouped under
        `"(hand-curated)"`.
        """
        out: dict[str, list[CiteOccurrence]] = {}
        for occ in self.occurrences:
            label = occ.prefix if occ.prefix else "(hand-curated)"
            out.setdefault(label, []).append(occ)
        return out

    @property
    def duplicates(self) -> dict[str, list[CiteOccurrence]]:
        """Return cite keys that appear in more than one place."""
        seen: dict[str, list[CiteOccurrence]] = {}
        for occ in self.occurrences:
            seen.setdefault(occ.key, []).append(occ)
        return {key: occs for key, occs in seen.items() if len(occs) > 1}


def classify(key: str) -> tuple[str | None, str]:
    """Classify a cite key into (prefix, identifier).

    Args:
        key: The cite key as it appeared in source, including the leading `@`.

    Returns:
        A tuple `(prefix, identifier)`. `prefix` is one of KNOWN_PREFIXES
        (lowercased) or `None` for hand-curated keys. `identifier` is the
        part after the prefix, or the whole key minus `@` if no prefix.
    """
    if match := _PREFIX_RE.match(key):
        prefix = match.group(1)
        if prefix in KNOWN_PREFIXES:
            return prefix, match.group(2)
    if match := _BARE_DOI_RE.match(key):
        # A bare DOI like @10.1371/foo gets classified under "doi" because
        # manubot-infer-citekey-prefixes does the same at render time.
        return "doi", match.group(1)
    return None, key[1:]


def find_cite_keys(text: str) -> Iterator[tuple[str, int]]:
    """Yield `(key, lineno)` for each cite key in text.

    Skips YAML/TOML frontmatter at the top of the file, fenced code
    blocks, and inline code spans. The line numbers are 1-based.
    """
    lines = text.splitlines()
    in_frontmatter = False
    fence: str | None = None

    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Frontmatter starts at line 1 with `---` or `+++` and ends at
        # the next matching delimiter.
        if lineno == 1 and stripped in ("---", "+++"):
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped in ("---", "+++"):
                in_frontmatter = False
            continue

        # Fenced code blocks. Quarto uses ``` or ~~~ fences; we close
        # on a line whose stripped content starts with the same fence
        # we opened on (matching the run length is not required by
        # pandoc, but our heuristic doesn't fight it).
        if fence is not None:
            if stripped.startswith(fence):
                fence = None
            continue
        if stripped.startswith("```") or stripped.startswith("~~~"):
            ch = stripped[0]
            count = 0
            while count < len(stripped) and stripped[count] == ch:
                count += 1
            fence = ch * count
            continue

        # Strip inline code (`...`) before searching for cite keys —
        # avoids false positives like `@fake:notacite` in inline code.
        cleaned = _INLINE_CODE_RE.sub("", line)

        for match in _CITE_KEY_RE.finditer(cleaned):
            key = match.group(0).rstrip(_TRAILING_PUNCT)
            # Defensive: if stripping somehow ate the whole key, skip.
            if len(key) > 1:
                yield key, lineno


def collect_files(path: Path) -> Iterator[Path]:
    """Yield `.qmd` and `.md` files under `path`.

    If `path` is a file, yield it (if its suffix matches). If `path`
    is a directory, walk it recursively and skip `EXCLUDED_DIRS`.
    Results are sorted for deterministic output.
    """
    if path.is_file():
        if path.suffix in SCANNED_SUFFIXES:
            yield path
        return

    # rglob returns arbitrary order; sort for deterministic output.
    for item in sorted(path.rglob("*")):
        if not item.is_file():
            continue
        if item.suffix not in SCANNED_SUFFIXES:
            continue
        relative_parts = item.relative_to(path).parts
        if any(part in EXCLUDED_DIRS for part in relative_parts):
            continue
        yield item


def scan_path(path: Path) -> ScanResult:
    """Scan `path` for cite keys and return a `ScanResult`."""
    result = ScanResult()
    for file in collect_files(path):
        result.files_scanned += 1
        text = file.read_text(encoding="utf-8", errors="replace")
        for key, line in find_cite_keys(text):
            prefix, identifier = classify(key)
            result.occurrences.append(
                CiteOccurrence(
                    key=key,
                    file=file,
                    line=line,
                    prefix=prefix,
                    identifier=identifier,
                )
            )
    return result


def format_scan_result(result: ScanResult, *, relative_to: Path | None = None) -> str:
    """Render a `ScanResult` as the human-readable CLI output.

    Args:
        result: The scan to format.
        relative_to: If set, file paths in duplicate listings are
            displayed relative to this directory. Otherwise full paths
            are shown.
    """
    if result.files_scanned == 0:
        return "No .qmd or .md files found."

    if not result.occurrences:
        return f"Scanned {result.files_scanned} file(s). No citations found."

    lines: list[str] = []
    by_prefix = result.by_prefix
    # Sort: known prefixes alphabetically first, then "(hand-curated)" last.
    ordered_labels = sorted(
        by_prefix.keys(),
        key=lambda lbl: (lbl == "(hand-curated)", lbl),
    )
    for label in ordered_labels:
        lines.append(f"{label}:")
        by_identifier: dict[str, list[CiteOccurrence]] = {}
        for occ in by_prefix[label]:
            by_identifier.setdefault(occ.identifier, []).append(occ)
        for identifier in sorted(by_identifier):
            count = len(by_identifier[identifier])
            suffix = f" ({count}x)" if count > 1 else ""
            lines.append(f"  {identifier}{suffix}")

    unique = len(result.unique_keys)
    total = len(result.occurrences)
    lines.append("")
    lines.append(
        f"{unique} unique key(s), {total} total occurrence(s) "
        f"across {result.files_scanned} file(s)."
    )

    if result.duplicates:
        lines.append("")
        lines.append("Duplicates:")
        for key in sorted(result.duplicates):
            occs = result.duplicates[key]
            lines.append(f"  {key}:")
            for occ in occs:
                display = occ.file.relative_to(relative_to) if relative_to else occ.file
                lines.append(f"    {display}:{occ.line}")

    return "\n".join(lines)


__all__: Sequence[str] = (
    "EXCLUDED_DIRS",
    "KNOWN_PREFIXES",
    "SCANNED_SUFFIXES",
    "CiteOccurrence",
    "ScanResult",
    "classify",
    "collect_files",
    "find_cite_keys",
    "format_scan_result",
    "scan_path",
)
