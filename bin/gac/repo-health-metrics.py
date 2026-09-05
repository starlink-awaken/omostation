#!/usr/bin/env python3
"""Collect repo health metrics: worktrees, branches, submodules."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path


DEFAULT_WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
HISTORY_PATH = DEFAULT_WORKSPACE_ROOT / ".omo" / "state" / "history" / "repo-health.jsonl"


def git(args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)


def get_workspace_root():
    r = git(["rev-parse", "--show-toplevel"], cwd=DEFAULT_WORKSPACE_ROOT)
    return Path(r.stdout.strip())


def list_worktrees(wr):
    r = git(["worktree", "list", "--porcelain"], cwd=wr)
    results, current = [], {}
    for line in r.stdout.splitlines():
        if line == "":
            if current:
                results.append(current)
                current = {}
            continue
        if line.startswith("worktree "):
            current["worktree"] = line[len("worktree ") :]
        elif line.startswith("branch "):
            current["branch"] = line[len("branch ") :]
        elif line == "detached":
            current["detached"] = "true"
    if current:
        results.append(current)
    return results


def collect_worktree_metrics(wr, stale_days=7):
    total = active_24h = stale = zombie = 0
    cutoff = datetime.now() - timedelta(days=stale_days)
    cutoff_24h = datetime.now() - timedelta(hours=24)
    for wt in list_worktrees(wr):
        path = Path(wt["worktree"])
        if path == wr:
            continue
        total += 1
        if not (path / ".git").exists() and not (path / ".git").is_dir():
            zombie += 1
            continue
        if path.exists():
            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime)
                if mtime > cutoff_24h:
                    active_24h += 1
                if mtime < cutoff:
                    stale += 1
            except OSError:
                stale += 1
    return {"total": total, "active_24h": active_24h, "stale_7d": stale, "zombie": zombie}


def collect_branch_metrics(wr):
    r = git(["branch", "--format=%(refname:short)"], cwd=wr)
    local = len([l for l in r.stdout.splitlines() if l.strip()])
    r = git(["branch", "--merged", "origin/main", "--format=%(refname:short)"], cwd=wr)
    merged = {l for l in r.stdout.splitlines() if l.strip() and l != "main"}
    used = {wt.get("branch", "") for wt in list_worktrees(wr) if wt.get("branch")}
    r = git(["branch", "-r", "--format=%(refname:short)"], cwd=wr)
    remote = len([l for l in r.stdout.splitlines() if l.strip() and not l.startswith("origin/HEAD")])
    return {"local": local, "local_merged_deletable": len(merged - used), "remote": remote}


def collect_submodule_metrics(wr):
    r = git(["config", "--file", ".gitmodules", "--get-regexp", "path"], cwd=wr)
    paths = [parts[1] for line in r.stdout.splitlines() if len(parts := line.split()) >= 2]
    total, uncommitted, behind_main = len(paths), 0, 0
    for sub_path in paths:
        full = wr / sub_path
        if not full.exists():
            continue
        r = git(["status", "--porcelain"], cwd=full)
        if r.returncode == 0 and r.stdout.strip():
            uncommitted += 1
        r = git(["rev-list", "--count", "HEAD..origin/main"], cwd=full)
        if r.returncode == 0:
            try:
                if int(r.stdout.strip()) > 0:
                    behind_main += 1
            except ValueError:
                pass
    return {"total": total, "uncommitted": uncommitted, "behind_main": behind_main}


def main():
    parser = argparse.ArgumentParser(description="Collect repo health metrics.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-history", action="store_true")
    args = parser.parse_args()

    wr = get_workspace_root()
    report = {
        "timestamp": datetime.now().isoformat() + "Z",
        "worktrees": collect_worktree_metrics(wr),
        "branches": collect_branch_metrics(wr),
        "submodules": collect_submodule_metrics(wr),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not args.no_history:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(HISTORY_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(report, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
