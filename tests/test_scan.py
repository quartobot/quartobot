"""Tests for the scan command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quartobot.scan import (
    EXCLUDED_DIRS,
    CiteOccurrence,
    ScanResult,
    classify,
    collect_files,
    find_cite_keys,
    find_cite_keys_in_notebook,
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


# Pandoc's cite-key parser treats trailing `/` as terminator punctuation
# and drops it during parse. Without matching that here, the resolver
# writes `id: url:.../path/` into references.json while pandoc-citeproc
# looks up `url:.../path` — the citation silently degrades. See #61.
@pytest.mark.parametrize(
    ("raw_line", "expected_key"),
    [
        (
            "See [@url:https://www.ga4gh.org/about-us/strategic-road-map/].\n",
            "@url:https://www.ga4gh.org/about-us/strategic-road-map",
        ),
        (
            "Also [@url:https://www.ncbi.nlm.nih.gov/books/NBK562708/].\n",
            "@url:https://www.ncbi.nlm.nih.gov/books/NBK562708",
        ),
        (
            "Many slashes: @url:https://example.com/a/b/c/.\n",
            "@url:https://example.com/a/b/c",
        ),
        # Trailing slash followed by a sentence-ending period: both go.
        (
            "Period after: @url:https://example.com/path/.\n",
            "@url:https://example.com/path",
        ),
        # Trailing slash followed by other terminator punct.
        (
            "Comma: @url:https://example.com/path/, next.\n",
            "@url:https://example.com/path",
        ),
    ],
)
def test_url_trailing_slash_stripped(raw_line, expected_key):
    found = [key for key, _ in find_cite_keys(raw_line)]
    assert expected_key in found
    # The slash-bearing form should NOT appear.
    assert expected_key + "/" not in found


def test_url_without_trailing_slash_unchanged():
    # No-op case: a url: key with no trailing punctuation passes through.
    text = "Source: @url:https://example.com.\n"
    keys = [key for key, _ in find_cite_keys(text)]
    assert "@url:https://example.com" in keys


def test_url_internal_slashes_preserved():
    # Only *trailing* slashes are stripped; internal slashes are part
    # of the URL path and stay.
    text = "Source: @url:https://example.com/a/b/c.\n"
    keys = [key for key, _ in find_cite_keys(text)]
    assert "@url:https://example.com/a/b/c" in keys


def test_doi_trailing_slash_not_stripped():
    # The slash-stripping is scoped to `url:` keys. DOIs and other
    # prefixes keep any trailing slash the regex captured — those
    # aren't normal in prose, and we don't want to surprise users.
    text = "Cite @doi:10.1/x/ here.\n"
    keys = [key for key, _ in find_cite_keys(text)]
    assert "@doi:10.1/x/" in keys


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
    out = format_scan_result(ScanResult())
    assert "No matching files found" in out
    # Lists the supported suffixes so users know what we look for.
    assert ".ipynb" in out
    assert ".qmd" in out


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


# ------------------------------------------------------- jupyter notebooks


def _notebook(*cells: dict) -> str:
    """Return JSON text for a minimal nbformat-4 notebook."""
    return json.dumps(
        {
            "cells": list(cells),
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 5,
        }
    )


def _markdown_cell(source):
    return {"cell_type": "markdown", "metadata": {}, "source": source}


def _code_cell(source):
    return {
        "cell_type": "code",
        "metadata": {},
        "source": source,
        "execution_count": None,
        "outputs": [],
    }


def _raw_cell(source):
    return {"cell_type": "raw", "metadata": {}, "source": source}


def test_notebook_markdown_cell_basic():
    text = _notebook(_markdown_cell(["Cite @doi:10.1/x here.\n"]))
    hits = list(find_cite_keys_in_notebook(text))
    assert hits == [("@doi:10.1/x", 1, 1)]


def test_notebook_source_as_string_or_list_equivalent():
    string_form = _notebook(_markdown_cell("Cite @doi:10.1/x.\nNext line.\n"))
    list_form = _notebook(_markdown_cell(["Cite @doi:10.1/x.\n", "Next line.\n"]))
    assert list(find_cite_keys_in_notebook(string_form)) == list(
        find_cite_keys_in_notebook(list_form)
    )


def test_notebook_skips_code_and_raw_cells():
    text = _notebook(
        _code_cell("# Code: @doi:10.1/code is in a code cell\n"),
        _markdown_cell(["See @doi:10.1/md.\n"]),
        _raw_cell(["Raw: @doi:10.1/raw should also be skipped\n"]),
    )
    hits = list(find_cite_keys_in_notebook(text))
    # Only the markdown cell contributes.
    assert hits == [("@doi:10.1/md", 2, 1)]


def test_notebook_cell_index_is_1_based_across_all_cells():
    # Cells: [code, markdown, code, markdown]. The two markdown cells
    # are at notebook positions 2 and 4.
    text = _notebook(
        _code_cell("x = 1\n"),
        _markdown_cell(["First: @doi:10.1/a.\n"]),
        _code_cell("y = 2\n"),
        _markdown_cell(["Second: @doi:10.1/b.\n"]),
    )
    hits = list(find_cite_keys_in_notebook(text))
    assert hits == [("@doi:10.1/a", 2, 1), ("@doi:10.1/b", 4, 1)]


def test_notebook_line_within_cell_is_1_based():
    text = _notebook(
        _markdown_cell(
            [
                "# Header\n",
                "\n",
                "Body has @doi:10.1/x here.\n",
                "\n",
                "Then @pmid:42 down here.\n",
            ]
        )
    )
    hits = list(find_cite_keys_in_notebook(text))
    assert hits == [("@doi:10.1/x", 1, 3), ("@pmid:42", 1, 5)]


def test_notebook_fenced_code_inside_markdown_cell_skipped():
    text = _notebook(
        _markdown_cell(
            [
                "Real: @doi:10.1/real.\n",
                "```\n",
                "@doi:10.1/inside_fence ignored\n",
                "```\n",
                "After: @doi:10.1/after.\n",
            ]
        )
    )
    hits = list(find_cite_keys_in_notebook(text))
    keys = [h[0] for h in hits]
    assert "@doi:10.1/real" in keys
    assert "@doi:10.1/after" in keys
    assert "@doi:10.1/inside_fence" not in keys


def test_notebook_malformed_json_yields_nothing():
    # Garbled JSON shouldn't crash the scanner; it just contributes no hits.
    assert list(find_cite_keys_in_notebook("{not valid json")) == []


def test_notebook_missing_cells_key_yields_nothing():
    text = json.dumps({"metadata": {}, "nbformat": 4})
    assert list(find_cite_keys_in_notebook(text)) == []


def test_notebook_top_level_not_a_dict_yields_nothing():
    assert list(find_cite_keys_in_notebook(json.dumps(["just", "a", "list"]))) == []


def test_notebook_cell_source_missing_yields_nothing():
    text = _notebook({"cell_type": "markdown", "metadata": {}})
    assert list(find_cite_keys_in_notebook(text)) == []


def test_scan_path_includes_notebook_files(tmp_path):
    nb = tmp_path / "paper.ipynb"
    nb.write_text(_notebook(_markdown_cell(["Cite @doi:10.1/x.\n"])))
    qmd = tmp_path / "intro.qmd"
    qmd.write_text("Also cite @doi:10.1/x.\n")

    result = scan_path(tmp_path)
    assert result.files_scanned == 2
    # The notebook occurrence carries a cell index; the qmd one doesn't.
    notebook_occ = [o for o in result.occurrences if o.file == nb]
    qmd_occ = [o for o in result.occurrences if o.file == qmd]
    assert len(notebook_occ) == 1
    assert notebook_occ[0].cell == 1
    assert notebook_occ[0].line == 1
    assert len(qmd_occ) == 1
    assert qmd_occ[0].cell is None


def test_format_duplicates_renders_notebook_cell(tmp_path):
    nb = tmp_path / "paper.ipynb"
    nb.write_text(_notebook(_markdown_cell(["Cite @doi:10.1/x.\n"])))
    qmd = tmp_path / "other.qmd"
    qmd.write_text("Also @doi:10.1/x.\n")
    result = scan_path(tmp_path)
    out = format_scan_result(result, relative_to=tmp_path)
    assert "Duplicates:" in out
    assert "paper.ipynb:cell1:1" in out
    assert "other.qmd:1" in out


# ------------------------------------------------------- Rmd files


def test_scan_includes_rmd_files(tmp_path):
    rmd = tmp_path / "analysis.Rmd"
    rmd.write_text("R Markdown citing @doi:10.1/rmd.\n")
    result = scan_path(tmp_path)
    assert result.files_scanned == 1
    assert "@doi:10.1/rmd" in result.unique_keys


# ------------------------------------------------------- new excluded dirs


@pytest.mark.parametrize("excluded_name", ["_book", "_manuscript", ".ipynb_checkpoints"])
def test_collect_files_skips_added_excluded_dirs(tmp_path, excluded_name):
    sub = tmp_path / excluded_name
    sub.mkdir()
    (sub / "skip.qmd").write_text("Should be skipped: @doi:10.1/skip.\n")
    (tmp_path / "real.qmd").write_text("Real: @doi:10.1/real.\n")

    result = scan_path(tmp_path)
    keys = result.unique_keys
    assert "@doi:10.1/real" in keys
    assert "@doi:10.1/skip" not in keys


# ------------------------------------------------------- recursive flag


def test_collect_files_recursive_default_descends(tmp_path):
    deep = tmp_path / "sub" / "deeper"
    deep.mkdir(parents=True)
    (deep / "buried.qmd").write_text("Buried: @doi:10.1/buried.\n")
    (tmp_path / "top.qmd").write_text("Top: @doi:10.1/top.\n")

    files = sorted(f.name for f in collect_files(tmp_path))
    assert files == ["buried.qmd", "top.qmd"]


def test_collect_files_non_recursive_stays_at_top(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "deeper.qmd").write_text("Deep.\n")
    (tmp_path / "top.qmd").write_text("Top.\n")

    files = list(collect_files(tmp_path, recursive=False))
    assert [f.name for f in files] == ["top.qmd"]


def test_scan_path_non_recursive_skips_subdirs(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "deeper.qmd").write_text("Deeper: @doi:10.1/deeper.\n")
    (tmp_path / "top.qmd").write_text("Top: @doi:10.1/top.\n")

    result = scan_path(tmp_path, recursive=False)
    keys = result.unique_keys
    assert "@doi:10.1/top" in keys
    assert "@doi:10.1/deeper" not in keys


def test_strip_pandoc_trailing_handles_bare_url_form():
    # cli.py's explicit-key path strips the leading `@` before
    # normalization, so the helper has to recognize `url:` (no @) as
    # a URL key and strip its trailing slash.
    from quartobot.scan import strip_pandoc_trailing

    assert strip_pandoc_trailing("url:https://example.com/path/") == "url:https://example.com/path"
    # Sentence-ending punctuation still strips too.
    assert strip_pandoc_trailing("url:https://example.com/path/.") == "url:https://example.com/path"
    # No-op stays no-op.
    assert strip_pandoc_trailing("url:https://example.com/path") == "url:https://example.com/path"
