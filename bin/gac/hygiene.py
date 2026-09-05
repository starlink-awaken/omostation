#!/usr/bin/env python3
"""Scan stale branches + detect zombie worktrees."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path


DEFAULT_WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


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


def detect_zombies(wr):
    return [str(Path(wt["worktree"])) for wt in list_worktrees(wr)
            if Path(wt["worktree"]) != wr and not (Path(wt["worktree"]) / ".git").exists()]


def scan_stale_branches(wr, days):
    r = git(["branch", "-r", "--format=%(refname:short)"], cwd=wr)
    stale, cutoff = [], datetime.now() - timedelta(days=days)
    prefixes = ("origin/work/", "origin/feat/", "origin/fix/", "origin/agent/", "origin/chore/")
    for branch in r.stdout.splitlines():
        branch = branch.strip()
        if not branch or branch == "origin/main" or not any(branch.startswith(p) for p in prefixes):
            continue
        lr = git(["log", "--format=%ci;%s", "-1", branch], cwd=wr)
        if lr.returncode != 0 or not lr.stdout.strip():
            continue
        parts = lr.stdout.strip().split(";", 1)
        try:
            dt = datetime.strptime(parts[0].strip()[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        if dt < cutoff:
            stale.append({"branch": branch.replace("origin/", ""), "days_inactive": (datetime.now() - dt).days,
                          "subject": parts[1].strip()[:80] if len(parts) > 1 else "?"})
    stale.sort(key=lambda x: x["days_inactive"], reverse=True)
    return stale


def main():
    parser = argparse.ArgumentParser(description="Scan stale branches and zombie worktrees.")
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    wr = get_workspace_root()
    zombies = detect_zombies(wr)
    stale = scan_stale_branches(wr, args.days)
    report = {"timestamp": datetime.now().isoformat() + "Z", "zombies": zombies, "stale_branches": stale}
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"Zombies: {len(zombies)}, Stale (>{args.days}d): {len(stale)}")
    sys.exit(1 if zombies or stale else 0)


if __name__ == "__main__":
    main()
