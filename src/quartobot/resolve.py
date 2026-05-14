"""Pre-fetch citations via manubot before render.

`quartobot resolve` runs `manubot.cite` against a list of persistent-
identifier cite keys (either passed as arguments or scanned out of a
project) and writes the resulting CSL JSON to disk. The point isn't to
replace what `pandoc-manubot-cite` does at render time — it's to do
the network work on a developer's machine, ahead of push, so CI never
sees a Crossref or PubMed hiccup.

Hand-curated cite keys (no recognized prefix) are filtered out: those
live in `references.bib` and pandoc citeproc handles them.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from quartobot.scan import scan_path

logger = logging.getLogger(__name__)

# A CSL JSON item (manubot's `csl_item` is dict-like with mixed types).
# Aliased here to keep type signatures readable without committing to a
# strict TypedDict — manubot's items vary by source.
CSLItem = dict[str, Any]


@dataclass(frozen=True)
class Resolution:
    """The outcome of resolving one cite key."""

    key: str
    """The input key as the user provided it (e.g. `doi:10.1371/foo`)."""
    standard_id: str
    """Manubot's canonical form (e.g. `doi:10.1371/foo`)."""
    short_id: str | None
    """Manubot's short hash used as CSL `id`. None if resolution failed."""
    succeeded: bool
    """Whether resolution produced a CSL item."""
    error: str | None = None
    """Error message when succeeded is False."""


@dataclass
class ResolveOutcome:
    """The aggregate outcome of a resolve run."""

    resolutions: list[Resolution] = field(default_factory=list)
    output_path: Path | None = None
    entries_written: int = 0
    cache_hits: int = 0

    @property
    def failures(self) -> list[Resolution]:
        """Return only the failed resolutions."""
        return [r for r in self.resolutions if not r.succeeded]

    @property
    def successes(self) -> list[Resolution]:
        """Return only the successful resolutions."""
        return [r for r in self.resolutions if r.succeeded]


def collect_resolvable_keys(path: Path) -> list[str]:
    """Walk `path` and return unique persistent-identifier cite keys.

    Hand-curated cite keys (no recognized prefix and not a bare-DOI form)
    are excluded — those belong in `references.bib` and pandoc citeproc
    handles them.

    Keys are returned in their `prefix:identifier` (manubot-standard)
    form, without the leading `@`. Duplicates removed.
    """
    result = scan_path(path)
    seen: set[str] = set()
    out: list[str] = []
    for occ in result.occurrences:
        if occ.prefix is None:
            continue
        standard = f"{occ.prefix}:{occ.identifier}"
        if standard in seen:
            continue
        seen.add(standard)
        out.append(standard)
    return out


def _load_existing(path: Path | None) -> list[CSLItem]:
    """Read an existing CSL JSON file. Return empty list if missing."""
    if path is None or not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _build_cache_index(items: Sequence[CSLItem]) -> dict[str, CSLItem]:
    """Index existing CSL items by their `standard_id` note.

    Manubot writes the standard_id into the CSL item's `note` field as
    `standard_id: <value>`. We parse that out to detect cache hits and
    avoid re-resolving keys we already have.
    """
    out: dict[str, CSLItem] = {}
    for item in items:
        note = item.get("note", "")
        if not isinstance(note, str):
            continue
        for line in note.splitlines():
            line = line.strip()
            if line.startswith("standard_id:"):
                sid = line.split(":", 1)[1].strip()
                out[sid] = item
                break
    return out


