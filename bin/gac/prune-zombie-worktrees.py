#!/usr/bin/env python3
"""Detect and optionally prune zombie worktrees, stale worktrees, and merged branches.

Zombie worktree: registered in .git/worktrees but the worktree directory
no longer contains a .git file (data lost or manually removed).

Stale worktree: a worktree whose directory has not been modified for a
configurable number of days (default 7) and has no uncommitted changes.

Merged branch: a local branch that is fully merged into origin/main and is
not used by any active worktree.

Usage:
    python3 bin/gac/prune-zombie-worktrees.py [--json]
    python3 bin/gac/prune-zombie-worktrees.py --prune --days 14 --dry-run
    python3 bin/gac/prune-zombie-worktrees.py --prune --days 14
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


DEFAULT_WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STALE_DAYS = 7


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def get_workspace_root() -> Path:
    r = git(["rev-parse", "--show-toplevel"], cwd=DEFAULT_WORKSPACE_ROOT)
    if r.returncode != 0:
        print(f"ERROR: not inside a git repo: {r.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return Path(r.stdout.strip())


def list_worktrees(workspace_root: Path) -> list[dict[str, str]]:
    """Return list of {worktree, HEAD, branch, detached} dicts."""
    r = git(["worktree", "list", "--porcelain"], cwd=workspace_root)
    if r.returncode != 0:
        print(f"ERROR: git worktree list failed: {r.stderr.strip()}", file=sys.stderr)
        sys.exit(1)

    results: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in r.stdout.splitlines():
        if line == "":
            if current:
                results.append(current)
                current = {}
            continue
        if line.startswith("worktree "):
            current["worktree"] = line[len("worktree ") :]
        elif line.startswith("HEAD "):
            current["HEAD"] = line[len("HEAD ") :]
        elif line.startswith("branch "):
            current["branch"] = line[len("branch ") :]
        elif line == "detached":
            current["detached"] = "true"
    if current:
        results.append(current)
    return results


def is_merged_into(branch: str, target: str, workspace_root: Path) -> bool:
    r = git(["merge-base", "--is-ancestor", branch, target], cwd=workspace_root)
    return r.returncode == 0


def branch_exists(branch: str, workspace_root: Path) -> bool:
    r = git(["rev-parse", "--verify", branch], cwd=workspace_root)
    return r.returncode == 0


def delete_local_branch(branch: str, workspace_root: Path, force: bool = False) -> bool:
    flag = "-D" if force else "-d"
    r = git(["branch", flag, branch], cwd=workspace_root)
    return r.returncode == 0


def prune_worktree(path: Path, workspace_root: Path, force: bool = False) -> bool:
    args = ["worktree", "remove", "--force"] if force else ["worktree", "remove"]
    args.append(str(path))
    r = git(args, cwd=workspace_root)
    return r.returncode == 0


def prune_git_worktree_refs(workspace_root: Path) -> None:
    git(["worktree", "prune"], cwd=workspace_root)


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


@dataclass
class ZombieInfo:
    path: str
    reason: str


@dataclass
class StaleInfo:
    path: str
    branch: str
    last_modified: str
    days_inactive: int
    dirty: int


@dataclass
class MergedBranchInfo:
    branch: str
    last_commit: str
    used_by_worktree: bool


@dataclass
class Report:
    zombies: list[ZombieInfo] = field(default_factory=list)
    stale: list[StaleInfo] = field(default_factory=list)
    merged_branches: list[MergedBranchInfo] = field(default_factory=list)


def detect_zombies(
    worktrees: list[dict[str, str]], workspace_root: Path
) -> list[ZombieInfo]:
    zombies: list[ZombieInfo] = []
    for wt in worktrees:
        path = Path(wt["worktree"])
        if path == workspace_root:
            continue
        git_file = path / ".git"
        if not git_file.exists():
            zombies.append(ZombieInfo(path=str(path), reason="missing .git file"))
    return zombies


def detect_stale(
    worktrees: list[dict[str, str]],
    workspace_root: Path,
    stale_days: int,
) -> list[StaleInfo]:
    stale: list[StaleInfo] = []
    cutoff = datetime.now() - timedelta(days=stale_days)

    for wt in worktrees:
        path = Path(wt["worktree"])
        if path == workspace_root:
            continue
        if not path.exists():
            continue

        # Check for uncommitted changes
        r = git(["status", "--porcelain"], cwd=path)
        dirty = 0
        if r.returncode == 0:
            dirty = len(
                [
                    ln
                    for ln in r.stdout.splitlines()
                    if ln.strip() and not ln.startswith("??")
                ]
            )
        if dirty > 0:
            continue

        # Check directory mtime
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
        except OSError:
            continue
        if mtime > cutoff:
            continue

        days_inactive = (datetime.now() - mtime).days
        branch = wt.get("branch", "detached")
        stale.append(
            StaleInfo(
                path=str(path),
                branch=branch,
                last_modified=mtime.strftime("%Y-%m-%d %H:%M"),
                days_inactive=days_inactive,
                dirty=dirty,
            )
        )
    return stale


def detect_merged_branches(
    worktrees: list[dict[str, str]], workspace_root: Path
) -> list[MergedBranchInfo]:
    used_branches = {
        wt.get("branch", "") for wt in worktrees if wt.get("branch")
    }

    r = git(["branch", "--merged", "origin/main", "--format=%(refname:short)"],
            cwd=workspace_root)
    if r.returncode != 0:
        return []

    merged: list[MergedBranchInfo] = []
    for line in r.stdout.splitlines():
        branch = line.strip()
        if not branch or branch == "main":
            continue
        lr = git(["log", "--oneline", "-1", branch], cwd=workspace_root)
        last_commit = lr.stdout.strip() if lr.returncode == 0 else "?"
        merged.append(
            MergedBranchInfo(
                branch=branch,
                last_commit=last_commit,
                used_by_worktree=branch in used_branches,
            )
        )
    return merged


# ---------------------------------------------------------------------------
# Prune
# ---------------------------------------------------------------------------


def do_prune(
    report: Report,
    workspace_root: Path,
    dry_run: bool = True,
    delete_merged: bool = False,
) -> dict[str, list[str]]:
    actions: dict[str, list[str]] = {
        "zombies_removed": [],
        "stale_removed": [],
        "merged_deleted": [],
        "failed": [],
    }

    for z in report.zombies:
        if dry_run:
            actions["zombies_removed"].append(f"[dry-run] {z.path}")
        else:
            if prune_worktree(Path(z.path), workspace_root, force=True):
                actions["zombies_removed"].append(z.path)
            else:
                actions["failed"].append(f"zombie: {z.path}")

    for s in report.stale:
        if dry_run:
            actions["stale_removed"].append(f"[dry-run] {s.path} ({s.branch})")
        else:
            if prune_worktree(Path(s.path), workspace_root, force=False):
                actions["stale_removed"].append(s.path)
            else:
                actions["failed"].append(f"stale: {s.path}")

    if delete_merged:
        for m in report.merged_branches:
            if m.used_by_worktree:
                continue
            if dry_run:
                actions["merged_deleted"].append(f"[dry-run] {m.branch}")
            else:
                if delete_local_branch(m.branch, workspace_root, force=True):
                    actions["merged_deleted"].append(m.branch)
                else:
                    actions["failed"].append(f"branch: {m.branch}")

    if not dry_run:
        prune_git_worktree_refs(workspace_root)

    return actions


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def to_dict(report: Report) -> dict[str, Any]:
    return {
        "zombies": [
            {"path": z.path, "reason": z.reason} for z in report.zombies
        ],
        "stale": [
            {
                "path": s.path,
                "branch": s.branch,
                "last_modified": s.last_modified,
                "days_inactive": s.days_inactive,
            }
            for s in report.stale
        ],
        "merged_branches": [
            {
                "branch": m.branch,
                "last_commit": m.last_commit,
                "used_by_worktree": m.used_by_worktree,
            }
            for m in report.merged_branches
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detect and prune zombie/stale worktrees and merged branches."
    )
    parser.add_argument(
        "--json", action="store_true", help="Output JSON report"
    )
    parser.add_argument(
        "--prune", action="store_true", help="Perform cleanup (default: detect only)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be pruned without making changes",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_STALE_DAYS,
        help=f"Days of inactivity before a worktree is stale (default: {DEFAULT_STALE_DAYS})",
    )
    parser.add_argument(
        "--delete-merged",
        action="store_true",
        help="Also delete local branches merged into origin/main (not used by worktrees)",
    )
    args = parser.parse_args()

    workspace_root = get_workspace_root()
    worktrees = list_worktrees(workspace_root)

    report = Report()
    report.zombies = detect_zombies(worktrees, workspace_root)
    report.stale = detect_stale(worktrees, workspace_root, args.days)
    report.merged_branches = detect_merged_branches(worktrees, workspace_root)

    if args.json:
        print(json.dumps(to_dict(report), indent=2, ensure_ascii=False))
        return

    # Human-readable output
    print(f"Workspace: {workspace_root}")
    print()

    print(f"🧟 Zombie worktrees: {len(report.zombies)}")
    for z in report.zombies:
        print(f"  - {z.path} ({z.reason})")
    print()

    print(f"⏰ Stale worktrees (>{args.days} days, no changes): {len(report.stale)}")
    for s in report.stale:
        print(
            f"  - {s.path} [{s.branch}] last={s.last_modified} ({s.days_inactive}d ago)"
        )
    print()

    deletable = [m for m in report.merged_branches if not m.used_by_worktree]
    print(
        f"🔀 Merged branches: {len(report.merged_branches)} "
        f"({len(deletable)} deletable, {len(report.merged_branches) - len(deletable)} in use)"
    )
    for m in report.merged_branches:
        tag = "✓" if m.used_by_worktree else "✗"
        print(f"  [{tag}] {m.branch}: {m.last_commit[:60]}")
    print()

    if args.prune or args.dry_run:
        actions = do_prune(
            report,
            workspace_root,
            dry_run=args.dry_run,
            delete_merged=args.delete_merged,
        )
        mode = "DRY RUN" if args.dry_run else "PRUNED"
        print(f"--- {mode} ---")
        for category, items in actions.items():
            if items:
                print(f"{category}: {len(items)}")
                for item in items:
                    print(f"  - {item}")

    # Exit code: 0 = clean, 1 = issues found
    if report.zombies or report.stale or deletable:
        sys.exit(1)


if __name__ == "__main__":
    main()
