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


def test_scan_stub_exits_two():
    runner = CliRunner()
    result = runner.invoke(main, ["scan", "."])
    assert result.exit_code == 2
    assert "not yet" in result.output


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
