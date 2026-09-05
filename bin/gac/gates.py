#!/usr/bin/env python3
"""Pre-commit gate: block runtime artifacts and gitignore drift."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
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


def is_whitelisted(path, allowlist):
    return any(fnmatch.fnmatch(path, p) for p in allowlist)


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


def main():
    parser = argparse.ArgumentParser(description="Block runtime artifacts and gitignore drift.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    wr = get_workspace_root()
    violations = []

    allowlist = load_allowlist()
    staged = get_staged_files(wr)
    for path in staged:
        if is_whitelisted(path, allowlist):
            continue
        is_artifact, reason = check_file(path)
        if is_artifact:
            violations.append({"path": path, "reason": reason, "gate": "artifacts"})

    drift = get_ignored_tracked(wr)
    for f in drift[:50]:
        violations.append({"path": f, "reason": "tracked but matches gitignore", "gate": "gitignore"})

    if args.json:
        print(json.dumps({"ok": len(violations) == 0, "violations": violations}, indent=2, ensure_ascii=False))
        return

    if violations:
        print(f"❌ {len(violations)} gate violation(s):", file=sys.stderr)
        for v in violations[:20]:
            print(f"  - {v['path']} [{v['gate']}] {v['reason']}", file=sys.stderr)
        sys.exit(1)

    print("✓ gates: clean")


if __name__ == "__main__":
    main()
