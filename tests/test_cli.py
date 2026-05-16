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
    assert "No matching files found" in result.output


def test_scan_no_recursive_stays_at_top(tmp_path):
    """`--no-recursive` skips subdirectories."""
    (tmp_path / "top.qmd").write_text("Top @doi:10.1/top.\n")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "deeper.qmd").write_text("Deeper @doi:10.1/deeper.\n")

    runner = CliRunner()
    result = runner.invoke(main, ["scan", "--no-recursive", str(tmp_path)])
    assert result.exit_code == 0
    assert "10.1/top" in result.output
    assert "10.1/deeper" not in result.output


def test_scan_exits_one_on_duplicates(tmp_path):
    (tmp_path / "a.qmd").write_text("See @doi:10.1371/journal.pcbi.1007128.\n")
    (tmp_path / "b.qmd").write_text("Also @doi:10.1371/journal.pcbi.1007128.\n")
    runner = CliRunner()
    result = runner.invoke(main, ["scan", str(tmp_path)])
    assert result.exit_code == 1
    assert "Duplicates:" in result.output


def test_resolve_no_args_exits_zero():
    """`resolve` with no keys and no --from-scan: clean exit, friendly message."""
    runner = CliRunner()
    result = runner.invoke(main, ["resolve"])
    assert result.exit_code == 0
    assert "No persistent-identifier" in result.output


def test_subcommands_listed_in_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    for sub in ("scan", "resolve", "validate"):
        assert sub in result.output


def test_resolve_normalizes_url_trailing_slash_on_explicit_keys(monkeypatch):
    """The explicit-key resolve path strips pandoc-trailing slashes
    on `url:` keys before they reach resolve_keys."""
    captured: dict = {}

    def fake_resolve_keys(keys, **kwargs):
        captured["keys"] = list(keys)
        captured["kwargs"] = kwargs

        class _Outcome:
            ok_count = len(keys)
            err_count = 0
            failures: list = []

        return _Outcome()

    def fake_format_outcome(outcome):
        return ""

    import quartobot.resolve as r

    monkeypatch.setattr(r, "resolve_keys", fake_resolve_keys)
    monkeypatch.setattr(r, "format_outcome", fake_format_outcome)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "resolve",
            "--id-mode",
            "citation-key",
            "@url:https://example.com/path/",
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured["keys"] == ["url:https://example.com/path"]
