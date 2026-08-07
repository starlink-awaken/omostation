#!/usr/bin/env python3
"""worktree-hygiene-audit: detect stale/abandoned worktrees and unregistered dirs.

Scans both `git worktree list` (registered worktrees) and the filesystem
(`~/ws-*`, `~/workspace-*`) to find:

- registered worktrees that are clean and whose branch is merged to origin/main
- registered worktrees with dirty state but no recent activity
- directories that look like former worktrees but are no longer registered
- independent clones or directories with source files that need human review

Output: exit 0 = audit completed (findings may still be present); exit 1 = error.
"""
from __future__ import annotations

import argparse
import json
import os
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


def _main() -> int:
    global STALE_DAYS
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument("--stale-days", type=float, default=STALE_DAYS, help="Stale threshold in days")
    parser.add_argument("--remove-empty", action="store_true", help="Remove empty/log-only abandoned dirs (dry-run by default)")
    parser.add_argument("--execute", action="store_true", help="Actually perform removals with --remove-empty")
    args = parser.parse_args()

    STALE_DAYS = args.stale_days

    registered = _registered_worktrees()
    registered_paths = {w["path"] for w in registered}

    worktree_reports = [_categorize_worktree(w) for w in registered if w.get("path")]

    unregistered = [d for d in _candidate_dirs() if not _is_registered(d, registered_paths)]
    unregistered_reports = [_unregistered_dir_info(d) for d in unregistered]

    removed_dirs: list[str] = []
    if args.remove_empty:
        for info in unregistered_reports:
            if info.category in ("empty_abandoned", "log_only_abandoned"):
                if args.execute:
                    try:
                        import shutil
                        shutil.rmtree(info.path)
                        removed_dirs.append(info.path)
                    except Exception as exc:
                        removed_dirs.append(f"{info.path} (error: {exc})")
                else:
                    removed_dirs.append(f"{info.path} (dry-run)")

    if args.json:
        report = {
            "worktrees": [asdict(w) for w in worktree_reports],
            "unregistered_dirs": [asdict(u) for u in unregistered_reports],
            "removed_dirs": removed_dirs,
        }
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    print("=== Registered Worktrees ===")
    for w in worktree_reports:
        flag = "🔴" if w.category in ("safe_to_remove", "stale_clean", "stale_dirty") else "🟡" if w.category == "merged_with_dirty" else "🟢"
        print(f"{flag} {w.path}")
        print(f"   branch={w.branch} dirty={w.dirty} merged={w.merged_to_origin_main} mtime_days={w.mtime_days:.1f}")
        print(f"   category={w.category} | {w.reason}")

    print("\n=== Unregistered Dirs ===")
    for u in unregistered_reports:
        flag = "🔴" if u.category in ("empty_abandoned", "log_only_abandoned") else "🟡" if u.category in ("small_clean_repo", "dirty_repo") else "🟢"
        print(f"{flag} {u.path}")
        print(f"   files={u.file_count} git={u.is_git_repo} dirty={u.dirty} branch={u.branch}")
        print(f"   category={u.category} | {u.reason}")

    if args.remove_empty:
        print("\n=== Removal Actions ===")
        if not removed_dirs:
            print("No empty/log-only dirs to remove.")
        else:
            for r in removed_dirs:
                print(f"{'removed' if args.execute else 'would remove'}: {r}")

    return 0


if __name__ == "__main__":
    sys.exit(_main())
