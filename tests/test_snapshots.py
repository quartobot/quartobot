"""Tests for the snapshots module and ``quartobot snapshots`` CLI."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from quartobot.cli import main
from quartobot.snapshots import (
    DEFAULT_POLICY,
    Decision,
    Inventory,
    RetentionPolicy,
    apply_decision,
    decide_retention,
    format_log,
    inventory,
    load_policy,
    project_post_prune_bytes,
)


def _write_version(
    gh_pages: Path,
    sha: str,
    size_bytes: int = 1024,
    *,
    age_seconds: float = 0,
) -> None:
    """Create a fake ``v/<sha>/index.html`` of approximately ``size_bytes``."""
    d = gh_pages / "v" / sha
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_bytes(b"x" * size_bytes)
    if age_seconds > 0:
        mtime = time.time() - age_seconds
        os.utime(d / "index.html", (mtime, mtime))


def _write_pr(gh_pages: Path, n: int, size_bytes: int = 512) -> None:
    """Create a fake ``pr/<n>/index.html`` preview."""
    d = gh_pages / "pr" / str(n)
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_bytes(b"y" * size_bytes)


def _write_root(gh_pages: Path, size_bytes: int = 256) -> None:
    """Create an ``index.html`` at the gh-pages root."""
    (gh_pages / "index.html").write_bytes(b"z" * size_bytes)


# -- load_policy -----------------------------------------------------------


class TestLoadPolicy:
    def test_no_quarto_yml_returns_defaults(self, tmp_path: Path) -> None:
        load = load_policy(tmp_path)
        assert load.policy == DEFAULT_POLICY
        assert "defaults" in load.source
        assert load.overrides == {}

    def test_quarto_yml_without_quartobot_block(self, tmp_path: Path) -> None:
        (tmp_path / "_quarto.yml").write_text(
            yaml.safe_dump({"project": {"type": "default"}})
        )
        load = load_policy(tmp_path)
        assert load.policy == DEFAULT_POLICY
        assert "no quartobot.snapshots" in load.source

    def test_quarto_yml_with_empty_snapshots_block(self, tmp_path: Path) -> None:
        (tmp_path / "_quarto.yml").write_text(
            yaml.safe_dump({"quartobot": {"snapshots": {}}})
        )
        load = load_policy(tmp_path)
        assert load.policy == DEFAULT_POLICY

    def test_override_recent_and_budget(self, tmp_path: Path) -> None:
        (tmp_path / "_quarto.yml").write_text(
            yaml.safe_dump(
                {"quartobot": {"snapshots": {"recent": 25, "size_budget_mb": 500}}}
            )
        )
        load = load_policy(tmp_path)
        assert load.policy.recent == 25
        assert load.policy.size_budget_mb == 500
        assert load.policy.on_over_budget == DEFAULT_POLICY.on_over_budget
        assert load.overrides == {"recent": 10, "size_budget_mb": 800}
        assert "_quarto.yml::quartobot.snapshots" in load.source

    def test_override_to_default_value_not_marked(self, tmp_path: Path) -> None:
        (tmp_path / "_quarto.yml").write_text(
            yaml.safe_dump({"quartobot": {"snapshots": {"recent": 10}}})
        )
        load = load_policy(tmp_path)
        assert load.policy.recent == 10
        assert "recent" not in load.overrides

    def test_unknown_keys_ignored(self, tmp_path: Path) -> None:
        (tmp_path / "_quarto.yml").write_text(
            yaml.safe_dump(
                {"quartobot": {"snapshots": {"recent": 5, "future_knob": "x"}}}
            )
        )
        load = load_policy(tmp_path)
        assert load.policy.recent == 5

    def test_invalid_enum_value_raises(self, tmp_path: Path) -> None:
        (tmp_path / "_quarto.yml").write_text(
            yaml.safe_dump(
                {"quartobot": {"snapshots": {"on_over_budget": "panic"}}}
            )
        )
        with pytest.raises(ValueError, match="on_over_budget"):
            load_policy(tmp_path)

    def test_invalid_int_raises(self, tmp_path: Path) -> None:
        (tmp_path / "_quarto.yml").write_text(
            yaml.safe_dump({"quartobot": {"snapshots": {"recent": "ten"}}})
        )
        with pytest.raises(ValueError, match="recent"):
            load_policy(tmp_path)


# -- inventory -------------------------------------------------------------


class TestInventory:
    def test_empty_dir(self, tmp_path: Path) -> None:
        inv = inventory(tmp_path)
        assert inv.snapshots == ()
        assert inv.pr_dirs == {}
        assert inv.root_bytes == 0
        assert inv.total_bytes == 0

    def test_groups_v_pr_root(self, tmp_path: Path) -> None:
        _write_version(tmp_path, "a" * 40, 1000)
        _write_version(tmp_path, "b" * 40, 2000)
        _write_pr(tmp_path, 7, 500)
        _write_root(tmp_path, 100)
        inv = inventory(tmp_path)
        assert {s.sha for s in inv.snapshots} == {"a" * 40, "b" * 40}
        assert inv.v_total_bytes == 3000
        assert inv.pr_dirs == {"7": 500}
        assert inv.root_bytes == 100
        assert inv.total_bytes == 3600

    def test_snapshots_sorted_by_mtime(self, tmp_path: Path) -> None:
        _write_version(tmp_path, "a" * 40, 100, age_seconds=1000)
        _write_version(tmp_path, "b" * 40, 100, age_seconds=10)
        inv = inventory(tmp_path)
        assert [s.sha[0] for s in inv.snapshots] == ["a", "b"]

    def test_missing_dir_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            inventory(tmp_path / "nope")

    def test_skips_git_dir(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_bytes(b"ref: refs/heads/gh-pages\n" * 100)
        inv = inventory(tmp_path)
        assert inv.total_bytes == 0


# -- decide_retention ------------------------------------------------------


def _inv_with_snapshots(*shas_in_order: str, size_each: int = 1000) -> Inventory:
    """Build an Inventory with synthetic snapshots in the supplied order."""
    from quartobot.snapshots import Snapshot

    snaps = tuple(
        Snapshot(sha=sha, size_bytes=size_each, mtime=float(i + 1))
        for i, sha in enumerate(shas_in_order)
    )
    return Inventory(
        gh_pages_dir=Path("/tmp/fake"),
        snapshots=snaps,
        pr_dirs={},
        root_bytes=0,
        other_bytes=0,
    )


class TestDecideRetention:
    def test_keeps_latest(self) -> None:
        inv = _inv_with_snapshots("a", "b", "c")
        d = decide_retention(
            inv, RetentionPolicy(recent=0), latest_sha="c", tagged_shas=set()
        )
        assert d.keep_latest == ("c",)
        assert d.keep_recent == ()
        assert set(d.prune) == {"a", "b"}

    def test_keeps_tagged(self) -> None:
        inv = _inv_with_snapshots("a", "b", "c", "d")
        d = decide_retention(
            inv,
            RetentionPolicy(recent=0),
            latest_sha="d",
            tagged_shas={"a", "c"},
        )
        assert d.keep_latest == ("d",)
        assert set(d.keep_tagged) == {"a", "c"}
        assert d.prune == ("b",)

    def test_recent_window(self) -> None:
        inv = _inv_with_snapshots("a", "b", "c", "d", "e")  # mtime a<b<c<d<e
        d = decide_retention(
            inv, RetentionPolicy(recent=2), latest_sha="e", tagged_shas=set()
        )
        # latest=e; recent=2 most-recent among non-kept => d, c (newest first)
        assert d.keep_latest == ("e",)
        assert d.keep_recent == ("d", "c")
        assert set(d.prune) == {"a", "b"}

    def test_recent_excludes_already_kept(self) -> None:
        inv = _inv_with_snapshots("a", "b", "c", "d", "e")
        d = decide_retention(
            inv,
            RetentionPolicy(recent=2),
            latest_sha="e",
            tagged_shas={"d"},  # d already kept as tagged
        )
        # recent window slides past d, picks c and b
        assert "d" in d.keep_tagged
        assert set(d.keep_recent) == {"c", "b"}
        assert d.prune == ("a",)

    def test_latest_not_in_snapshots(self) -> None:
        # The about-to-be-deployed SHA isn't on gh-pages yet
        inv = _inv_with_snapshots("a", "b", "c")
        d = decide_retention(
            inv,
            RetentionPolicy(recent=2),
            latest_sha="future",
            tagged_shas=set(),
        )
        assert d.keep_latest == ()
        assert d.keep_recent == ("c", "b")
        assert d.prune == ("a",)

    def test_recent_zero_keeps_only_latest_and_tagged(self) -> None:
        inv = _inv_with_snapshots("a", "b", "c")
        d = decide_retention(
            inv,
            RetentionPolicy(recent=0),
            latest_sha="c",
            tagged_shas={"a"},
        )
        assert set(d.kept) == {"a", "c"}
        assert d.prune == ("b",)

    def test_kept_property_deduplicates(self) -> None:
        d = Decision(
            keep_latest=("a",),
            keep_tagged=("a", "b"),
            keep_recent=("b", "c"),
            prune=(),
            latest_sha="a",
        )
        assert d.kept == ("a", "b", "c")


# -- apply_decision --------------------------------------------------------


class TestApplyDecision:
    def test_redirect_replaces_dir_with_stub(self, tmp_path: Path) -> None:
        sha = "f" * 40
        _write_version(tmp_path, sha, 5000)
        inv = inventory(tmp_path)
        decision = Decision(
            keep_latest=(),
            keep_tagged=(),
            keep_recent=(),
            prune=(sha,),
            latest_sha="latest",
        )
        apply_decision(inv, decision, RetentionPolicy(pruned_behavior="redirect"))
        stub = tmp_path / "v" / sha / "index.html"
        assert stub.is_file()
        body = stub.read_text(encoding="utf-8")
        assert "meta http-equiv=\"refresh\"" in body
        assert sha in body
        # Single file, much smaller than the original 5000-byte payload
        assert stub.stat().st_size < 2000

    def test_delete_removes_dir(self, tmp_path: Path) -> None:
        sha = "e" * 40
        _write_version(tmp_path, sha, 1000)
        inv = inventory(tmp_path)
        decision = Decision(
            keep_latest=(),
            keep_tagged=(),
            keep_recent=(),
            prune=(sha,),
            latest_sha="latest",
        )
        apply_decision(inv, decision, RetentionPolicy(pruned_behavior="delete"))
        assert not (tmp_path / "v" / sha).exists()

    def test_keeps_kept_snapshots_untouched(self, tmp_path: Path) -> None:
        keep = "k" * 40
        prune = "p" * 40
        _write_version(tmp_path, keep, 1000)
        _write_version(tmp_path, prune, 1000)
        inv = inventory(tmp_path)
        decision = Decision(
            keep_latest=(keep,),
            keep_tagged=(),
            keep_recent=(),
            prune=(prune,),
            latest_sha=keep,
        )
        apply_decision(inv, decision, RetentionPolicy())
        assert (tmp_path / "v" / keep / "index.html").stat().st_size == 1000


# -- projection ------------------------------------------------------------


class TestProjection:
    def test_redirect_collapses_pruned_to_stub_size(self) -> None:
        from quartobot.snapshots import Snapshot

        inv = Inventory(
            gh_pages_dir=Path("/tmp/x"),
            snapshots=(
                Snapshot("a", 1_000_000, 1.0),
                Snapshot("b", 1_000_000, 2.0),
            ),
            pr_dirs={},
            root_bytes=0,
            other_bytes=0,
        )
        decision = Decision(("b",), (), (), ("a",), latest_sha="b")
        projected = project_post_prune_bytes(inv, decision, RetentionPolicy())
        # Kept: b (1_000_000) + pruned stub (~512) = ~1_000_512
        assert 1_000_000 < projected < 1_001_500

    def test_delete_collapses_pruned_to_zero(self) -> None:
        from quartobot.snapshots import Snapshot

        inv = Inventory(
            gh_pages_dir=Path("/tmp/x"),
            snapshots=(Snapshot("a", 1_000_000, 1.0),),
            pr_dirs={},
            root_bytes=0,
            other_bytes=0,
        )
        decision = Decision((), (), (), ("a",), latest_sha="none")
        projected = project_post_prune_bytes(
            inv, decision, RetentionPolicy(pruned_behavior="delete")
        )
        assert projected == 0


# -- format_log ------------------------------------------------------------


class TestFormatLog:
    def test_echo_only_when_no_decision(self, tmp_path: Path) -> None:
        _write_version(tmp_path, "a" * 40)
        inv = inventory(tmp_path)
        load = load_policy(tmp_path)
        out = format_log(load, inv, decision=None, projected_post_prune_bytes=None)
        assert "echo-only" in out
        assert "Retention decisions" not in out

    def test_marks_overrides(self, tmp_path: Path) -> None:
        gh_pages = tmp_path / "gh"
        gh_pages.mkdir()
        (tmp_path / "_quarto.yml").write_text(
            yaml.safe_dump({"quartobot": {"snapshots": {"recent": 25}}})
        )
        load = load_policy(tmp_path)
        inv = inventory(gh_pages)
        out = format_log(load, inv, None, None)
        assert "recent=25" in out
        assert "overridden from default 10" in out

    def test_over_budget_status_present(self, tmp_path: Path) -> None:
        # Force a small budget so the inventory exceeds it
        (tmp_path / "_quarto.yml").write_text(
            yaml.safe_dump({"quartobot": {"snapshots": {"size_budget_mb": 1}}})
        )
        _write_version(tmp_path, "a" * 40, size_bytes=2_000_000)
        load = load_policy(tmp_path)
        inv = inventory(tmp_path)
        out = format_log(load, inv, None, None)
        assert "OVER BUDGET" in out


# -- CLI -------------------------------------------------------------------


class TestSnapshotsCli:
    def _init_git(self, project: Path) -> str:
        """Initialize a tiny git repo in ``project`` and return HEAD SHA."""
        import subprocess

        subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=project)
        subprocess.check_call(["git", "config", "user.email", "t@t.test"], cwd=project)
        subprocess.check_call(["git", "config", "user.name", "t"], cwd=project)
        (project / "x.txt").write_text("x")
        subprocess.check_call(["git", "add", "."], cwd=project)
        subprocess.check_call(
            ["git", "commit", "-q", "-m", "init"], cwd=project
        )
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=project, text=True
        ).strip()

    def test_inventory_command_reports(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        project.mkdir()
        gh = tmp_path / "gh-pages"
        gh.mkdir()
        _write_version(gh, "a" * 40)
        head = self._init_git(project)
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "snapshots",
                "inventory",
                "--gh-pages-dir",
                str(gh),
                "--project",
                str(project),
                "--latest-sha",
                head,
            ],
        )
        assert result.exit_code == 0, result.output
        assert "snapshot retention" in result.output
        assert "Retention decisions" in result.output

    def test_apply_dry_run_does_not_mutate(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        project.mkdir()
        gh = tmp_path / "gh-pages"
        gh.mkdir()
        _write_version(gh, "a" * 40, 5000)
        _write_version(gh, "b" * 40, 5000)
        before = list((gh / "v").iterdir())
        self._init_git(project)
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "snapshots",
                "apply",
                "--gh-pages-dir",
                str(gh),
                "--project",
                str(project),
                "--latest-sha",
                "z" * 40,
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        after = list((gh / "v").iterdir())
        assert sorted(p.name for p in before) == sorted(p.name for p in after)
        for d in after:
            assert (d / "index.html").stat().st_size == 5000

    def test_apply_fails_when_over_budget(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        project.mkdir()
        (project / "_quarto.yml").write_text(
            yaml.safe_dump(
                {
                    "quartobot": {
                        "snapshots": {
                            "size_budget_mb": 1,
                            "recent": 99,
                            "on_over_budget": "fail",
                        }
                    }
                }
            )
        )
        gh = tmp_path / "gh-pages"
        gh.mkdir()
        # Two 2 MB snapshots, both kept under recent=99; total > 1 MB budget.
        _write_version(gh, "a" * 40, 2_000_000)
        _write_version(gh, "b" * 40, 2_000_000)
        self._init_git(project)
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "snapshots",
                "apply",
                "--gh-pages-dir",
                str(gh),
                "--project",
                str(project),
                "--latest-sha",
                "z" * 40,
            ],
        )
        assert result.exit_code != 0
        assert "exceeds budget" in result.output

    def test_apply_warn_does_not_fail(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        project.mkdir()
        (project / "_quarto.yml").write_text(
            yaml.safe_dump(
                {
                    "quartobot": {
                        "snapshots": {
                            "size_budget_mb": 1,
                            "recent": 99,
                            "on_over_budget": "warn",
                        }
                    }
                }
            )
        )
        gh = tmp_path / "gh-pages"
        gh.mkdir()
        _write_version(gh, "a" * 40, 2_000_000)
        self._init_git(project)
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "snapshots",
                "apply",
                "--gh-pages-dir",
                str(gh),
                "--project",
                str(project),
                "--latest-sha",
                "z" * 40,
            ],
        )
        assert result.exit_code == 0
        assert "warning" in result.output.lower()
