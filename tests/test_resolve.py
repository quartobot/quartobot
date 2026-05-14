"""Tests for the resolve command and module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from quartobot.cli import main
from quartobot.resolve import (
    Resolution,
    ResolveOutcome,
    _build_cache_index,
    _load_existing,
    collect_resolvable_keys,
    format_outcome,
    resolve_keys,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample.qmd"


# ----------------------------------------------------------- helpers


class _FakeCiteKey:
    """Stand-in for manubot.cite.citekey.CiteKey for tests."""

    def __init__(self, raw: str, infer_prefix: bool = True) -> None:
        self.input_id = raw
        # Use the raw form as the standard_id — matches manubot for
        # well-formed `prefix:id` inputs.
        self.standard_id = raw


def _fake_csl_item(citekey, **_kwargs):
    """Stand-in for citekey_to_csl_item — return a deterministic stub."""
    sid = citekey.standard_id
    # Predictable short_id: first 4 chars of the identifier portion.
    after = sid.split(":", 1)[-1]
    short = after.replace("/", "").replace(".", "")[:8] or "shortid"
    return {
        "id": f"SHORT_{short}",
        "title": f"Stub for {sid}",
        "type": "article-journal",
        "note": f"standard_id: {sid}",
    }


# ----------------------------------------------------------- collect


def test_collect_only_persistent_ids(tmp_path):
    qmd = tmp_path / "doc.qmd"
    qmd.write_text(
        "Persistent: @doi:10.1/x and @pmid:99.\nHand-curated: @somekey — should be skipped.\n"
    )
    keys = collect_resolvable_keys(tmp_path)
    assert "doi:10.1/x" in keys
    assert "pmid:99" in keys
    assert "somekey" not in keys


def test_collect_dedupes_repeats(tmp_path):
    a = tmp_path / "a.qmd"
    b = tmp_path / "b.qmd"
    a.write_text("@doi:10.1/x\n")
    b.write_text("@doi:10.1/x repeated.\n")
    keys = collect_resolvable_keys(tmp_path)
    assert keys.count("doi:10.1/x") == 1


def test_collect_handles_bare_doi(tmp_path):
    qmd = tmp_path / "doc.qmd"
    qmd.write_text("Bare: @10.1038/abc.\n")
    keys = collect_resolvable_keys(tmp_path)
    # Bare DOI is classified under "doi" prefix.
    assert any(k.startswith("doi:10.1038/") for k in keys)


def test_collect_empty_project(tmp_path):
    assert collect_resolvable_keys(tmp_path) == []


# ----------------------------------------------------------- _load_existing + cache index


def test_load_existing_missing_returns_empty(tmp_path):
    assert _load_existing(tmp_path / "missing.json") == []


def test_load_existing_invalid_json_returns_empty(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("not json")
    assert _load_existing(p) == []


def test_load_existing_non_list_returns_empty(tmp_path):
    p = tmp_path / "obj.json"
    p.write_text('{"id": "x"}')
    assert _load_existing(p) == []


def test_load_existing_round_trip(tmp_path):
    p = tmp_path / "ok.json"
    items = [{"id": "abc"}, {"id": "def"}]
    p.write_text(json.dumps(items))
    assert _load_existing(p) == items


def test_build_cache_index_extracts_standard_id():
    items = [
        {"id": "abc", "note": "Some context\nstandard_id: doi:10.1/x"},
        {"id": "def", "note": "standard_id: pmid:99"},
    ]
    index = _build_cache_index(items)
    assert "doi:10.1/x" in index
    assert "pmid:99" in index


def test_build_cache_index_skips_entries_without_standard_id():
    items = [{"id": "abc", "note": "just a free-text note"}, {"id": "def"}]
    assert _build_cache_index(items) == {}


# ----------------------------------------------------------- resolve_keys


def test_resolve_dry_run_no_network():
    keys = ["doi:10.1/x", "pmid:99"]
    # Even though we don't pass a mock, dry_run shouldn't touch manubot.
    outcome = resolve_keys(keys, dry_run=True)
    assert len(outcome.successes) == 2
    assert all(r.short_id is None for r in outcome.successes)
    assert outcome.entries_written == 0


def test_resolve_writes_csl_json(tmp_path):
    out = tmp_path / "references.json"
    with (
        patch("manubot.cite.citekey.CiteKey", _FakeCiteKey),
        patch("manubot.cite.citekey.citekey_to_csl_item", _fake_csl_item),
    ):
        outcome = resolve_keys(
            ["doi:10.1/x", "pmid:99"],
            output_path=out,
            cache_path=out,
        )
    assert outcome.entries_written == 2
    data = json.loads(out.read_text())
    ids = sorted(item["id"] for item in data)
    assert ids == sorted(["SHORT_101x", "SHORT_99"])


def test_resolve_cache_hit_skips_resolution(tmp_path):
    # Pre-populate the output file with one entry.
    out = tmp_path / "references.json"
    out.write_text(
        json.dumps(
            [
                {"id": "SHORT_101x", "title": "Cached", "note": "standard_id: doi:10.1/x"},
            ]
        )
    )

    calls: list[str] = []

    def _track(citekey, **_):
        calls.append(citekey.standard_id)
        return _fake_csl_item(citekey)

    with (
        patch("manubot.cite.citekey.CiteKey", _FakeCiteKey),
        patch("manubot.cite.citekey.citekey_to_csl_item", _track),
    ):
        outcome = resolve_keys(
            ["doi:10.1/x", "pmid:99"],
            cache_path=out,
            output_path=out,
        )
    assert outcome.cache_hits == 1
    # Only the uncached key triggered a resolver call.
    assert calls == ["pmid:99"]


def test_resolve_records_failure(tmp_path):
    def _raises(citekey, **_):
        raise RuntimeError("crossref 404")

    with (
        patch("manubot.cite.citekey.CiteKey", _FakeCiteKey),
        patch("manubot.cite.citekey.citekey_to_csl_item", _raises),
    ):
        outcome = resolve_keys(["doi:10.1/missing"])
    assert len(outcome.failures) == 1
    assert outcome.failures[0].error == "crossref 404"


def test_resolve_records_resolver_returning_none(tmp_path):
    def _none(citekey, **_):
        return None

    with (
        patch("manubot.cite.citekey.CiteKey", _FakeCiteKey),
        patch("manubot.cite.citekey.citekey_to_csl_item", _none),
    ):
        outcome = resolve_keys(["doi:10.1/foo"])
    assert len(outcome.failures) == 1
    assert "None" in (outcome.failures[0].error or "")


def test_resolve_output_sorted_for_diff_stability(tmp_path):
    out = tmp_path / "references.json"
    with (
        patch("manubot.cite.citekey.CiteKey", _FakeCiteKey),
        patch("manubot.cite.citekey.citekey_to_csl_item", _fake_csl_item),
    ):
        resolve_keys(
            ["pmid:99", "doi:10.1/x"],  # input in non-alpha order
            output_path=out,
        )
    items = json.loads(out.read_text())
    ids = [item["id"] for item in items]
    assert ids == sorted(ids)


# ----------------------------------------------------------- format_outcome


def test_format_no_keys():
    outcome = ResolveOutcome()
    assert "No persistent-identifier" in format_outcome(outcome)


def test_format_lists_successes_and_failures():
    outcome = ResolveOutcome()
    outcome.resolutions = [
        Resolution(
            key="doi:10.1/x",
            standard_id="doi:10.1/x",
            short_id="ABC",
            succeeded=True,
        ),
        Resolution(
            key="doi:10.1/y",
            standard_id="doi:10.1/y",
            short_id=None,
            succeeded=False,
            error="404",
        ),
    ]
    outcome.entries_written = 1
    outcome.output_path = Path("references.json")
    out = format_outcome(outcome)
    assert "✓" in out
    assert "✗" in out
    assert "1 resolved" in out
    assert "1 failed" in out
    assert "references.json" in out


# ----------------------------------------------------------- CLI


def test_cli_no_keys_no_scan_exits_zero():
    runner = CliRunner()
    result = runner.invoke(main, ["resolve"])
    assert result.exit_code == 0
    assert "No persistent-identifier" in result.output


def test_cli_dry_run_does_not_write(tmp_path):
    qmd = tmp_path / "doc.qmd"
    qmd.write_text("Cite: @doi:10.1/x.\n")
    out = tmp_path / "references.json"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "resolve",
            "--from-scan",
            str(tmp_path),
            "--output",
            str(out),
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    assert not out.exists()


def test_cli_writes_output_file(tmp_path):
    qmd = tmp_path / "doc.qmd"
    qmd.write_text("Cite: @doi:10.1/x.\n")
    out = tmp_path / "references.json"

    with (
        patch("manubot.cite.citekey.CiteKey", _FakeCiteKey),
        patch("manubot.cite.citekey.citekey_to_csl_item", _fake_csl_item),
    ):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "resolve",
                "--from-scan",
                str(tmp_path),
                "--output",
                str(out),
            ],
        )
    assert result.exit_code == 0, result.output
    assert out.exists()
    data = json.loads(out.read_text())
    assert len(data) == 1


def test_cli_strips_leading_at():
    """`quartobot resolve @doi:10.1/x` should work the same as `doi:10.1/x`."""
    with (
        patch("manubot.cite.citekey.CiteKey", _FakeCiteKey),
        patch("manubot.cite.citekey.citekey_to_csl_item", _fake_csl_item),
    ):
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["resolve", "@doi:10.1/x"])
    assert result.exit_code == 0, result.output


def test_cli_exits_one_on_failure(tmp_path):
    def _raises(citekey, **_):
        raise RuntimeError("nope")

    with (
        patch("manubot.cite.citekey.CiteKey", _FakeCiteKey),
        patch("manubot.cite.citekey.citekey_to_csl_item", _raises),
    ):
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["resolve", "doi:10.1/missing"])
    assert result.exit_code == 1
