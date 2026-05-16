"""Tests for `quartobot use github-ci`."""

from __future__ import annotations

import yaml
from click.testing import CliRunner

from quartobot.cli import main
from quartobot.use_github_ci import (
    apply_github_ci,
    format_outcome,
)


def test_apply_writes_ci_machinery(tmp_path):
    outcome = apply_github_ci(tmp_path)
    assert outcome.project_type == "manuscript"
    must_exist = [
        "_version-banner.html.template",
        "_version-banner.html",
        ".github/workflows/render.yml",
        ".github/workflows/pr-closed.yml",
    ]
    for rel in must_exist:
        assert (tmp_path / rel).exists(), f"{rel} not created"
    render = (tmp_path / ".github/workflows/render.yml").read_text()
    assert "project-type: manuscript" in render
    pr_closed = (tmp_path / ".github/workflows/pr-closed.yml").read_text()
    assert "Clean up PR preview" in pr_closed
    assert "types: [closed]" in pr_closed


def test_apply_respects_book_project_type(tmp_path):
    outcome = apply_github_ci(tmp_path, project_type="book")
    assert outcome.project_type == "book"
    render = (tmp_path / ".github/workflows/render.yml").read_text()
    assert "project-type: book" in render


def test_apply_auto_detects_book(tmp_path):
    (tmp_path / "_quarto.yml").write_text(yaml.safe_dump({"project": {"type": "book"}}))
    outcome = apply_github_ci(tmp_path)
    assert outcome.project_type == "book"


def test_apply_is_idempotent(tmp_path):
    apply_github_ci(tmp_path)
    snapshot = {p: p.read_text() for p in tmp_path.rglob("*") if p.is_file()}
    outcome_second = apply_github_ci(tmp_path)
    for p, content in snapshot.items():
        assert p.read_text() == content, f"{p} changed on re-run"
    # Every file should report as already-present.
    for action in outcome_second.actions:
        assert action.status == "skipped-exists", f"{action.path} status: {action.status}"


def test_apply_does_not_overwrite_existing_files(tmp_path):
    files = {
        "_version-banner.html.template": "original template\n",
        "_version-banner.html": "original banner\n",
        ".github/workflows/render.yml": "original workflow\n",
        ".github/workflows/pr-closed.yml": "original pr-closed\n",
    }
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    apply_github_ci(tmp_path)
    for rel, expected in files.items():
        assert (tmp_path / rel).read_text() == expected, f"{rel} was overwritten"


def test_manual_merge_snippet_when_yml_lacks_include(tmp_path):
    # A `_quarto.yml` with a pre-render line but no banner include.
    pre_render_cmd = (
        "quartobot resolve --from-scan . --output references.json --id-mode citation-key"
    )
    (tmp_path / "_quarto.yml").write_text(
        "project:\n"
        "  type: default\n"
        f"  pre-render: {pre_render_cmd}\n"
        "bibliography:\n"
        "  - references.bib\n"
        "  - references.json\n"
    )
    outcome = apply_github_ci(tmp_path)
    assert outcome.manual_merge_snippet is not None
    assert "_version-banner.html" in outcome.manual_merge_snippet
    assert "include-before-body" in outcome.manual_merge_snippet


def test_manual_merge_snippet_suppressed_when_already_included(tmp_path):
    # `_quarto.yml` already declares the banner include.
    (tmp_path / "_quarto.yml").write_text(
        "project:\n"
        "  type: default\n"
        "format:\n"
        "  html:\n"
        "    include-before-body:\n"
        "      - _version-banner.html\n"
    )
    outcome = apply_github_ci(tmp_path)
    assert outcome.manual_merge_snippet is None


def test_manual_merge_snippet_suppressed_when_yml_missing(tmp_path):
    # No `_quarto.yml`: caller probably hasn't run init yet. Stay quiet
    # on the merge front — the user's path is `init` then `use github-ci`.
    outcome = apply_github_ci(tmp_path)
    assert outcome.manual_merge_snippet is None


def test_manual_merge_snippet_robust_to_broken_yml(tmp_path):
    # Unparsable yml: the snippet should still print (the user will
    # see it alongside whatever parser error they're already dealing
    # with).
    (tmp_path / "_quarto.yml").write_text("not: valid: yaml: at all\n: : :")
    outcome = apply_github_ci(tmp_path)
    assert outcome.manual_merge_snippet is not None


def test_format_outcome_emits_glyphs(tmp_path):
    outcome = apply_github_ci(tmp_path)
    out = format_outcome(outcome, project=tmp_path)
    assert "_version-banner.html" in out
    assert "render.yml" in out
    assert "pr-closed.yml" in out
    assert "Next steps:" in out


def test_cli_use_group_help_lists_github_ci():
    runner = CliRunner()
    result = runner.invoke(main, ["use", "--help"])
    assert result.exit_code == 0, result.output
    assert "github-ci" in result.output


def test_cli_use_github_ci_in_empty_dir(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["use", "github-ci", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / ".github/workflows/render.yml").exists()
    assert (tmp_path / "_version-banner.html").exists()


def test_cli_use_github_ci_default_path_uses_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["use", "github-ci"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / ".github/workflows/render.yml").exists()


def test_cli_init_then_use_github_ci_round_trip(tmp_path):
    runner = CliRunner()
    init_result = runner.invoke(main, ["init", str(tmp_path)])
    assert init_result.exit_code == 0, init_result.output
    use_result = runner.invoke(main, ["use", "github-ci", str(tmp_path)])
    assert use_result.exit_code == 0, use_result.output
    # init writes 3 files (_quarto.yml + references.bib + .gitignore).
    assert (tmp_path / "_quarto.yml").exists()
    assert (tmp_path / "references.bib").exists()
    assert (tmp_path / ".gitignore").exists()
    # use github-ci adds 4 more.
    assert (tmp_path / "_version-banner.html.template").exists()
    assert (tmp_path / "_version-banner.html").exists()
    assert (tmp_path / ".github/workflows/render.yml").exists()
    assert (tmp_path / ".github/workflows/pr-closed.yml").exists()
    # Since init wrote _quarto.yml without the banner include, use
    # should have printed the merge snippet.
    assert "_version-banner.html" in use_result.output
    assert "include-before-body" in use_result.output
