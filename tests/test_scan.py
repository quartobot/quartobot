"""Tests for the scan command."""

from __future__ import annotations

from pathlib import Path

import pytest

from quartobot.scan import (
    EXCLUDED_DIRS,
    CiteOccurrence,
    ScanResult,
    classify,
    collect_files,
    find_cite_keys,
    format_scan_result,
    scan_path,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample.qmd"


# ---------------------------------------------------------------- classify


@pytest.mark.parametrize(
    ("key", "expected_prefix", "expected_id"),
    [
        ("@doi:10.1371/journal.pcbi.1007128", "doi", "10.1371/journal.pcbi.1007128"),
        ("@pmid:31479462", "pmid", "31479462"),
        ("@pmcid:PMC6735409", "pmcid", "PMC6735409"),
        ("@arxiv:2104.10729", "arxiv", "2104.10729"),
        ("@isbn:9780262035613", "isbn", "9780262035613"),
        ("@url:https://manubot.org", "url", "https://manubot.org"),
        ("@wikidata:Q56458094", "wikidata", "Q56458094"),
        ("@10.1038/s41586-024-12345", "doi", "10.1038/s41586-024-12345"),
        ("@quarto2024", None, "quarto2024"),
        ("@himmelstein-2019", None, "himmelstein-2019"),
    ],
)
def test_classify(key, expected_prefix, expected_id):
    prefix, identifier = classify(key)
    assert prefix == expected_prefix
    assert identifier == expected_id


def test_unknown_prefix_treated_as_hand_curated():
    # `@foo:bar` with an unknown prefix is treated as hand-curated.
    prefix, _ = classify("@madeupthing:abc")
    assert prefix is None


@pytest.mark.parametrize(
    ("raw_line", "expected_key"),
    [
        ("Sentence-ending @doi:10.1371/foo.\n", "@doi:10.1371/foo"),
        ("Comma after: @pmid:123, more.\n", "@pmid:123"),
        ("Semicolon: @arxiv:2104.10729;\n", "@arxiv:2104.10729"),
        ("Parens: (see @quarto2024).\n", "@quarto2024"),
        ("Question? @doi:10.1/x?\n", "@doi:10.1/x"),
    ],
)
def test_trailing_punctuation_stripped(raw_line, expected_key):
    found = [key for key, _ in find_cite_keys(raw_line)]
    assert expected_key in found
    # The punctuation-laden form should NOT appear.
    for punct in ".,;:!?)":
        assert expected_key + punct not in found


# ----------------------------------------------------------- find_cite_keys


def test_find_cite_keys_simple():
    text = "See @doi:10.1371/foo and @pmid:123.\n"
    found = list(find_cite_keys(text))
    assert ("@doi:10.1371/foo", 1) in found
    assert ("@pmid:123", 1) in found


def test_skips_multi_backtick_inline_code():
    # Pandoc allows multi-backtick inline code spans (for content that
    # itself contains backticks). Cite keys inside double/triple-tick
    # spans should be stripped just like single-tick.
    text = "Double: ``@doi:10.1371/double``; triple: ```@doi:10.1371/triple```.\n"
    assert list(find_cite_keys(text)) == []


def test_url_cite_with_query_string():
    text = "Source: @url:https://example.com/page?q=foo&n=1.\n"
    keys = [key for key, _ in find_cite_keys(text)]
    # The whole URL — including query string — should survive as one key.
    assert "@url:https://example.com/page?q=foo&n=1" in keys


def test_skips_email_addresses():
    text = "Contact you@example.com about this.\n"
    assert list(find_cite_keys(text)) == []


def test_skips_inline_code():
    text = "Use `@doi:10.1371/inline` in code.\n"
    assert list(find_cite_keys(text)) == []


def test_skips_fenced_code_block():
    text = (
        "Prose with @doi:10.1371/real.\n"
        "```\n"
        "@doi:10.1371/fenced_should_skip\n"
        "```\n"
        "More prose with @pmid:123.\n"
    )
    found = [key for key, _ in find_cite_keys(text)]
    assert "@doi:10.1371/real" in found
    assert "@pmid:123" in found
    assert "@doi:10.1371/fenced_should_skip" not in found


def test_skips_tilde_fenced_code_block():
    text = "Real: @doi:10.1371/yes.\n~~~\n@doi:10.1371/tilde_fenced_no\n~~~\n"
    found = [key for key, _ in find_cite_keys(text)]
    assert "@doi:10.1371/yes" in found
    assert "@doi:10.1371/tilde_fenced_no" not in found


def test_skips_yaml_frontmatter():
    text = (
        "---\n"
        "title: A paper\n"
        "bibliography:\n"
        "  - references.bib\n"
        "---\n"
        "\n"
        "Body with @doi:10.1371/real.\n"
    )
    found = list(find_cite_keys(text))
    assert ("@doi:10.1371/real", 7) in found
    # Make sure nothing from the frontmatter leaked through.
    assert all(line >= 6 for _, line in found)


def test_skips_toml_frontmatter():
    text = "+++\ntitle = 'A paper'\n+++\n\n@doi:10.1371/real\n"
    found = list(find_cite_keys(text))
    assert len(found) == 1
    assert found[0] == ("@doi:10.1371/real", 5)


def test_multi_cite_bracket_group():
    text = "See [@doi:10.1371/a; @pmid:123; @quarto2024].\n"
    found = [key for key, _ in find_cite_keys(text)]
    assert "@doi:10.1371/a" in found
    assert "@pmid:123" in found
    assert "@quarto2024" in found


def test_negated_cite_still_picked_up():
    # [-@key] is a pandoc cite that suppresses the author name. The `-`
    # is non-alphanumeric so the boundary regex still matches.
    text = "See [-@doi:10.1371/x].\n"
    found = [key for key, _ in find_cite_keys(text)]
    assert "@doi:10.1371/x" in found


def test_line_numbers():
    text = "line 1\nline 2 has @doi:10.1371/x\nline 3\nline 4 has @pmid:99.\n"
    found = list(find_cite_keys(text))
    assert ("@doi:10.1371/x", 2) in found
    assert ("@pmid:99", 4) in found


# ----------------------------------------------------------- collect_files


def test_collect_files_recursive(tmp_path):
    (tmp_path / "a.qmd").write_text("")
    (tmp_path / "b.md").write_text("")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.qmd").write_text("")
    (tmp_path / "not-markdown.txt").write_text("")

    files = list(collect_files(tmp_path))
    names = sorted(f.name for f in files)
    assert names == ["a.qmd", "b.md", "c.qmd"]


def test_collect_files_skips_excluded_dirs(tmp_path):
    (tmp_path / "real.qmd").write_text("")
    excluded = tmp_path / "_freeze"
    excluded.mkdir()
    (excluded / "should_skip.qmd").write_text("")

    files = list(collect_files(tmp_path))
    names = [f.name for f in files]
    assert "real.qmd" in names
    assert "should_skip.qmd" not in names


def test_collect_files_skips_all_known_excluded_dirs(tmp_path):
    for excluded_name in EXCLUDED_DIRS:
        sub = tmp_path / excluded_name
        sub.mkdir()
        (sub / "f.qmd").write_text("")
    (tmp_path / "real.qmd").write_text("")

    files = list(collect_files(tmp_path))
    assert [f.name for f in files] == ["real.qmd"]


def test_collect_files_single_file(tmp_path):
    target = tmp_path / "single.qmd"
    target.write_text("")
    files = list(collect_files(target))
    assert files == [target]


def test_collect_files_non_markdown_file_returns_empty(tmp_path):
    target = tmp_path / "single.txt"
    target.write_text("")
    files = list(collect_files(target))
    assert files == []


# ---------------------------------------------------------------- scan_path


def test_scan_empty_dir(tmp_path):
    result = scan_path(tmp_path)
    assert result.files_scanned == 0
    assert result.occurrences == []
    assert result.unique_keys == set()


def test_scan_finds_all_fixture_citations():
    result = scan_path(FIXTURE)
    assert result.files_scanned == 1
    keys = result.unique_keys
    # Persistent-identifier citations the fixture declares in prose:
    assert "@doi:10.1371/journal.pcbi.1007128" in keys
    assert "@pmid:31479462" in keys
    assert "@arxiv:2104.10729" in keys
    assert "@isbn:9780262035613" in keys
    assert "@10.1038/s41586-024-12345" in keys
    assert "@quarto2024" in keys
    assert "@pmid:99999999" in keys
    assert "@url:https://manubot.org" in keys
    assert "@wikidata:Q56458094" in keys


def test_scan_skips_fixture_decoys():
    result = scan_path(FIXTURE)
    keys = result.unique_keys
    # Email address — should not be a cite key.
    assert not any("example.com" in k for k in keys)
    # Inline code.
    assert "@doi:10.1371/inline_should_be_skipped" not in keys
    # Fenced code blocks.
    assert "@doi:10.1371/inline_2" not in keys
    assert "@doi:10.1371/fenced_should_be_skipped" not in keys
    assert "@doi:10.1371/tilde_fence_should_be_skipped" not in keys
    # Frontmatter bibliography line — `references.bib` shouldn't be a key.
    assert not any("references" in k.lower() for k in keys)


def test_scan_detects_fixture_duplicate():
    result = scan_path(FIXTURE)
    # The manubot paper DOI appears in prose AND in the bracket group AND
    # in the negated cite — three occurrences.
    dup = result.duplicates
    assert "@doi:10.1371/journal.pcbi.1007128" in dup
    assert len(dup["@doi:10.1371/journal.pcbi.1007128"]) >= 3


def test_scan_groups_by_prefix():
    result = scan_path(FIXTURE)
    by_prefix = result.by_prefix
    assert "doi" in by_prefix
    assert "pmid" in by_prefix
    assert "arxiv" in by_prefix
    assert "isbn" in by_prefix
    assert "url" in by_prefix
    assert "wikidata" in by_prefix
    assert "(hand-curated)" in by_prefix


def test_scan_classifies_bare_doi_under_doi():
    result = scan_path(FIXTURE)
    doi_keys = {occ.key for occ in result.by_prefix["doi"]}
    # The bare DOI @10.1038/... is grouped under "doi"
    assert "@10.1038/s41586-024-12345" in doi_keys


def test_scan_skips_excluded_dirs(tmp_path):
    (tmp_path / "real.qmd").write_text("Real: @doi:10.1371/yes.\n")
    excluded = tmp_path / "_freeze"
    excluded.mkdir()
    (excluded / "cached.qmd").write_text("Cached: @doi:10.1371/no.\n")

    result = scan_path(tmp_path)
    keys = result.unique_keys
    assert "@doi:10.1371/yes" in keys
    assert "@doi:10.1371/no" not in keys


# ------------------------------------------------------- format_scan_result


def test_format_empty():
    assert format_scan_result(ScanResult()) == "No .qmd or .md files found."


def test_format_no_citations():
    out = format_scan_result(ScanResult(files_scanned=3))
    assert "No citations found" in out


def test_format_includes_summary_line(tmp_path):
    result = scan_path(FIXTURE)
    out = format_scan_result(result)
    assert "unique key" in out
    assert "total occurrence" in out


def test_format_groups_hand_curated_last():
    occurrences = [
        CiteOccurrence("@hand", Path("a"), 1, None, "hand"),
        CiteOccurrence("@doi:10.1/x", Path("a"), 2, "doi", "10.1/x"),
    ]
    out = format_scan_result(ScanResult(occurrences=occurrences, files_scanned=1))
    # `doi:` should appear before `(hand-curated):` in the output.
    assert out.index("doi:") < out.index("(hand-curated)")


def test_format_lists_duplicates(tmp_path):
    a = tmp_path / "a.qmd"
    b = tmp_path / "b.qmd"
    a.write_text("@doi:10.1/x\n")
    b.write_text("@doi:10.1/x\n")
    result = scan_path(tmp_path)
    out = format_scan_result(result, relative_to=tmp_path)
    assert "Duplicates:" in out
    assert "a.qmd:1" in out
    assert "b.qmd:1" in out
