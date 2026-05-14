"""Command-line interface for quartobot."""

from __future__ import annotations

from pathlib import Path

import click

from quartobot import __version__


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="quartobot")
def main() -> None:
    """quartobot: manuscript-as-software, on Quarto.

    Pre-render and out-of-render tooling for Quarto projects that use the
    quarto-manubot-cite extension.
    """


@main.command()
@click.argument(
    "path",
    type=click.Path(exists=True, file_okay=True, dir_okay=True, path_type=Path),
    default=".",
)
def scan(path: Path) -> None:
    """Scan a Quarto project for cite keys and group by prefix.

    Walks .qmd and .md files under PATH, extracts cite keys (both
    persistent-identifier ones like @doi: and @pmid:, and hand-curated
    keys), and reports counts and duplicates. Pure read; no network.

    Exits 1 if any duplicates are found (so it works as a pre-commit
    hook), 0 otherwise.
    """
    from quartobot.scan import format_scan_result, scan_path

    result = scan_path(path)
    relative_to = path if path.is_dir() else path.parent
    click.echo(format_scan_result(result, relative_to=relative_to))
    if result.duplicates:
        raise SystemExit(1)


@main.command()
@click.argument("keys", nargs=-1)
@click.option(
    "--from-scan",
    type=click.Path(exists=True, file_okay=True, dir_okay=True, path_type=Path),
    default=None,
    help="Resolve every persistent-identifier key found by scanning this path.",
)
@click.option(
    "--output",
    type=click.Path(file_okay=True, dir_okay=False, path_type=Path),
    default="references.json",
    show_default=True,
    help="Path to write the resolved CSL JSON bibliography to.",
)
@click.option(
    "--cache",
    type=click.Path(file_okay=True, dir_okay=False, path_type=Path),
    default=None,
    help=(
        "Optional path to read cached entries from. Cache hits skip the "
        "network call. Defaults to the value of --output, so resolve is "
        "idempotent against its own previous output."
    ),
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Report what would be resolved without making network calls.",
)
def resolve(
    keys: tuple[str, ...],
    from_scan: Path | None,
    output: Path,
    cache: Path | None,
    dry_run: bool,
) -> None:
    """Pre-fetch citations and write CSL JSON to disk.

    Resolves persistent-identifier cite keys via manubot.cite and writes
    the resulting CSL JSON to --output (default `references.json`). The
    point isn't to replace what manubot does at render — it's to do the
    network work on a developer's machine ahead of push, so CI never
    sees a Crossref or PubMed hiccup.

    Pass keys as arguments (`@doi:10.x/y pmid:12345`) or use --from-scan
    to resolve every persistent-identifier cite found in a project.
    Hand-curated keys (no recognized prefix) are skipped — those live
    in references.bib and pandoc citeproc handles them.

    Exits 1 if any keys fail to resolve, 0 otherwise.
    """
    from quartobot.resolve import collect_resolvable_keys, format_outcome, resolve_keys

    collected: list[str] = []
    for k in keys:
        # Allow either `@doi:10.x/y` or `doi:10.x/y` — strip leading @.
        collected.append(k.lstrip("@"))

    if from_scan is not None:
        collected.extend(collect_resolvable_keys(from_scan))

    # De-dup while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for k in collected:
        if k not in seen:
            seen.add(k)
            unique.append(k)

    if not unique:
        click.echo("No persistent-identifier cite keys to resolve.")
        return

    cache_path = cache if cache is not None else output
    outcome = resolve_keys(
        unique,
        cache_path=cache_path,
        output_path=output,
        dry_run=dry_run,
    )
    click.echo(format_outcome(outcome))
    if outcome.failures:
        raise SystemExit(1)


@main.command()
@click.argument(
    "project",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=".",
)
def validate(project: Path) -> None:
    """Pre-flight check a Quarto project for the quartobot pattern.

    Runs a battery of static config checks: the extension is installed,
    `_quarto.yml` declares `bibliography:` and the manubot keys, the
    output bibliography is also in the bibliography list, no duplicate
    cite keys across files.

    Citation-resolution checks (does Crossref actually return metadata
    for this DOI?) are out of scope here — they need network. Run
    `quartobot resolve --dry-run --from-scan .` if you want that.

    Exits 1 if any check fails, 0 if all pass.
    """
    from quartobot.validate import format_outcome, validate_project

    outcome = validate_project(project)
    click.echo(format_outcome(outcome))
    if not outcome.passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
