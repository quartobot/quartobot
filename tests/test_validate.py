"""Tests for the validate command and module."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from quartobot.cli import main
from quartobot.validate import (
    DEFAULT_EXTENSION_DIR,
    Check,
    ValidateOutcome,
    _check_bibliography_declared,
    _check_extension_installed,
    _check_manubot_cache,
    _check_manubot_output_matches_bibliography,
    _check_no_duplicate_cites,
    _check_quarto_yml_exists,
    _load_quarto_yml,
    format_outcome,
    validate_project,
)


def _make_project(
    tmp_path: Path,
    *,
    extension: bool = True,
    quarto_yml: object = "ok",
    qmd_content: str = "Some prose.\n",
) -> Path:
    """Build a small Quarto project tree under tmp_path."""
    if extension:
        ext_dir = tmp_path / DEFAULT_EXTENSION_DIR
        ext_dir.mkdir(parents=True, exist_ok=True)
        (ext_dir / "_extension.yml").write_text("title: quarto-manubot-cite\n")

    if quarto_yml == "ok":
        import yaml

        cfg = {
            "filters": ["quarto-manubot-cite"],
            "bibliography": ["references.bib", "references.json"],
            "manubot-bibliography-cache": "_freeze/manubot-cache.json",
            "manubot-output-bibliography": "references.json",
        }
        (tmp_path / "_quarto.yml").write_text(yaml.safe_dump(cfg))
    elif isinstance(quarto_yml, dict):
        import yaml

        (tmp_path / "_quarto.yml").write_text(yaml.safe_dump(quarto_yml))
    elif quarto_yml == "broken":
        (tmp_path / "_quarto.yml").write_text("not: valid: yaml: at all\n: : :")
    elif quarto_yml is None:
        pass

    (tmp_path / "index.qmd").write_text(qmd_content)
    return tmp_path


def test_load_missing_yml(tmp_path):
    assert _load_quarto_yml(tmp_path) is None


def test_load_broken_yml(tmp_path):
    (tmp_path / "_quarto.yml").write_text("not: valid: yaml: at all\n: : :")
    assert _load_quarto_yml(tmp_path) is None


def test_load_non_mapping_yml(tmp_path):
    (tmp_path / "_quarto.yml").write_text("- a\n- b\n")
    assert _load_quarto_yml(tmp_path) is None


def test_load_ok_yml(tmp_path):
    (tmp_path / "_quarto.yml").write_text("title: ok\n")
    assert _load_quarto_yml(tmp_path) == {"title": "ok"}


def test_extension_installed_pass(tmp_path):
    _make_project(tmp_path)
    c = _check_extension_installed(tmp_path)
    assert c.passed


def test_extension_not_installed(tmp_path):
    _make_project(tmp_path, extension=False)
    c = _check_extension_installed(tmp_path)
    assert not c.passed
    assert "quarto add" in (c.detail or "")


def test_quarto_yml_exists(tmp_path):
    _make_project(tmp_path)
    c = _check_quarto_yml_exists(tmp_path)
    assert c.passed


def test_quarto_yml_missing(tmp_path):
    _make_project(tmp_path, quarto_yml=None)
    c = _check_quarto_yml_exists(tmp_path)
    assert not c.passed


def test_bibliography_declared_as_list():
    cfg = {"bibliography": ["references.bib", "references.json"]}
    c = _check_bibliography_declared(cfg)
    assert c.passed


def test_bibliography_declared_as_string():
    cfg = {"bibliography": "references.bib"}
    c = _check_bibliography_declared(cfg)
    assert c.passed


def test_bibliography_missing():
    c = _check_bibliography_declared({})
    assert not c.passed


def test_bibliography_garbage_type():
    c = _check_bibliography_declared({"bibliography": 42})
    assert not c.passed


def test_manubot_cache_set():
    c = _check_manubot_cache({"manubot-bibliography-cache": "_freeze/manubot-cache.json"})
    assert c.passed


def test_manubot_cache_missing():
    c = _check_manubot_cache({})
    assert not c.passed


def test_manubot_output_in_bibliography():
    cfg = {
        "bibliography": ["references.bib", "references.json"],
        "manubot-output-bibliography": "references.json",
    }
    c = _check_manubot_output_matches_bibliography(cfg)
    assert c.passed


def test_manubot_output_not_in_bibliography():
    cfg = {
        "bibliography": ["references.bib"],
        "manubot-output-bibliography": "references.json",
    }
    c = _check_manubot_output_matches_bibliography(cfg)
    assert not c.passed
    assert "Citeproc won't" in (c.detail or "")


def test_manubot_output_missing():
    c = _check_manubot_output_matches_bibliography({})
    assert not c.passed


def test_no_dup_cites_clean(tmp_path):
    _make_project(tmp_path, qmd_content="One @doi:10.1/x cite.\n")
    c = _check_no_duplicate_cites(tmp_path)
    assert c.passed


def test_duplicate_cites_flagged(tmp_path):
    p = _make_project(tmp_path, qmd_content="See @doi:10.1/x.\n")
    (p / "other.qmd").write_text("Also @doi:10.1/x.\n")
    c = _check_no_duplicate_cites(p)
    assert not c.passed
    assert "appear in multiple" in (c.detail or "")


def test_validate_happy_path(tmp_path):
    _make_project(tmp_path, qmd_content="Cite @doi:10.1371/journal.pcbi.1007128.\n")
    outcome = validate_project(tmp_path)
    assert outcome.passed, outcome.failures
    assert len(outcome.checks) == 6


def test_validate_missing_extension(tmp_path):
    _make_project(tmp_path, extension=False)
    outcome = validate_project(tmp_path)
    assert not outcome.passed
    names = [c.name for c in outcome.failures]
    assert "extension installed" in names


def test_validate_missing_cache_key(tmp_path):
    cfg = {
        "bibliography": ["references.bib", "references.json"],
        "manubot-output-bibliography": "references.json",
    }
    _make_project(tmp_path, quarto_yml=cfg)
    outcome = validate_project(tmp_path)
    assert not outcome.passed
    assert "manubot-bibliography-cache" in [c.name for c in outcome.failures]


def test_validate_output_not_in_bibliography(tmp_path):
    cfg = {
        "bibliography": ["references.bib"],
        "manubot-bibliography-cache": "_freeze/cache.json",
        "manubot-output-bibliography": "references.json",
    }
    _make_project(tmp_path, quarto_yml=cfg)
    outcome = validate_project(tmp_path)
    assert not outcome.passed
    assert "manubot-output-bibliography" in [c.name for c in outcome.failures]


def test_validate_no_quarto_yml(tmp_path):
    _make_project(tmp_path, quarto_yml=None)
    outcome = validate_project(tmp_path)
    assert not outcome.passed
    assert "_quarto.yml exists" in [c.name for c in outcome.failures]
    # Config checks skipped when _quarto.yml is missing.
    assert len(outcome.checks) == 3


def test_validate_broken_yml(tmp_path):
    _make_project(tmp_path, quarto_yml="broken")
    outcome = validate_project(tmp_path)
    assert not outcome.passed
    assert "_quarto.yml parses as YAML" in [c.name for c in outcome.failures]


def test_format_all_passing():
    outcome = ValidateOutcome(
        checks=[
            Check(name="a", passed=True),
            Check(name="b", passed=True, detail="extra info"),
        ]
    )
    out = format_outcome(outcome)
    assert "✓ a" in out
    assert "✓ b — extra info" in out
    assert "All 2 check(s) passed" in out


def test_format_with_failure():
    outcome = ValidateOutcome(
        checks=[
            Check(name="a", passed=True),
            Check(name="b", passed=False, detail="broken"),
        ]
    )
    out = format_outcome(outcome)
    assert "✗ b — broken" in out
    assert "1 of 2 check(s) failed" in out


def test_cli_happy_path_exits_zero(tmp_path):
    _make_project(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(tmp_path)])
    assert result.exit_code == 0, result.output


def test_cli_failure_exits_one(tmp_path):
    _make_project(tmp_path, extension=False)
    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(tmp_path)])
    assert result.exit_code == 1
    assert "✗ extension installed" in result.output
