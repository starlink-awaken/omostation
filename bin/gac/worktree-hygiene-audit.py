#!/usr/bin/env python3
"""worktree-hygiene-audit: detect stale/abandoned worktrees and unregistered dirs.

Scans both `git worktree list` (registered worktrees) and the filesystem
(`~/ws-*`, `~/workspace-*`) to find:

- registered worktrees that are clean and whose branch is merged to origin/main
- registered worktrees with dirty state but no recent activity
- directories that look like former worktrees but are no longer registered
- independent clones or directories with source files that need human review

Output: exit 0 = audit completed and no unsafe state remains (when --fail-on-unsafe);
        exit 1 = error or unsafe state detected.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
HOME = Path.home()

# Dirs older than this (in days) are considered stale.
STALE_DAYS = 2

# Filenames that are safe to drop in an abandoned worktree dir.
SAFE_LOG_PATTERNS = ("watch_stderr.log", "watch_stdout.log")

UNSAFE_WORKTREE_CATEGORIES = frozenset(
    {"merged_with_dirty", "stale_dirty", "stale_clean"}
)
UNSAFE_DIR_CATEGORIES = frozenset(
    {"dirty_repo", "small_clean_repo", "needs_review"}
)
AUTO_DIR_CATEGORIES = frozenset({"empty_abandoned", "log_only_abandoned"})


@dataclass
class WorktreeInfo:
    path: str
    branch: str
    head: str
    dirty: int
    merged_to_origin_main: bool
    mtime_days: float
    upstream: str
    category: str
    reason: str


@dataclass
class UnregisteredDirInfo:
    path: str
    file_count: int
    is_git_repo: bool
    branch: str
    dirty: int
    category: str
    reason: str


@dataclass
class RemovalResult:
    path: str
    removed: bool
    dry_run: bool
    error: str = ""


def _run(cmd: list[str], cwd: Path | None = None, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd or WORKSPACE,
        capture_output=True,
        text=True,
        check=check,
    )


def _registered_worktrees() -> list[dict[str, str]]:
    out = _run(["git", "worktree", "list", "--porcelain"], check=True)
    worktrees: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in out.stdout.splitlines():
        if line.startswith("worktree "):
            if current:
                worktrees.append(current)
            current = {"path": line.split(" ", 1)[1]}
        elif line.startswith("HEAD "):
            current["head"] = line.split(" ", 1)[1]
        elif line.startswith("branch "):
            current["branch"] = line.split(" ", 1)[1]
        elif line.startswith("detached"):
            current["branch"] = "DETACHED"
    if current:
        worktrees.append(current)
    return worktrees


def _worktree_status(path: Path) -> tuple[int, str]:
    out = _run(["git", "status", "--short"], cwd=path)
    dirty = len([l for l in out.stdout.splitlines() if l.strip()])
    upstream_out = _run(["git", "rev-parse", "--abbrev-ref", "HEAD@{upstream}"], cwd=path)
    upstream = upstream_out.stdout.strip() if upstream_out.returncode == 0 else "none"
    return dirty, upstream


def _is_merged_to_origin_main(head: str) -> bool:
    rc = _run(["git", "merge-base", "--is-ancestor", head, "origin/main"]).returncode
    return rc == 0


def _mtime_days(path: Path) -> float:
    try:
        return (time.time() - path.stat().st_mtime) / 86400.0
    except Exception:
        return -1.0


def _categorize_worktree(wt: dict[str, str]) -> WorktreeInfo:
    path = Path(wt["path"])
    branch = wt.get("branch", "UNKNOWN")
    head = wt.get("head", "")
    dirty, upstream = _worktree_status(path)
    merged = _is_merged_to_origin_main(head) if head else False
    mtime_days = _mtime_days(path)

    if dirty == 0 and merged:
        category = "safe_to_remove"
        reason = "clean and merged to origin/main"
    elif dirty == 0 and not merged and mtime_days > STALE_DAYS:
        category = "stale_clean"
        reason = f"clean but unmerged and inactive for {mtime_days:.1f} days"
    elif dirty > 0 and merged:
        category = "merged_with_dirty"
        reason = f"merged to origin/main but has {dirty} uncommitted changes"
    elif dirty > 0 and mtime_days > STALE_DAYS:
        category = "stale_dirty"
        reason = f"inactive for {mtime_days:.1f} days with {dirty} uncommitted changes"
    else:
        category = "active"
        reason = "recently used or unmerged"

    return WorktreeInfo(
        path=str(path),
        branch=branch,
        head=head,
        dirty=dirty,
        merged_to_origin_main=merged,
        mtime_days=mtime_days,
        upstream=upstream,
        category=category,
        reason=reason,
    )


def _candidate_dirs() -> list[Path]:
    candidates: list[Path] = []
    for prefix in ("ws-", "workspace-"):
        candidates.extend(HOME.glob(f"{prefix}*"))
    return [d for d in candidates if d.is_dir()]


def _is_registered(path: Path, registered_paths: set[str]) -> bool:
    return str(path) in registered_paths or str(path.resolve()) in registered_paths


def _dir_file_count(path: Path) -> int:
    try:
        return sum(1 for _ in path.rglob("*") if _.is_file())
    except PermissionError:
        return -1


def _is_git_repo(path: Path) -> bool:
    git_dir = path / ".git"
    git_file = path / ".git"
    if git_dir.is_dir():
        return True
    if git_file.is_file():
        return True
    return False


def _unregistered_dir_info(path: Path) -> UnregisteredDirInfo:
    file_count = _dir_file_count(path)
    is_git = _is_git_repo(path)
    branch = ""
    dirty = 0

    if is_git:
        branch_out = _run(["git", "branch", "--show-current"], cwd=path)
        branch = branch_out.stdout.strip() if branch_out.returncode == 0 else ""
        status_out = _run(["git", "status", "--short"], cwd=path)
        dirty = len([l for l in status_out.stdout.splitlines() if l.strip()])

    if file_count == 0:
        category = "empty_abandoned"
        reason = "empty unregistered directory"
    elif file_count > 0 and all(
        p.name in SAFE_LOG_PATTERNS
        for p in path.rglob("*")
        if p.is_file()
    ):
        category = "log_only_abandoned"
        reason = "only contains runtime log files"
    elif is_git and dirty == 0 and file_count < 10:
        category = "small_clean_repo"
        reason = "small clean git repo; verify before deletion"
    elif is_git and dirty > 0:
        category = "dirty_repo"
        reason = f"git repo with {dirty} uncommitted changes"
    else:
        category = "needs_review"
        reason = f"unregistered directory with {file_count} files"

    return UnregisteredDirInfo(
        path=str(path),
        file_count=file_count,
        is_git_repo=is_git,
        branch=branch,
        dirty=dirty,
        category=category,
        reason=reason,
    )


def _protected_paths() -> set[str]:
    """Return paths that must never be removed (current workspace, cwd, repo root)."""
    protected = {
        str(WORKSPACE),
        str(WORKSPACE.resolve()),
        str(Path.cwd()),
        str(Path.cwd().resolve()),
    }
    try:
        repo_root = _run(["git", "rev-parse", "--show-toplevel"]).stdout.strip()
        if repo_root:
            protected.add(repo_root)
            protected.add(str(Path(repo_root).resolve()))
    except Exception:
        pass
    return protected


def _remove_worktree(path: str, execute: bool, protected: set[str]) -> RemovalResult:
    p = Path(path)
    if str(p) in protected or str(p.resolve()) in protected:
        return RemovalResult(path=path, removed=False, dry_run=False, error="protected path")

    if not execute:
        return RemovalResult(path=path, removed=False, dry_run=True, error="")

    # Try the graceful git path first.
    res = _run(["git", "worktree", "remove", "--force", path])
    if res.returncode == 0:
        _run(["git", "worktree", "prune"])
        return RemovalResult(path=path, removed=True, dry_run=False, error="")

    # Fallback: some worktrees contain submodules that git refuses to remove.
    try:
        shutil.rmtree(path, ignore_errors=False)
        _run(["git", "worktree", "prune"])
        return RemovalResult(path=path, removed=True, dry_run=False, error="")
    except Exception as exc:
        return RemovalResult(path=path, removed=False, dry_run=False, error=f"fallback rm failed: {exc}")


def _remove_dir(path: str, execute: bool, protected: set[str]) -> RemovalResult:
    p = Path(path)
    if str(p) in protected or str(p.resolve()) in protected:
        return RemovalResult(path=path, removed=False, dry_run=False, error="protected path")

    if not execute:
        return RemovalResult(path=path, removed=False, dry_run=True, error="")

    try:
        shutil.rmtree(path, ignore_errors=False)
        return RemovalResult(path=path, removed=True, dry_run=False, error="")
    except Exception as exc:
        return RemovalResult(path=path, removed=False, dry_run=False, error=str(exc))


def _summary_counts(
    worktree_reports: list[WorktreeInfo],
    unregistered_reports: list[UnregisteredDirInfo],
) -> dict[str, dict[str, int] | int]:
    worktree_counts: dict[str, int] = {}
    for w in worktree_reports:
        worktree_counts[w.category] = worktree_counts.get(w.category, 0) + 1
    dir_counts: dict[str, int] = {}
    for u in unregistered_reports:
        dir_counts[u.category] = dir_counts.get(u.category, 0) + 1
    return {
        "worktrees": worktree_counts,
        "unregistered_dirs": dir_counts,
        "total_worktrees": len(worktree_reports),
        "total_unregistered_dirs": len(unregistered_reports),
    }


def _main() -> int:
    global STALE_DAYS
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument("--stale-days", type=float, default=STALE_DAYS, help="Stale threshold in days")
    parser.add_argument(
        "--remove-empty",
        action="store_true",
        help="Remove empty/log-only abandoned dirs (dry-run by default; use --execute)",
    )
    parser.add_argument(
        "--auto-clean",
        action="store_true",
        help="Auto-clean safe worktrees and empty/log-only dirs (dry-run by default; use --execute)",
    )
    parser.add_argument("--execute", action="store_true", help="Actually perform removals")
    parser.add_argument(
        "--fail-on-unsafe",
        action="store_true",
        help="Exit with code 1 if any unsafe state remains after audit/cleanup",
    )
    args = parser.parse_args()

    STALE_DAYS = args.stale_days

    registered = _registered_worktrees()
    registered_paths = {w["path"] for w in registered}

    worktree_reports = [_categorize_worktree(w) for w in registered if w.get("path")]

    unregistered = [d for d in _candidate_dirs() if not _is_registered(d, registered_paths)]
    unregistered_reports = [_unregistered_dir_info(d) for d in unregistered]

    protected = _protected_paths()
    removal_results: list[RemovalResult] = []

    # Legacy option: only empty/log-only dirs.
    if args.remove_empty:
        for info in unregistered_reports:
            if info.category in AUTO_DIR_CATEGORIES:
                removal_results.append(_remove_dir(info.path, args.execute, protected))

    if args.auto_clean:
        # Remove safe registered worktrees.
        for info in worktree_reports:
            if info.category == "safe_to_remove":
                removal_results.append(_remove_worktree(info.path, args.execute, protected))
        # Refresh registered list and reports after removals so summary is accurate.
        if args.execute:
            registered = _registered_worktrees()
            registered_paths = {w["path"] for w in registered}
            worktree_reports = [_categorize_worktree(w) for w in registered if w.get("path")]
            unregistered = [d for d in _candidate_dirs() if not _is_registered(d, registered_paths)]
            unregistered_reports = [_unregistered_dir_info(d) for d in unregistered]

        # Remove empty/log-only unregistered dirs.
        for info in unregistered_reports:
            if info.category in AUTO_DIR_CATEGORIES:
                removal_results.append(_remove_dir(info.path, args.execute, protected))

        if args.execute:
            unregistered = [d for d in _candidate_dirs() if not _is_registered(d, registered_paths)]
            unregistered_reports = [_unregistered_dir_info(d) for d in unregistered]

    counts = _summary_counts(worktree_reports, unregistered_reports)
    unsafe_worktrees = [w for w in worktree_reports if w.category in UNSAFE_WORKTREE_CATEGORIES]
    unsafe_dirs = [u for u in unregistered_reports if u.category in UNSAFE_DIR_CATEGORIES]
    unsafe_count = len(unsafe_worktrees) + len(unsafe_dirs)

    if args.json:
        report = {
            "worktrees": [asdict(w) for w in worktree_reports],
            "unregistered_dirs": [asdict(u) for u in unregistered_reports],
            "removal_results": [asdict(r) for r in removal_results],
            "summary": {
                "counts": counts,
                "unsafe_remaining": unsafe_count,
                "unsafe_worktrees": [asdict(w) for w in unsafe_worktrees],
                "unsafe_dirs": [asdict(u) for u in unsafe_dirs],
            },
        }
        print(json.dumps(report, indent=2, ensure_ascii=False))
        if args.fail_on_unsafe and unsafe_count:
            return 1
        return 0

    print("=== Registered Worktrees ===")
    for w in worktree_reports:
        flag = "🔴" if w.category in UNSAFE_WORKTREE_CATEGORIES else "🟡" if w.category == "merged_with_dirty" else "🟢"
        print(f"{flag} {w.path}")
        print(f"   branch={w.branch} dirty={w.dirty} merged={w.merged_to_origin_main} mtime_days={w.mtime_days:.1f}")
        print(f"   category={w.category} | {w.reason}")

    print("\n=== Unregistered Dirs ===")
    for u in unregistered_reports:
        flag = "🔴" if u.category in UNSAFE_DIR_CATEGORIES else "🟡" if u.category == "merged_with_dirty" else "🟢"
        print(f"{flag} {u.path}")
        print(f"   files={u.file_count} git={u.is_git_repo} dirty={u.dirty} branch={u.branch}")
        print(f"   category={u.category} | {u.reason}")

    if args.remove_empty or args.auto_clean:
        print("\n=== Removal Actions ===")
        if not removal_results:
            print("No items to remove.")
        else:
            for r in removal_results:
                status = "removed" if r.removed else "would remove" if r.dry_run else "failed"
                suffix = f" [{r.error}]" if r.error else ""
                print(f"{status}: {r.path}{suffix}")

    print("\n=== Summary ===")
    print(f"worktrees: {counts['total_worktrees']}")
    for cat, n in counts["worktrees"].items():
        print(f"  {cat}: {n}")
    print(f"unregistered_dirs: {counts['total_unregistered_dirs']}")
    for cat, n in counts["unregistered_dirs"].items():
        print(f"  {cat}: {n}")
    print(f"unsafe_remaining: {unsafe_count}")

    if args.fail_on_unsafe and unsafe_count:
        print(f"\n❌ fail-on-unsafe: {unsafe_count} unsafe item(s) remain")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(_main())