def resolve_keys(
    keys: Iterable[str],
    *,
    cache_path: Path | None = None,
    output_path: Path | None = None,
    dry_run: bool = False,
    log_level: str = "WARNING",
) -> ResolveOutcome:
    """Resolve a list of persistent-identifier keys.

    Args:
        keys: Cite keys in `prefix:identifier` form (no leading `@`).
        cache_path: Optional path to read previously-resolved entries
            from. Cache hits skip the network call.
        output_path: Optional path to merge cache + new resolutions
            into. Same shape as cache_path (CSL JSON list).
        dry_run: If True, don't make network calls — report what would
            be resolved.
        log_level: Manubot's logging verbosity for resolver failures.

    Returns:
        A `ResolveOutcome` describing what happened.
    """
    keys = list(keys)
    outcome = ResolveOutcome(output_path=output_path)

    if dry_run:
        for k in keys:
            outcome.resolutions.append(
                Resolution(key=k, standard_id=k, short_id=None, succeeded=True)
            )
        return outcome

    # Defer the import so unit tests can monkey-patch without pulling
    # the whole manubot dependency tree at module-import time.
    from manubot.cite.citekey import CiteKey, citekey_to_csl_item

    existing = _load_existing(cache_path)
    cache_index = _build_cache_index(existing)
    # Output is the union of cache + new resolutions, keyed by short_id.
    new_items: dict[str, CSLItem] = {item["id"]: item for item in existing if "id" in item}

    for key in keys:
        try:
            ck = CiteKey(key, infer_prefix=True)
        except Exception as exc:
            outcome.resolutions.append(
                Resolution(
                    key=key,
                    standard_id=key,
                    short_id=None,
                    succeeded=False,
                    error=f"parse: {exc}",
                )
            )
            continue

        if ck.standard_id in cache_index:
            cached = cache_index[ck.standard_id]
            outcome.cache_hits += 1
            outcome.resolutions.append(
                Resolution(
                    key=key,
                    standard_id=ck.standard_id,
                    short_id=cached.get("id"),
                    succeeded=True,
                )
            )
            continue

        try:
            csl_item = citekey_to_csl_item(ck, log_level=log_level)
        except Exception as exc:
            outcome.resolutions.append(
                Resolution(
                    key=key,
                    standard_id=ck.standard_id,
                    short_id=None,
                    succeeded=False,
                    error=str(exc),
                )
            )
            continue

        if csl_item is None:
            outcome.resolutions.append(
                Resolution(
                    key=key,
                    standard_id=ck.standard_id,
                    short_id=None,
                    succeeded=False,
                    error="resolver returned None",
                )
            )
            continue

        # csl_item is a manubot CSL_Item (dict-like). Coerce to plain dict
        # for JSON serialization.
        plain = dict(csl_item)
        new_items[plain["id"]] = plain
        outcome.resolutions.append(
            Resolution(
                key=key,
                standard_id=ck.standard_id,
                short_id=plain.get("id"),
                succeeded=True,
            )
        )

    if output_path is not None and not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Sort by id for deterministic diffs.
        merged = sorted(new_items.values(), key=lambda d: d.get("id", ""))
        output_path.write_text(
            json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        outcome.entries_written = len(merged)

    return outcome


def format_outcome(outcome: ResolveOutcome) -> str:
    """Render a `ResolveOutcome` as the human-readable CLI report."""
    lines: list[str] = []
    if not outcome.resolutions:
        return "No persistent-identifier cite keys to resolve."

    for res in outcome.resolutions:
        if res.succeeded:
            short = f" → {res.short_id}" if res.short_id else " (dry-run)"
            lines.append(f"  ✓ {res.standard_id}{short}")
        else:
            lines.append(f"  ✗ {res.standard_id} — {res.error}")

    n_ok = len(outcome.successes)
    n_fail = len(outcome.failures)
    lines.append("")
    summary = f"{n_ok} resolved"
    if outcome.cache_hits:
        summary += f" ({outcome.cache_hits} from cache)"
    if n_fail:
        summary += f", {n_fail} failed"
    if outcome.output_path is not None:
        summary += f". Wrote {outcome.entries_written} entries to {outcome.output_path}."
    lines.append(summary)
    return "\n".join(lines)


__all__: Sequence[str] = (
    "Resolution",
    "ResolveOutcome",
    "collect_resolvable_keys",
    "format_outcome",
    "resolve_keys",
)
