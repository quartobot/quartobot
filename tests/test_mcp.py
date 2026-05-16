"""Tests for the MCP server wrappers.

The MCP SDK isn't a base dependency, so the whole module is skipped
when `mcp` isn't installed. CI's `dev` extra pulls it in, so these
tests run on every PR; a user without the extra can still run the
rest of the test suite without spurious failures.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

pytest.importorskip("mcp", reason="quartobot[mcp] extra not installed")

# Imports below depend on the importorskip above passing.
from quartobot import mcp as mcp_module
from quartobot.cli import main


def test_three_tools_register():
    """The server registers exactly the three documented tools."""
    tools = {t.name for t in mcp_module.server._tool_manager.list_tools()}
    assert tools == {"resolve_citation", "scan_project", "validate_project"}


def test_resolve_citation_returns_error_dict_on_unresolvable_key(monkeypatch):
    """A failed resolution surfaces as `{"error": ..., "cite_key": ...}` instead
    of raising — the agent sees a usable response, the server stays up."""

    def fake_resolver(key):
        raise RuntimeError("boom: simulated registrar timeout")

    monkeypatch.setattr("manubot.cite.citekey_to_csl_item", fake_resolver)

    result = mcp_module.resolve_citation("@url:https://example.com/x/")
    assert "error" in result
    # The leading @ and trailing slash were normalized before hitting the resolver.
    assert result["cite_key"] == "url:https://example.com/x"


def test_scan_project_returns_inventory(tmp_path: Path):
    """`scan_project` returns the same data the CLI scan does, as plain dicts."""
    (tmp_path / "a.qmd").write_text(
        "Cite once: @doi:10.1371/journal.pcbi.1007128.\n"
        "Cite again: @doi:10.1371/journal.pcbi.1007128.\n"
    )
    (tmp_path / "b.qmd").write_text("Different paper: @pmid:31479462.\n")

    result = mcp_module.scan_project(str(tmp_path))

    assert result["files_scanned"] == 2
    assert set(result["by_prefix"].keys()) == {"doi", "pmid"}

    # Same-file repetition shows up in `repetitions`, NOT in `duplicates`
    # (cross-file only) — matches the contract validate uses.
    assert "@doi:10.1371/journal.pcbi.1007128" in result["repetitions"]
    assert "@doi:10.1371/journal.pcbi.1007128" not in result["duplicates"]


def test_validate_project_returns_check_summary(tmp_path: Path):
    """`validate_project` returns `{passed, checks, failures}` as plain dicts.

    The project here has no `_quarto.yml`, so at least one check fails —
    enough to exercise the `passed` and `failures` paths without locking
    the test to a specific failure count.
    """
    result = mcp_module.validate_project(str(tmp_path))

    assert result["passed"] is False
    assert isinstance(result["checks"], list)
    assert len(result["checks"]) >= 1
    assert all(set(c.keys()) == {"name", "passed", "detail"} for c in result["checks"])
    assert all(not c["passed"] for c in result["failures"])


def test_cli_mcp_command_registered():
    """`quartobot mcp --help` is discoverable from the CLI surface."""
    runner = CliRunner()
    result = runner.invoke(main, ["mcp", "--help"])
    assert result.exit_code == 0
    assert "MCP server" in result.output or "mcp" in result.output.lower()


def test_cli_mcp_command_install_hint_when_extra_missing(monkeypatch):
    """When the `mcp` extra isn't installed, the subcommand prints an
    install hint instead of bubbling up `ModuleNotFoundError`."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "quartobot.mcp" or name.startswith("quartobot.mcp."):
            raise ImportError("simulated missing mcp extra")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    runner = CliRunner()
    result = runner.invoke(main, ["mcp"])
    assert result.exit_code != 0
    assert "quartobot[mcp]" in result.output
