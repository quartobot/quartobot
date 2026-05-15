"""Snapshot retention policy for the gh-pages ``v/<sha>/`` directory layout.

quartobot publishes an immutable per-commit snapshot of the rendered
manuscript to ``v/<sha>/`` on gh-pages. Without a retention policy, that
directory grows linearly with every push to ``main`` and every PR build
and eventually crosses GitHub's 1 GB soft limit for Pages sites.

This module:

* Defines :class:`RetentionPolicy` and its defaults.
* Loads policy from ``quartobot.snapshots`` in ``_quarto.yml``.
* Inventories an on-disk gh-pages tree (sizes per top-level prefix and
  per ``v/<sha>``).
* Decides which ``v/<sha>`` entries to keep or redirect.
* Applies decisions: replaces pruned snapshots with tiny redirect stubs.
* Formats a human-readable log block summarizing the run.

The git knowledge — which SHAs carry tags, what "the latest" is right
now — is pushed to the caller. This module does no shelling out and no
network; it is pure file IO over a directory.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field, fields, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import yaml

PrunedBehavior = Literal["redirect", "delete"]
OverBudget = Literal["fail", "warn"]


@dataclass(frozen=True)
class RetentionPolicy:
    """Configurable retention rules for ``v/<sha>/`` snapshots on gh-pages.

    Defaults are tuned for an active manuscript project: enough headroom
    for a fast-iteration sprint, hard stop before GitHub's 1 GB Pages
    soft limit, tag-as-milestone convention to retain user-meaningful
    versions indefinitely.

    Attributes:
        latest: Whether the snapshot matching ``latest_sha`` is always
            retained. ``keep`` (default) is almost always correct; the
            knob exists for symmetry.
        tagged: Whether any snapshot whose commit carries a git tag is
            retained indefinitely. Tags are the user's "this version
            matters" signal.
        recent: How many *additional* untagged snapshots to keep, newest
            first. Set to ``0`` to keep only the latest + tagged.
        pruned_behavior: What to do with snapshots that fall outside the
            retention set. ``redirect`` writes a ~1 KB ``index.html``
            meta-refresh stub to the latest version; ``delete`` removes
            the directory entirely (URLs 404 afterwards).
        size_budget_mb: Soft budget for the *projected post-prune* gh-
            pages size, in megabytes. GitHub's documented soft limit is
            1 GB; defaulting to 800 leaves headroom for the next render.
        on_over_budget: Behavior when the projected post-prune size
            still exceeds ``size_budget_mb``. ``fail`` aborts the
            workflow so users notice early; ``warn`` logs a warning and
            continues.
    """

    latest: Literal["keep", "discard"] = "keep"
    tagged: Literal["keep", "discard"] = "keep"
    recent: int = 10
    pruned_behavior: PrunedBehavior = "redirect"
    size_budget_mb: int = 800
    on_over_budget: OverBudget = "fail"


DEFAULT_POLICY = RetentionPolicy()


@dataclass(frozen=True)
class PolicyLoad:
    """Result of loading a :class:`RetentionPolicy` from disk.

    Attributes:
        policy: The effective policy after applying any overrides.
        source: Human-readable description of where the policy came
            from (e.g. ``"defaults (no quartobot.snapshots in
            _quarto.yml)"`` or ``"_quarto.yml::quartobot.snapshots"``).
        overrides: Mapping from field name to the *default* value it
            was overridden from. Empty when no overrides were applied.
            Used to annotate the echo log.
    """

    policy: RetentionPolicy
    source: str
    overrides: dict[str, Any] = field(default_factory=dict)


def load_policy(project_dir: Path) -> PolicyLoad:
    """Load a :class:`RetentionPolicy` from ``project_dir/_quarto.yml``.

    Looks for a top-level ``quartobot:`` mapping with a ``snapshots:``
    child. Any keys present override the corresponding defaults; absent
    keys keep their default. Missing ``_quarto.yml``, missing
    ``quartobot`` block, or missing ``snapshots`` child all fall back
    cleanly to defaults — no error.

    Unknown keys under ``quartobot.snapshots`` are ignored with no
    warning here (callers can format diagnostics if desired).

    Args:
        project_dir: Directory containing ``_quarto.yml``.

    Returns:
        A :class:`PolicyLoad` carrying the effective policy plus
        diagnostics for the echo log.

    Raises:
        ValueError: If a known field is present but holds an unparseable
            value (e.g. ``recent: "ten"``).
    """
    config_path = project_dir / "_quarto.yml"
    if not config_path.is_file():
        return PolicyLoad(
            policy=DEFAULT_POLICY,
            source=f"defaults (no {config_path.name} found)",
        )

    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    snapshots_block = (raw.get("quartobot") or {}).get("snapshots")
    if not isinstance(snapshots_block, dict) or not snapshots_block:
        return PolicyLoad(
            policy=DEFAULT_POLICY,
            source=f"defaults (no quartobot.snapshots in {config_path.name})",
        )

    known = {f.name for f in fields(RetentionPolicy)}
    overrides: dict[str, Any] = {}
    updates: dict[str, Any] = {}
    for key, value in snapshots_block.items():
        if key not in known:
            continue
        default_value = getattr(DEFAULT_POLICY, key)
        if value == default_value:
            continue
        try:
            coerced = _coerce(key, value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"_quarto.yml: invalid value for quartobot.snapshots.{key}: {value!r} ({exc})"
            ) from exc
        if coerced == default_value:
            continue
        updates[key] = coerced
        overrides[key] = default_value

    policy = replace(DEFAULT_POLICY, **updates) if updates else DEFAULT_POLICY
    return PolicyLoad(
        policy=policy,
        source=f"{config_path.name}::quartobot.snapshots",
        overrides=overrides,
    )


def _coerce(key: str, value: Any) -> Any:
    """Coerce a raw YAML value to the type expected by :class:`RetentionPolicy`."""
    if key == "recent":
        return int(value)
    if key == "size_budget_mb":
        return int(value)
    if key in {"latest", "tagged"}:
        if value not in {"keep", "discard"}:
            raise ValueError(f"expected 'keep' or 'discard', got {value!r}")
        return value
    if key == "pruned_behavior":
        if value not in {"redirect", "delete"}:
            raise ValueError(f"expected 'redirect' or 'delete', got {value!r}")
        return value
    if key == "on_over_budget":
        if value not in {"fail", "warn"}:
            raise ValueError(f"expected 'fail' or 'warn', got {value!r}")
        return value
    return value


@dataclass(frozen=True)
class Snapshot:
    """A single ``v/<sha>/`` directory on gh-pages.

    Attributes:
        sha: Full git SHA (the directory name).
        size_bytes: Sum of all blob sizes under the directory.
        mtime: Latest mtime of any file in the directory (proxy for
            "when this snapshot was built"). Used to order untagged
            snapshots for the rolling ``recent`` window.
    """

    sha: str
    size_bytes: int
    mtime: float


@dataclass(frozen=True)
class Inventory:
    """Current state of a gh-pages tree, grouped by top-level prefix.

    Attributes:
        gh_pages_dir: The directory inventoried.
        snapshots: All ``v/<sha>/`` directories, oldest first by mtime.
        pr_dirs: ``pr/<n>/`` previews still present (size in bytes).
        root_bytes: Bytes in files directly under ``gh_pages_dir`` or
            in non-``v/``/``pr/`` subdirectories (the "latest at root"
            snapshot plus any shared assets).
        other_bytes: Bytes outside ``v/`` and ``pr/`` (folded into
            ``root_bytes`` for the log; tracked separately for tests).
    """

    gh_pages_dir: Path
    snapshots: tuple[Snapshot, ...]
    pr_dirs: dict[str, int]
    root_bytes: int
    other_bytes: int

    @property
    def v_total_bytes(self) -> int:
        """Total bytes across all ``v/<sha>/`` snapshots."""
        return sum(s.size_bytes for s in self.snapshots)

    @property
    def pr_total_bytes(self) -> int:
        """Total bytes across all ``pr/<n>/`` previews."""
        return sum(self.pr_dirs.values())

    @property
    def total_bytes(self) -> int:
        """Total bytes inventoried (``v/`` + ``pr/`` + root + other)."""
        return self.v_total_bytes + self.pr_total_bytes + self.root_bytes + self.other_bytes


def inventory(gh_pages_dir: Path) -> Inventory:
    """Walk ``gh_pages_dir`` and return an :class:`Inventory`.

    The walk is shallow on the top level (we only care about ``v/``,
    ``pr/``, and "everything else") and recursive within those prefixes
    to sum bytes. Symbolic links are not followed. ``.git`` is skipped.

    Args:
        gh_pages_dir: Path to a directory containing the gh-pages tree.
            Need not have a ``.git`` subdirectory — works on a plain
            checkout or a temp staging dir.

    Returns:
        An :class:`Inventory` describing the current contents.

    Raises:
        FileNotFoundError: If ``gh_pages_dir`` does not exist.
        NotADirectoryError: If ``gh_pages_dir`` is not a directory.
    """
    if not gh_pages_dir.exists():
        raise FileNotFoundError(gh_pages_dir)
    if not gh_pages_dir.is_dir():
        raise NotADirectoryError(gh_pages_dir)

    snapshots: list[Snapshot] = []
    pr_dirs: dict[str, int] = {}
    root_bytes = 0
    other_bytes = 0

    for entry in os.scandir(gh_pages_dir):
        if entry.name == ".git":
            continue
        if entry.is_symlink():
            continue
        if entry.is_dir():
            if entry.name == "v":
                for ver in os.scandir(entry.path):
                    if not ver.is_dir() or ver.is_symlink():
                        continue
                    size, mtime = _dir_size_and_mtime(Path(ver.path))
                    snapshots.append(Snapshot(sha=ver.name, size_bytes=size, mtime=mtime))
            elif entry.name == "pr":
                for pr in os.scandir(entry.path):
                    if not pr.is_dir() or pr.is_symlink():
                        continue
                    size, _ = _dir_size_and_mtime(Path(pr.path))
                    pr_dirs[pr.name] = size
            else:
                size, _ = _dir_size_and_mtime(Path(entry.path))
                other_bytes += size
        else:
            try:
                root_bytes += entry.stat().st_size
            except FileNotFoundError:
                pass

    snapshots.sort(key=lambda s: s.mtime)
    return Inventory(
        gh_pages_dir=gh_pages_dir,
        snapshots=tuple(snapshots),
        pr_dirs=pr_dirs,
        root_bytes=root_bytes,
        other_bytes=other_bytes,
    )


def _dir_size_and_mtime(path: Path) -> tuple[int, float]:
    """Recursively sum file sizes and find the max mtime under ``path``."""
    total = 0
    latest_mtime = 0.0
    for dirpath, dirnames, filenames in os.walk(path, followlinks=False):
        if ".git" in dirnames:
            dirnames.remove(".git")
        for name in filenames:
            try:
                st = os.stat(os.path.join(dirpath, name))
            except FileNotFoundError:
                continue
            total += st.st_size
            if st.st_mtime > latest_mtime:
                latest_mtime = st.st_mtime
    return total, latest_mtime


@dataclass(frozen=True)
class Decision:
    """Retention plan for a single :class:`Inventory`.

    Attributes:
        keep_latest: SHAs retained because they match ``latest_sha``.
        keep_tagged: SHAs retained because their commit carries a tag.
        keep_recent: SHAs retained by the rolling-window rule.
        prune: SHAs that fall outside the retention set and will be
            redirected or deleted per the policy.
        latest_sha: The "current" SHA the decision was made against.
            Echoed in logs and used to write redirect stubs that link
            back to root (which serves this SHA's render).
    """

    keep_latest: tuple[str, ...]
    keep_tagged: tuple[str, ...]
    keep_recent: tuple[str, ...]
    prune: tuple[str, ...]
    latest_sha: str

    @property
    def kept(self) -> tuple[str, ...]:
        """Union of all keep buckets, in stable order."""
        seen: set[str] = set()
        out: list[str] = []
        for sha in (*self.keep_latest, *self.keep_tagged, *self.keep_recent):
            if sha not in seen:
                seen.add(sha)
                out.append(sha)
        return tuple(out)


def decide_retention(
    inv: Inventory,
    policy: RetentionPolicy,
    *,
    latest_sha: str,
    tagged_shas: set[str],
) -> Decision:
    """Apply ``policy`` to ``inv`` and return the keep/prune plan.

    Order of evaluation:

    1. If ``policy.latest == "keep"``, retain ``latest_sha``.
    2. If ``policy.tagged == "keep"``, retain every SHA in
       ``tagged_shas`` that has a corresponding snapshot.
    3. Of the snapshots not yet retained, keep the most recent
       ``policy.recent`` by mtime.
    4. Everything else goes in the prune set.

    Args:
        inv: Current inventory.
        policy: Effective retention policy.
        latest_sha: SHA of the build currently being deployed (the one
            served at ``/``). Passed in by the caller because this
            module does not shell out to git.
        tagged_shas: Full git SHAs that carry at least one tag.

    Returns:
        A :class:`Decision` listing which SHAs land in each bucket.
    """
    snapshot_shas = {s.sha for s in inv.snapshots}

    keep_latest: list[str] = []
    if policy.latest == "keep" and latest_sha in snapshot_shas:
        keep_latest.append(latest_sha)

    keep_tagged: list[str] = []
    if policy.tagged == "keep":
        for sha in sorted(tagged_shas & snapshot_shas):
            if sha not in keep_latest:
                keep_tagged.append(sha)

    already_kept = set(keep_latest) | set(keep_tagged)
    recent_candidates = [s for s in inv.snapshots if s.sha not in already_kept]
    recent_candidates.sort(key=lambda s: s.mtime, reverse=True)
    keep_recent = [s.sha for s in recent_candidates[: max(policy.recent, 0)]]

    all_kept = already_kept | set(keep_recent)
    prune = tuple(s.sha for s in inv.snapshots if s.sha not in all_kept)

    return Decision(
        keep_latest=tuple(keep_latest),
        keep_tagged=tuple(keep_tagged),
        keep_recent=tuple(keep_recent),
        prune=prune,
        latest_sha=latest_sha,
    )


def project_post_prune_bytes(inv: Inventory, decision: Decision, policy: RetentionPolicy) -> int:
    """Estimate ``gh_pages_dir`` size after applying ``decision``.

    Approximation: pruned ``v/<sha>/`` directories collapse to a single
    redirect stub (~512 bytes) when ``pruned_behavior == 'redirect'``,
    or to zero bytes when ``pruned_behavior == 'delete'``. Kept
    directories keep their current size. ``pr/`` and root contributions
    are unchanged.
    """
    stub_bytes = 512 if policy.pruned_behavior == "redirect" else 0
    kept = set(decision.kept)
    kept_v = sum(s.size_bytes for s in inv.snapshots if s.sha in kept)
    pruned_v = stub_bytes * sum(1 for s in inv.snapshots if s.sha not in kept)
    return kept_v + pruned_v + inv.pr_total_bytes + inv.root_bytes + inv.other_bytes


REDIRECT_STUB_TEMPLATE = """<!DOCTYPE html>
<meta charset="utf-8">
<title>Snapshot pruned</title>
<meta http-equiv="refresh" content="0; url=../../">
<link rel="canonical" href="../../">
<style>
body {{ font-family: system-ui, sans-serif; max-width: 36rem;
       margin: 4rem auto; padding: 0 1rem; color: #333; }}
code {{ font-family: ui-monospace, monospace; }}
</style>
<h1>Snapshot pruned</h1>
<p>This per-commit snapshot has been retired per the project's retention policy.
Redirecting to the <a href="../../">latest version</a>.</p>
<p style="color:#666;font-size:0.85em">Snapshot SHA: <code>{sha}</code> · Pruned: {date_iso}</p>
"""


def apply_decision(inv: Inventory, decision: Decision, policy: RetentionPolicy) -> None:
    """Mutate ``inv.gh_pages_dir`` to match ``decision``.

    For each pruned SHA, depending on ``policy.pruned_behavior``:

    * ``redirect``: replace the directory with a single ``index.html``
      meta-refresh stub. The directory itself is preserved so the URL
      remains live.
    * ``delete``: remove the directory entirely.

    Kept snapshots are untouched. Files at the root and under ``pr/``
    are not modified by this function — PR cleanup lives in a separate
    workflow.

    Args:
        inv: Inventory produced from the same directory.
        decision: Decision computed from that inventory.
        policy: Effective retention policy (controls stub behavior).
    """
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for sha in decision.prune:
        version_dir = inv.gh_pages_dir / "v" / sha
        if not version_dir.is_dir():
            continue
        if policy.pruned_behavior == "delete":
            _rmtree(version_dir)
            continue
        _rmtree(version_dir)
        version_dir.mkdir(parents=True, exist_ok=True)
        stub = version_dir / "index.html"
        stub.write_text(REDIRECT_STUB_TEMPLATE.format(sha=sha, date_iso=now), encoding="utf-8")


def _rmtree(path: Path) -> None:
    """Remove a directory tree without following symlinks."""
    for dirpath, dirnames, filenames in os.walk(path, topdown=False, followlinks=False):
        for name in filenames:
            try:
                os.unlink(os.path.join(dirpath, name))
            except FileNotFoundError:
                pass
        for name in dirnames:
            try:
                os.rmdir(os.path.join(dirpath, name))
            except (FileNotFoundError, OSError):
                pass
    try:
        os.rmdir(path)
    except (FileNotFoundError, OSError):
        pass


def format_log(
    load: PolicyLoad,
    inv: Inventory,
    decision: Decision | None,
    projected_post_prune_bytes: int | None,
) -> str:
    """Format the log block echoed at the top of every prune step.

    The block is produced unconditionally, even when no prune is
    needed, so the Actions log always documents the policy that was in
    force for a given build.

    Args:
        load: The policy load result (policy + source + overrides).
        inv: Current inventory.
        decision: Retention decision, or ``None`` for echo-only mode
            (PR builds inventory the tree but do not decide).
        projected_post_prune_bytes: Estimated size after applying
            ``decision``. ``None`` in echo-only mode.

    Returns:
        A multi-line string ready to print verbatim. No trailing
        newline; callers add one if writing to a stream.
    """
    lines: list[str] = []
    lines.append("=== quartobot snapshot retention ===")
    lines.append(f"Config source: {load.source}")
    policy_dict = asdict(load.policy)
    pairs: list[str] = []
    ordered_keys = (
        "latest",
        "tagged",
        "recent",
        "pruned_behavior",
        "size_budget_mb",
        "on_over_budget",
    )
    for key in ordered_keys:
        val = policy_dict[key]
        marker = ""
        if key in load.overrides:
            marker = f"  (overridden from default {load.overrides[key]})"
        pairs.append(f"  {key}={val}{marker}")
    lines.extend(pairs)
    lines.append("")
    lines.append("Inventory (current gh-pages):")
    lines.append(f"  v/   {len(inv.snapshots):>3} dirs  {_mb(inv.v_total_bytes):>8.1f} MB")
    lines.append(f"  pr/  {len(inv.pr_dirs):>3} dirs  {_mb(inv.pr_total_bytes):>8.1f} MB")
    lines.append(f"  root           {_mb(inv.root_bytes + inv.other_bytes):>8.1f} MB")
    budget_bytes = load.policy.size_budget_mb * 1_000_000
    over_now = inv.total_bytes > budget_bytes
    status_now = f"OVER BUDGET: {load.policy.size_budget_mb} MB" if over_now else "OK"
    lines.append(f"  total          {_mb(inv.total_bytes):>8.1f} MB    [{status_now}]")

    if decision is None:
        lines.append("")
        lines.append("Mode: echo-only (no mutations on this event)")
        return "\n".join(lines)

    lines.append("")
    lines.append("Retention decisions:")
    lines.append(f"  keep (latest):    {_short_join(decision.keep_latest) or '(none)'}")
    lines.append(f"  keep (tagged):    {_short_join(decision.keep_tagged) or '(none)'}")
    recent_line = _short_join(decision.keep_recent) or "(none)"
    lines.append(f"  keep (recent x{load.policy.recent}): {recent_line}")
    behavior = load.policy.pruned_behavior
    arrow = "→ /" if behavior == "redirect" else "(deleted)"
    lines.append(f"  {behavior:<9}         {len(decision.prune)} older snapshots {arrow}")

    if projected_post_prune_bytes is not None:
        over_after = projected_post_prune_bytes > budget_bytes
        status_after = f"OVER BUDGET: {load.policy.size_budget_mb} MB" if over_after else "OK"
        lines.append("")
        projected_mb = _mb(projected_post_prune_bytes)
        lines.append(f"Projected total after prune: {projected_mb:.1f} MB    [{status_after}]")
    return "\n".join(lines)


def _mb(n: int) -> float:
    """Convert bytes to megabytes (decimal, matching GitHub's UI)."""
    return n / 1_000_000


def _short_join(shas: tuple[str, ...]) -> str:
    """Join short SHAs space-separated, wrapping at ~80 chars per line."""
    if not shas:
        return ""
    parts = [s[:7] for s in shas]
    lines: list[str] = []
    current = ""
    for p in parts:
        candidate = f"{current} {p}".strip() if current else p
        if len(candidate) > 70 and current:
            lines.append(current)
            current = p
        else:
            current = candidate
    if current:
        lines.append(current)
    return ("\n" + " " * 20).join(lines)
