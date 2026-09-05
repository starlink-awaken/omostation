#!/usr/bin/env python3
"""Collect and aggregate repository health metrics.

Metrics:
- worktrees: total, active_24h, stale_7d, zombie
- branches: local, local_merged_deletable, remote, remote_stale_14d, remote_stale_30d
- submodules: total, uncommitted, behind_main
- artifacts: gitignore_drift_count, runtime_artifacts_staged

Output: JSON to stdout, appends to .omo/state/history/repo-health.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


DEFAULT_WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
HISTORY_PATH = (
    DEFAULT_WORKSPACE_ROOT / ".omo" / "state" / "history" / "repo-health.jsonl"
)
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
    r = git(["worktree", "list", "--porcelain"], cwd=workspace_root)
    if r.returncode != 0:
        return []
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


# ---------------------------------------------------------------------------
# Metrics collection
# ---------------------------------------------------------------------------


def collect_worktree_metrics(
    workspace_root: Path, stale_days: int
) -> dict[str, Any]:
    worktrees = list_worktrees(workspace_root)
    total = 0
    active_24h = 0
    stale = 0
    zombie = 0
    cutoff = datetime.now() - timedelta(days=stale_days)
    cutoff_24h = datetime.now() - timedelta(hours=24)

    for wt in worktrees:
        path = Path(wt["worktree"])
        if path == workspace_root:
            continue
        total += 1

        # Zombie detection
        git_file = path / ".git"
        if not git_file.exists() and not (path / ".git").is_dir():
            zombie += 1
            continue

        # Activity detection
        if path.exists():
            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime)
                if mtime > cutoff_24h:
                    active_24h += 1
                if mtime < cutoff:
                    stale += 1
            except OSError:
                stale += 1

    return {
        "total": total,
        "active_24h": active_24h,
        "stale_7d": stale,
        "zombie": zombie,
    }


def collect_branch_metrics(workspace_root: Path) -> dict[str, Any]:
    # Local branches
    r = git(["branch", "--format=%(refname:short)"], cwd=workspace_root)
    local_branches = [
        ln.strip() for ln in r.stdout.splitlines() if ln.strip()
    ]
    local = len(local_branches)

    # Local merged deletable
    r = git(["branch", "--merged", "origin/main", "--format=%(refname:short)"],
            cwd=workspace_root)
    merged = {ln.strip() for ln in r.stdout.splitlines() if ln.strip() and ln.strip() != "main"}

    # Worktree used branches
    worktrees = list_worktrees(workspace_root)
    used = {wt.get("branch", "") for wt in worktrees if wt.get("branch")}
    merged_deletable = len(merged - used)

    # Remote branches
    r = git(["branch", "-r", "--format=%(refname:short)"], cwd=workspace_root)
    remote_branches = [
        ln.strip() for ln in r.stdout.splitlines()
        if ln.strip() and not ln.strip().startswith("origin/HEAD")
    ]
    remote = len(remote_branches)

    # Remote stale
    remote_stale_14d = 0
    remote_stale_30d = 0
    cutoff_14d = datetime.now() - timedelta(days=14)
    cutoff_30d = datetime.now() - timedelta(days=30)

    for rb in remote_branches:
        lr = git(["log", "--format=%ci", "-1", rb], cwd=workspace_root)
        if lr.returncode != 0:
            continue
        date_str = lr.stdout.strip()
        if not date_str:
            continue
        try:
            dt = datetime.strptime(date_str[:19], "%Y-%m-%d %H:%M:%S")
            if dt < cutoff_30d:
                remote_stale_30d += 1
            elif dt < cutoff_14d:
                remote_stale_14d += 1
        except ValueError:
            continue

    return {
        "local": local,
        "local_merged_deletable": merged_deletable,
        "remote": remote,
        "remote_stale_14d": remote_stale_14d,
        "remote_stale_30d": remote_stale_30d,
    }


def collect_submodule_metrics(workspace_root: Path) -> dict[str, Any]:
    # Get submodule paths
    r = git(["config", "--file", ".gitmodules", "--get-regexp", "path"],
            cwd=workspace_root)
    if r.returncode != 0:
        return {"total": 0, "uncommitted": 0, "behind_main": 0}

    paths: list[str] = []
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            paths.append(parts[1])

    total = len(paths)
    uncommitted = 0
    behind_main = 0

    for sub_path in paths:
        full = workspace_root / sub_path
        if not full.exists():
            continue

        # Uncommitted
        r = git(["status", "--porcelain"], cwd=full)
        if r.returncode == 0 and r.stdout.strip():
            uncommitted += 1

        # Behind main
        r = git(["rev-list", "--count", "HEAD..origin/main"], cwd=full)
        if r.returncode == 0:
            try:
                count = int(r.stdout.strip())
                if count > 0:
                    behind_main += 1
            except ValueError:
                continue

    return {
        "total": total,
        "uncommitted": uncommitted,
        "behind_main": behind_main,
    }


def collect_artifact_metrics(workspace_root: Path) -> dict[str, Any]:
    # Gitignore drift
    tracked = git(["ls-files"], cwd=workspace_root)
    drift = 0
    if tracked.returncode == 0:
        proc = subprocess.run(
            ["git", "check-ignore", "--stdin"],
            cwd=workspace_root,
            input=tracked.stdout,
            capture_output=True,
            text=True,
            check=False,
        )
        drift = len([ln for ln in proc.stdout.splitlines() if ln.strip()])

    # Runtime artifacts staged
    staged = git(["diff", "--cached", "--name-only", "--diff-filter=A"],
                 cwd=workspace_root)
    runtime_staged = 0
    blacklist_suffixes = (
        ".sqlite", ".sqlite3", ".db", ".pyc", ".pyo", ".class", ".o", ".so"
    )
    if staged.returncode == 0:
        for f in staged.stdout.splitlines():
            if any(f.endswith(s) for s in blacklist_suffixes):
                runtime_staged += 1

    return {
        "tracked_gitignore_violations": drift,
        "runtime_artifacts_staged": runtime_staged,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect repository health metrics."
    )
    parser.add_argument(
        "--json", action="store_true", help="Output JSON only"
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Do not append to history file"
    )
    args = parser.parse_args()

    workspace_root = get_workspace_root()

    report = {
        "timestamp": datetime.now().isoformat() + "Z",
        "worktrees": collect_worktree_metrics(workspace_root, DEFAULT_STALE_DAYS),
        "branches": collect_branch_metrics(workspace_root),
        "submodules": collect_submodule_metrics(workspace_root),
        "artifacts": collect_artifact_metrics(workspace_root),
    }

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))

    # Append to history
    if not args.no_history:
        try:
            HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(HISTORY_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(report, ensure_ascii=False) + "\n")
        except OSError as e:
            print(f"WARNING: failed to write history: {e}", file=sys.stderr)

    # Exit code: 1 if issues found
    wt = report["worktrees"]
    br = report["branches"]
    am = report["artifacts"]
    if wt["zombie"] > 0 or wt["stale_7d"] > 0 or br["local_merged_deletable"] > 10 or am["tracked_gitignore_violations"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
