"""Smoke tests for the CLI surface."""

from __future__ import annotations

from click.testing import CliRunner

from quartobot import __version__
from quartobot.cli import main


def test_help_runs():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "manuscript-as-software, on Quarto" in result.output


def test_version_reports_package_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_scan_runs_on_empty_dir(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["scan", str(tmp_path)])
    assert result.exit_code == 0
    assert "No .qmd or .md files found" in result.output


def test_scan_exits_one_on_duplicates(tmp_path):
    (tmp_path / "a.qmd").write_text("See @doi:10.1371/journal.pcbi.1007128.\n")
    (tmp_path / "b.qmd").write_text("Also @doi:10.1371/journal.pcbi.1007128.\n")
    runner = CliRunner()
    result = runner.invoke(main, ["scan", str(tmp_path)])
    assert result.exit_code == 1
    assert "Duplicates:" in result.output


def test_resolve_stub_exits_two():
    runner = CliRunner()
    result = runner.invoke(main, ["resolve"])
    assert result.exit_code == 2


def test_validate_stub_exits_two(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(tmp_path)])
    assert result.exit_code == 2


def test_subcommands_listed_in_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    for sub in ("scan", "resolve", "validate"):
        assert sub in result.output
