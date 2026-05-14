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
    help="Resolve every key found by scanning this path.",
)
def resolve(keys: tuple[str, ...], from_scan: Path | None) -> None:
    """Pre-fetch citations and write to references.json (and BibTeX).

    Resolve a list of persistent-identifier keys via manubot.cite and
    write the resulting CSL JSON to references.json. Optionally append
    BibTeX to references.bib. The point isn't to replace what manubot
    does at render — it's to do it ahead of time so CI never sees a
    Crossref hiccup.
    """
    click.echo("not yet — see https://github.com/seandavi/quartobot/issues/27")
    raise SystemExit(2)


@main.command()
@click.argument(
    "project",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=".",
)
def validate(project: Path) -> None:
    """Pre-flight check a Quarto project for citation and config issues.

    Every cite key in the prose either lives in references.bib or
    resolves cleanly; _quarto.yml declares both bibliographies;
    manubot-bibliography-cache is set. Exit nonzero on any failure.
    """
    click.echo("not yet — see https://github.com/seandavi/quartobot/issues/28")
    raise SystemExit(2)


if __name__ == "__main__":
    main()
