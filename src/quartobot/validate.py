"""Pre-flight validation of a Quarto project for the quartobot pattern.

`quartobot validate` runs a battery of static checks before render:

- The quarto-manubot-cite extension is installed.
- `_quarto.yml` exists and declares `bibliography:`.
- The manubot configuration keys are present and consistent
  (`manubot-bibliography-cache`, `manubot-output-bibliography`,
  the output file is also in the bibliography list).
- The project's cite keys don't have duplicates that would break
  pre-commit hooks (delegates to `scan`).

Citation-resolution checks (do all `@doi:` keys actually resolve at
Crossref?) are deliberately out of scope for v0.1 — they'd require
network access. Run `quartobot resolve --dry-run --from-scan .` if you
want that check separately.

Exits 0 if every check passes, 1 if any fail.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from quartobot.scan import scan_path

DEFAULT_EXTENSION_DIR = Path("_extensions") / "seandavi" / "quarto-manubot-cite"


@dataclass(frozen=True)
class Check:
    """One pre-flight check and its outcome."""

    name: str
    """Short label of what was checked."""
    passed: bool
    """Whether the check passed."""
    detail: str | None = None
    """Optional human-readable detail (e.g. error message)."""


@dataclass
class ValidateOutcome:
    """The aggregate of every check run by `validate_project`."""

    checks: list[Check] = field(default_factory=list)

    @property
    def failures(self) -> list[Check]:
        """Return only failed checks."""
        return [c for c in self.checks if not c.passed]

    @property
    def passed(self) -> bool:
        """True if every check passed."""
        return all(c.passed for c in self.checks)


def _load_quarto_yml(path: Path) -> dict[str, Any] | None:
    """Read `_quarto.yml` from the project root. None if missing or unparsable."""
    yml = path / "_quarto.yml"
    if not yml.exists():
        return None
    try:
        loaded = yaml.safe_load(yml.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return None
    if not isinstance(loaded, dict):
        return None
    return loaded


def _check_extension_installed(project: Path) -> Check:
    """The quarto-manubot-cite extension must be present in `_extensions/`."""
    target = project / DEFAULT_EXTENSION_DIR / "_extension.yml"
    if target.exists():
        return Check(
            name="extension installed",
            passed=True,
            detail=f"found {DEFAULT_EXTENSION_DIR}/_extension.yml",
        )
    return Check(
        name="extension installed",
        passed=False,
        detail=(f"missing {target} — run `quarto add seandavi/quartobot --no-prompt`"),
    )


def _check_quarto_yml_exists(project: Path) -> Check:
    """`_quarto.yml` must exist for any Quarto project."""
    yml = project / "_quarto.yml"
    if yml.exists():
        return Check(name="_quarto.yml exists", passed=True)
    return Check(
        name="_quarto.yml exists",
        passed=False,
        detail=f"{yml} not found — is this a Quarto project?",
    )


def _bibliography_list(config: dict[str, Any]) -> list[str]:
    """Normalize `_quarto.yml`'s `bibliography:` value to a list of paths."""
    value = config.get("bibliography")
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


def _check_bibliography_declared(config: dict[str, Any]) -> Check:
    """`bibliography:` must be set in `_quarto.yml`."""
    bibs = _bibliography_list(config)
    if not bibs:
        return Check(
            name="bibliography declared",
            passed=False,
            detail="_quarto.yml has no `bibliography:` key",
        )
    return Check(
        name="bibliography declared",
        passed=True,
        detail=f"{len(bibs)} file(s): {', '.join(bibs)}",
    )


def _check_manubot_cache(config: dict[str, Any]) -> Check:
    """`manubot-bibliography-cache:` should be set so renders stay offline."""
    cache = config.get("manubot-bibliography-cache")
    if not cache:
        return Check(
            name="manubot-bibliography-cache",
            passed=False,
            detail=(
                "missing — without this, manubot will re-resolve every "
                "citation on every render. Recommended: "
                "`manubot-bibliography-cache: _freeze/manubot-cache.json`"
            ),
        )
    return Check(
        name="manubot-bibliography-cache",
        passed=True,
        detail=f"set to `{cache}`",
    )


def _check_manubot_output_matches_bibliography(config: dict[str, Any]) -> Check:
    """`manubot-output-bibliography` should also appear in `bibliography:`.

    Otherwise manubot writes a CSL JSON file that citeproc never reads,
    and the resolved entries don't reach the rendered output.
    """
    output = config.get("manubot-output-bibliography")
    if not output:
        return Check(
            name="manubot-output-bibliography",
            passed=False,
            detail=(
                "missing — recommended: "
                "`manubot-output-bibliography: references.json` "
                "(and include `references.json` in `bibliography:`)"
            ),
        )
    bibs = _bibliography_list(config)
    if str(output) not in bibs:
        return Check(
            name="manubot-output-bibliography",
            passed=False,
            detail=(
                f"`{output}` set, but not listed under `bibliography:` "
                f"({bibs}). Citeproc won't read manubot's resolved entries."
            ),
        )
    return Check(
        name="manubot-output-bibliography",
        passed=True,
        detail=f"set to `{output}` and listed in `bibliography:`",
    )


def _check_no_duplicate_cites(project: Path) -> Check:
    """Cite keys appearing in multiple files break pre-commit-hook flow."""
    result = scan_path(project)
    dup_count = len(result.duplicates)
    if dup_count == 0:
        return Check(
            name="no duplicate cite keys",
            passed=True,
            detail=f"{len(result.unique_keys)} unique key(s) in {result.files_scanned} file(s)",
        )
    examples = list(result.duplicates.keys())[:3]
    suffix = f" (e.g. {', '.join(examples)})"
    if dup_count > 3:
        suffix += f" — {dup_count - 3} more"
    return Check(
        name="no duplicate cite keys",
        passed=False,
        detail=f"{dup_count} key(s) appear in multiple files{suffix}",
    )


def validate_project(project: Path) -> ValidateOutcome:
    """Run every check against `project` (the Quarto project root)."""
    outcome = ValidateOutcome()

    # Extension first — without it the whole flow doesn't work.
    outcome.checks.append(_check_extension_installed(project))

    yml_check = _check_quarto_yml_exists(project)
    outcome.checks.append(yml_check)

    if yml_check.passed:
        config = _load_quarto_yml(project)
        if config is None:
            outcome.checks.append(
                Check(
                    name="_quarto.yml parses as YAML",
                    passed=False,
                    detail="failed to parse — fix YAML syntax",
                )
            )
        else:
            outcome.checks.append(_check_bibliography_declared(config))
            outcome.checks.append(_check_manubot_cache(config))
            outcome.checks.append(_check_manubot_output_matches_bibliography(config))

    # Duplicate-cite scan is independent of _quarto.yml.
    outcome.checks.append(_check_no_duplicate_cites(project))

    return outcome


def format_outcome(outcome: ValidateOutcome) -> str:
    """Pretty-print a ValidateOutcome."""
    lines: list[str] = []
    for c in outcome.checks:
        glyph = "✓" if c.passed else "✗"
        line = f"  {glyph} {c.name}"
        if c.detail:
            line += f" — {c.detail}"
        lines.append(line)
    lines.append("")
    n_fail = len(outcome.failures)
    if n_fail == 0:
        lines.append(f"All {len(outcome.checks)} check(s) passed.")
    else:
        lines.append(f"{n_fail} of {len(outcome.checks)} check(s) failed. Exit 1.")
    return "\n".join(lines)


__all__: Sequence[str] = (
    "DEFAULT_EXTENSION_DIR",
    "Check",
    "ValidateOutcome",
    "format_outcome",
    "validate_project",
)
