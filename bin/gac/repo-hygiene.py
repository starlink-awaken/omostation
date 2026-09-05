#!/usr/bin/env python3
"""Repo hygiene: runtime-artifact gate, gitignore drift, metrics, stale branches."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path


DEFAULT_WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
ALLOWLIST_PATH = DEFAULT_WORKSPACE_ROOT / ".omo" / "_truth" / "registry" / "artifact-allowlist.yaml"

BLACKLIST_SUFFIXES = (".sqlite", ".sqlite3", ".db", ".pyc", ".pyo", ".class", ".o", ".so", ".dylib", ".dll", ".exe")
BLACKLIST_FILENAMES = (".DS_Store", "Thumbs.db", "desktop.ini")
BLACKLIST_PREFIXES = (".omo/locks/", ".omo/_log/", ".omo/_delivery/", "__pycache__/", ".venv/", "node_modules/", "dist/", "build/", "target/debug/", "target/release/", ".next/", ".nuxt/", ".output/", "coverage/", ".nyc_output/", ".cache/", "tmp/", "logs/", ".turbo/")
LOCK_WHITELIST = ("package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lock", "uv.lock", "Cargo.lock", "go.sum", "Gemfile.lock", "composer.lock", "poetry.lock")


def git(args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)


def get_workspace_root():
    r = git(["rev-parse", "--show-toplevel"], cwd=DEFAULT_WORKSPACE_ROOT)
    return Path(r.stdout.strip())


def get_staged_files(wr):
    r = git(["diff", "--cached", "--name-only", "--diff-filter=A"], cwd=wr)
    return [ln for ln in r.stdout.splitlines() if ln.strip()]


def load_allowlist():
    if not ALLOWLIST_PATH.is_file():
        return []
    try:
        import yaml
        data = yaml.safe_load(ALLOWLIST_PATH.read_text()) or {}
        return list(data.get("allowlist", []))
    except Exception:
        return []


def check_file(path):
    filename = os.path.basename(path)
    if filename in BLACKLIST_FILENAMES:
        return True, f"blacklisted filename: {filename}"
    for suffix in BLACKLIST_SUFFIXES:
        if path.endswith(suffix):
            return True, f"blacklisted suffix: {suffix}"
    for prefix in BLACKLIST_PREFIXES:
        if path.startswith(prefix):
            return True, f"blacklisted prefix: {prefix}"
    if filename.endswith(".lock") and filename not in LOCK_WHITELIST:
        return True, f"unwhitelisted lock file: {filename}"
    return False, ""


def get_ignored_tracked(wr):
    r = git(["ls-files"], cwd=wr)
    tracked = [ln for ln in r.stdout.splitlines() if ln.strip()]
    if not tracked:
        return []
    proc = subprocess.run(["git", "check-ignore", "--stdin"], cwd=wr, input="\n".join(tracked), capture_output=True, text=True, check=False)
    return [ln for ln in proc.stdout.splitlines() if ln.strip()]


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
    parser = argparse.ArgumentParser(description="Repo hygiene gates + metrics + stale branch scan.")
    parser.add_argument("--mode", choices=["gate", "metrics", "scan", "all"], default="all")
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    wr = get_workspace_root()
    result: dict = {"timestamp": datetime.now().isoformat() + "Z"}

    if args.mode in ("gate", "all"):
        violations = []
        allowlist = load_allowlist()
        for path in get_staged_files(wr):
            if not any(fnmatch.fnmatch(path, p) for p in allowlist):
                is_art, reason = check_file(path)
                if is_art:
                    violations.append({"path": path, "reason": reason, "gate": "artifacts"})
        for f in get_ignored_tracked(wr)[:50]:
            violations.append({"path": f, "reason": "tracked but matches gitignore", "gate": "gitignore"})
        result["gate"] = {"ok": len(violations) == 0, "violations": violations}

    if args.mode in ("metrics", "all"):
        total = active = stale = zombie = 0
        cutoff_24h = datetime.now() - timedelta(hours=24)
        for wt in list_worktrees(wr):
            p = Path(wt["worktree"])
            if p == wr:
                continue
            total += 1
            if not (p / ".git").exists():
                zombie += 1
            elif p.exists():
                try:
                    mtime = datetime.fromtimestamp(p.stat().st_mtime)
                    if mtime > cutoff_24h:
                        active += 1
                except OSError:
                    pass
        result["metrics"] = {"worktrees": {"total": total, "active_24h": active, "zombie": zombie}}

    if args.mode in ("scan", "all"):
        result["stale_branches"] = scan_stale_branches(wr, args.days)

    if args.json or args.mode != "all":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        g = result.get("gate", {})
        m = result.get("metrics", {}).get("worktrees", {})
        s = result.get("stale_branches", [])
        print(f"Gate: {'clean' if g.get('ok') else str(len(g.get('violations', []))) + ' violations'}")
        print(f"Worktrees: {m.get('total', 0)} total, {m.get('active_24h', 0)} active, {m.get('zombie', 0)} zombie")
        print(f"Stale branches (>{args.days}d): {len(s)}")

    violations = result.get("gate", {}).get("violations", [])
    if violations:
        sys.exit(1)


if __name__ == "__main__":
    main()
