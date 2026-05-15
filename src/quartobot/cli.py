"""Command-line interface for quartobot."""

from __future__ import annotations

from pathlib import Path

import click

from quartobot import __version__


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="quartobot")
def main() -> None:
    """quartobot: manuscript-as-software, on Quarto.

    Pre-render and out-of-render tooling for Quarto projects that resolve
    citations through manubot from a pre-render hook.
    """


@main.command()
@click.argument(
    "path",
    type=click.Path(exists=True, file_okay=True, dir_okay=True, path_type=Path),
    default=".",
)
@click.option(
    "--recursive/--no-recursive",
    default=True,
    show_default=True,
    help=(
        "When PATH is a directory, descend into subdirectories. "
        "`--no-recursive` only scans files directly under PATH."
    ),
)
def scan(path: Path, recursive: bool) -> None:
    """Scan a Quarto project for cite keys and group by prefix.

    Walks supported files (.qmd, .md, .Rmd, .ipynb) under PATH,
    extracts cite keys (both persistent-identifier ones like @doi: and
    @pmid:, and hand-curated keys), and reports counts and duplicates.
    Pure read; no network. Markdown cells inside .ipynb notebooks are
    scanned; cell index appears alongside line number in duplicate
    reports (e.g. `paper.ipynb:cell3:5`).

    Render outputs and tool caches (`_site/`, `_book/`, `_freeze/`,
    `.quarto/`, `.git/`, `.ipynb_checkpoints/`, `node_modules/`, etc.)
    are skipped at any depth.

    Exits 1 if any duplicates are found (so it works as a pre-commit
    hook), 0 otherwise.
    """
    from quartobot.scan import format_scan_result, scan_path

    result = scan_path(path, recursive=recursive)
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
    "--recursive/--no-recursive",
    default=True,
    show_default=True,
    help=(
        "When --from-scan is a directory, descend into subdirectories. "
        "`--no-recursive` only scans files directly under that path."
    ),
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
@click.option(
    "--id-mode",
    type=click.Choice(["short-hash", "citation-key"]),
    default="short-hash",
    show_default=True,
    help=(
        "How to populate the CSL `id` field. `citation-key` (the form "
        "expected by the `quartobot` pre-render hook) writes the user's "
        "original `prefix:identifier` so pandoc-citeproc matches prose "
        "keys directly. `short-hash` keeps manubot's hash form for "
        "callers that consume `manubot.cite` output directly."
    ),
)
def resolve(
    keys: tuple[str, ...],
    from_scan: Path | None,
    output: Path,
    cache: Path | None,
    dry_run: bool,
    id_mode: str,
    recursive: bool,
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
        collected.extend(collect_resolvable_keys(from_scan, recursive=recursive))

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
        id_mode=id_mode,
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

    Runs a battery of static config checks: `_quarto.yml` exists and
    declares `bibliography:`, `project.pre-render` calls
    `quartobot resolve --id-mode citation-key`, `references.json`
    is in the bibliography list, no duplicate cite keys across files.

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


@main.group()
def snapshots() -> None:
    """Inspect and apply the gh-pages snapshot retention policy.

    The retention policy controls which ``v/<sha>/`` directories on
    gh-pages are kept, which are replaced with redirect stubs, and how
    far gh-pages is allowed to grow before the workflow refuses to push.

    Defaults apply when no ``quartobot.snapshots`` block is present in
    ``_quarto.yml``. Pass ``--help`` to either subcommand for details.
    """


def _resolve_git_facts(
    project: Path,
    latest_sha: str | None,
    tag_shas: str | None,
) -> tuple[str, set[str]]:
    """Fill in ``latest_sha`` and ``tag_shas`` from git when omitted.

    The snapshots module is intentionally git-free; this helper bridges
    it to the local repo so ``quartobot snapshots ...`` is ergonomic
    for ad-hoc local runs without an explicit ``--latest-sha``.

    Args:
        project: Project directory, used as the git working dir.
        latest_sha: User-supplied SHA, or ``None`` to resolve from
            ``git rev-parse HEAD``.
        tag_shas: User-supplied comma-separated SHA list, or ``None``
            to resolve from ``git for-each-ref refs/tags/``.

    Returns:
        ``(resolved_latest_sha, resolved_tag_shas_set)``.

    Raises:
        click.ClickException: If git isn't available or the directory
            isn't a git repository and the caller didn't supply
            ``latest_sha`` explicitly.
    """
    import subprocess

    if latest_sha is None:
        try:
            latest_sha = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=project,
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            raise click.ClickException(
                "could not resolve --latest-sha from git; pass it explicitly"
            ) from exc

    if tag_shas is None:
        try:
            out = subprocess.check_output(
                ["git", "for-each-ref", "--format=%(objectname)", "refs/tags/"],
                cwd=project,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            resolved_tags = {line.strip() for line in out.splitlines() if line.strip()}
        except (FileNotFoundError, subprocess.CalledProcessError):
            resolved_tags = set()
    else:
        resolved_tags = {s.strip() for s in tag_shas.split(",") if s.strip()}

    return latest_sha, resolved_tags


_GH_PAGES_OPT = click.option(
    "--gh-pages-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    required=True,
    help="Path to a checkout of the gh-pages branch.",
)
_PROJECT_OPT = click.option(
    "--project",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=Path("."),
    show_default=True,
    help="Project directory containing _quarto.yml.",
)
_LATEST_SHA_OPT = click.option(
    "--latest-sha",
    type=str,
    default=None,
    help=(
        "Full SHA of the build to treat as 'latest'. Defaults to "
        "`git rev-parse HEAD` in the project directory."
    ),
)
_TAG_SHAS_OPT = click.option(
    "--tag-shas",
    type=str,
    default=None,
    help=(
        "Comma-separated full SHAs of tagged commits. Defaults to all "
        "tag targets in the project's git repo."
    ),
)


@snapshots.command("inventory")
@_GH_PAGES_OPT
@_PROJECT_OPT
@_LATEST_SHA_OPT
@_TAG_SHAS_OPT
def snapshots_inventory(
    gh_pages_dir: Path,
    project: Path,
    latest_sha: str | None,
    tag_shas: str | None,
) -> None:
    """Echo the retention policy and current gh-pages inventory.

    Read-only. Does not modify ``gh-pages-dir``. Use this on PR events
    or for ad-hoc local inspection — it shows what *would* be pruned
    on the next ``apply``.
    """
    from quartobot.snapshots import (
        decide_retention,
        format_log,
        inventory,
        load_policy,
        project_post_prune_bytes,
    )

    load = load_policy(project)
    inv = inventory(gh_pages_dir)
    resolved_latest, resolved_tags = _resolve_git_facts(project, latest_sha, tag_shas)
    decision = decide_retention(
        inv, load.policy, latest_sha=resolved_latest, tagged_shas=resolved_tags
    )
    projected = project_post_prune_bytes(inv, decision, load.policy)
    click.echo(format_log(load, inv, decision, projected))


@snapshots.command("apply")
@_GH_PAGES_OPT
@_PROJECT_OPT
@_LATEST_SHA_OPT
@_TAG_SHAS_OPT
@click.option(
    "--dry-run",
    is_flag=True,
    help="Report what would change without modifying gh-pages-dir.",
)
def snapshots_apply(
    gh_pages_dir: Path,
    project: Path,
    latest_sha: str | None,
    tag_shas: str | None,
    dry_run: bool,
) -> None:
    """Apply the retention policy: prune ``v/<sha>/`` and write stubs.

    Mutates ``gh-pages-dir`` in place. The caller is responsible for
    committing and pushing the result.

    Exits 1 if the projected post-prune total still exceeds
    ``size_budget_mb`` and ``on_over_budget`` is ``fail``.
    """
    from quartobot.snapshots import (
        apply_decision,
        decide_retention,
        format_log,
        inventory,
        load_policy,
        project_post_prune_bytes,
    )

    load = load_policy(project)
    inv = inventory(gh_pages_dir)
    resolved_latest, resolved_tags = _resolve_git_facts(project, latest_sha, tag_shas)
    decision = decide_retention(
        inv, load.policy, latest_sha=resolved_latest, tagged_shas=resolved_tags
    )
    projected = project_post_prune_bytes(inv, decision, load.policy)
    click.echo(format_log(load, inv, decision, projected))

    if not dry_run:
        apply_decision(inv, decision, load.policy)
        click.echo("")
        click.echo(f"Applied: {len(decision.prune)} snapshots pruned in {gh_pages_dir}")

    budget_bytes = load.policy.size_budget_mb * 1_000_000
    if projected > budget_bytes:
        message = (
            f"projected post-prune size {projected / 1_000_000:.1f} MB exceeds "
            f"budget {load.policy.size_budget_mb} MB"
        )
        if load.policy.on_over_budget == "fail":
            raise click.ClickException(message)
        click.echo(f"warning: {message}", err=True)


@main.command()
@click.argument(
    "project",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=".",
)
@click.option(
    "--project-type",
    type=click.Choice(["auto", "manuscript", "book"]),
    default="auto",
    show_default=True,
    help=(
        "Quarto project shape. `auto` detects from an existing _quarto.yml "
        "and falls back to manuscript when there's nothing to detect from."
    ),
)
def init(project: Path, project_type: str) -> None:
    """Scaffold the quartobot pattern into an existing Quarto project.

    Writes the files that make a vanilla Quarto project adopt the
    quartobot pattern: `_quarto.yml` (when absent), `references.bib`,
    the version banner template + dev placeholder, a ten-line GitHub
    Actions workflow that calls the upstream reusable workflow, the
    PR-cleanup workflow, and `.gitignore` augments.

    Conservative — never overwrites existing files. If `_quarto.yml`
    already exists, prints a YAML snippet to merge in manually.
    """
    from quartobot.init_project import format_outcome, init_project

    outcome = init_project(project, project_type=project_type)
    click.echo(format_outcome(outcome, project=project))


if __name__ == "__main__":
    main()
