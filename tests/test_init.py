"""Tests for the init command and module."""

from __future__ import annotations

import yaml
from click.testing import CliRunner

from quartobot.cli import main
from quartobot.init_project import (
    Action,
    InitOutcome,
    _ensure_gitignore,
    detect_project_type,
    format_outcome,
    init_project,
)


def test_detect_no_yml(tmp_path):
    assert detect_project_type(tmp_path) == "unknown"


def test_detect_book(tmp_path):
    (tmp_path / "_quarto.yml").write_text(yaml.safe_dump({"project": {"type": "book"}}))
    assert detect_project_type(tmp_path) == "book"


def test_detect_manuscript_default_type(tmp_path):
    (tmp_path / "_quarto.yml").write_text("title: foo\n")
    assert detect_project_type(tmp_path) == "manuscript"


def test_detect_manuscript_explicit_default(tmp_path):
    (tmp_path / "_quarto.yml").write_text(yaml.safe_dump({"project": {"type": "default"}}))
    assert detect_project_type(tmp_path) == "manuscript"


def test_detect_broken_yml(tmp_path):
    (tmp_path / "_quarto.yml").write_text("not: valid: yaml: at all\n: : :")
    assert detect_project_type(tmp_path) == "unknown"


def test_init_empty_project_creates_files(tmp_path):
    outcome = init_project(tmp_path)
    assert outcome.project_type == "manuscript"
    must_exist = [
        "_quarto.yml",
        "references.bib",
        "_version-banner.html.template",
        "_version-banner.html",
        ".github/workflows/render.yml",
        ".github/workflows/pr-closed.yml",
        ".gitignore",
    ]
    for rel in must_exist:
        assert (tmp_path / rel).exists(), f"{rel} not created"
    render = (tmp_path / ".github/workflows/render.yml").read_text()
    assert "project-type: manuscript" in render


def test_init_book_project_writes_book_quarto_yml(tmp_path):
    outcome = init_project(tmp_path, project_type="book")
    assert outcome.project_type == "book"
    cfg = yaml.safe_load((tmp_path / "_quarto.yml").read_text())
    assert cfg["project"]["type"] == "book"
    render = (tmp_path / ".github/workflows/render.yml").read_text()
    assert "project-type: book" in render


def test_init_auto_detects_book(tmp_path):
    (tmp_path / "_quarto.yml").write_text(yaml.safe_dump({"project": {"type": "book"}}))
    outcome = init_project(tmp_path, project_type="auto")
    assert outcome.project_type == "book"
    assert outcome.manual_merge_snippet is not None
    assert any(a.status == "manual-merge" and a.path.name == "_quarto.yml" for a in outcome.actions)


def test_init_does_not_overwrite_existing_files(tmp_path):
    files = {
        "_quarto.yml": "original yml\n",
        "references.bib": "@misc{orig, title={Original}}\n",
        "_version-banner.html.template": "original template\n",
        "_version-banner.html": "original banner\n",
        ".github/workflows/render.yml": "original workflow\n",
        ".github/workflows/pr-closed.yml": "original pr-closed\n",
    }
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    init_project(tmp_path)
    for rel, expected in files.items():
        assert (tmp_path / rel).read_text() == expected, f"{rel} was overwritten"


def test_init_is_idempotent(tmp_path):
    init_project(tmp_path)
    snapshot = {p: p.read_text() for p in tmp_path.rglob("*") if p.is_file()}
    init_project(tmp_path)
    for p, content in snapshot.items():
        assert p.read_text() == content, f"{p} changed on re-init"


def test_init_writes_pr_closed_workflow(tmp_path):
    init_project(tmp_path)
    pr_closed = (tmp_path / ".github/workflows/pr-closed.yml").read_text()
    assert "Clean up PR preview" in pr_closed
    assert "types: [closed]" in pr_closed


def test_gitignore_created_when_absent(tmp_path):
    action = _ensure_gitignore(tmp_path)
    assert action.status == "appended"
    content = (tmp_path / ".gitignore").read_text()
    assert "_freeze/" in content
    assert "_extensions/" in content


def test_gitignore_appends_only_missing_lines(tmp_path):
    (tmp_path / ".gitignore").write_text("existing\n_freeze/\nother\n")
    action = _ensure_gitignore(tmp_path)
    assert action.status == "appended"
    content = (tmp_path / ".gitignore").read_text()
    assert "existing" in content
    assert "other" in content
    assert content.count("_freeze/") == 1
    assert "_extensions/" in content


def test_gitignore_idempotent_when_all_present(tmp_path):
    _ensure_gitignore(tmp_path)
    action_second = _ensure_gitignore(tmp_path)
    assert action_second.status == "skipped-exists"


def test_format_emits_expected_glyphs(tmp_path):
    outcome = InitOutcome(
        project_type="manuscript",
        actions=[
            Action(path=tmp_path / "_quarto.yml", status="written"),
            Action(path=tmp_path / ".gitignore", status="appended", detail="2 lines"),
            Action(path=tmp_path / "references.bib", status="skipped-exists"),
        ],
    )
    out = format_outcome(outcome, project=tmp_path)
    assert "+ _quarto.yml" in out
    assert "~ .gitignore" in out
    assert "· references.bib" in out
    assert "manuscript" in out
    assert "quarto add" in out


def test_format_includes_manual_merge_snippet(tmp_path):
    outcome = InitOutcome(
        project_type="manuscript",
        manual_merge_snippet="# merge me\nfilters:\n  - quarto-manubot-cite\n",
        actions=[
            Action(path=tmp_path / "_quarto.yml", status="manual-merge"),
        ],
    )
    out = format_outcome(outcome, project=tmp_path)
    assert "merge me" in out


def test_cli_init_in_empty_dir(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["init", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "Next steps:" in result.output
    assert (tmp_path / "_quarto.yml").exists()


def test_cli_init_book_flag(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["init", str(tmp_path), "--project-type", "book"])
    assert result.exit_code == 0, result.output
    cfg = yaml.safe_load((tmp_path / "_quarto.yml").read_text())
    assert cfg["project"]["type"] == "book"


def test_cli_init_default_path_uses_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "_quarto.yml").exists()
