#!/usr/bin/env python3
"""Pre-commit gate: block runtime artifacts from entering git index.

Detects files that should not be tracked in git (databases, logs, build
artifacts, lock files, etc.) before they enter the staging area.

Whitelist: .omo/_truth/registry/artifact-allowlist.yaml
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


DEFAULT_WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
ALLOWLIST_PATH = (
    DEFAULT_WORKSPACE_ROOT
    / ".omo"
    / "_truth"
    / "registry"
    / "artifact-allowlist.yaml"
)

# ---------------------------------------------------------------------------
# Blacklist rules
# ---------------------------------------------------------------------------

# Suffixes that indicate runtime artifacts
BLACKLIST_SUFFIXES: tuple[str, ...] = (
    ".sqlite",
    ".sqlite3",
    ".sqlite-wal",
    ".sqlite-shm",
    ".db",
    ".pyc",
    ".pyo",
    ".class",
    ".o",
    ".so",
    ".dylib",
    ".dll",
    ".exe",
    ".wasm",
    ".d.ts",
    ".map",
)

# Exact filenames that are runtime artifacts
BLACKLIST_FILENAMES: tuple[str, ...] = (
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    ".env.local",
    ".env.*.local",
)

# Path prefixes (relative to repo root) that indicate runtime artifacts
BLACKLIST_PREFIXES: tuple[str, ...] = (
    ".omo/locks/",
    ".omo/_log/",
    ".omo/_delivery/",
    "__pycache__/",
    ".venv/",
    "node_modules/",
    "dist/",
    "build/out/",
    "target/debug/",
    "target/release/",
    ".next/",
    ".nuxt/",
    ".output/",
    "coverage/",
    ".nyc_output/",
    ".cache/",
    "tmp/",
    "logs/",
    ".turbo/",
)

# Lock files whitelist (these ARE allowed)
LOCK_WHITELIST: tuple[str, ...] = (
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lock",
    "uv.lock",
    "Cargo.lock",
    "go.sum",
    "Gemfile.lock",
    "composer.lock",
    "poetry.lock",
)


# ---------------------------------------------------------------------------
# Helpers
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


def get_staged_files(workspace_root: Path) -> list[str]:
    """Return list of staged file paths."""
    r = git(
        ["diff", "--cached", "--name-only", "--diff-filter=A"],
        cwd=workspace_root,
    )
    if r.returncode != 0:
        print(f"ERROR: git diff failed: {r.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return [ln for ln in r.stdout.splitlines() if ln.strip()]


def load_allowlist() -> list[str]:
    """Load whitelist patterns from YAML file."""
    if not ALLOWLIST_PATH.is_file():
        return []
    try:
        import yaml

        data = yaml.safe_load(ALLOWLIST_PATH.read_text()) or {}
        return list(data.get("allowlist", []))
    except Exception as e:
        print(f"WARNING: failed to load allowlist: {e}", file=sys.stderr)
        return []


def is_whitelisted(path: str, allowlist: list[str]) -> bool:
    for pattern in allowlist:
        if fnmatch.fnmatch(path, pattern):
            return True
    return False


def check_file(path: str) -> tuple[bool, str]:
    """Check if a file is a runtime artifact. Returns (is_artifact, reason)."""

    # Check exact filename
    filename = os.path.basename(path)
    if filename in BLACKLIST_FILENAMES:
        return True, f"blacklisted filename: {filename}"

    # Check suffix
    for suffix in BLACKLIST_SUFFIXES:
        if path.endswith(suffix):
            return True, f"blacklisted suffix: {suffix}"

    # Check path prefix
    for prefix in BLACKLIST_PREFIXES:
        if path.startswith(prefix):
            return True, f"blacklisted prefix: {prefix}"

    # Check lock files (only specific whitelisted ones allowed)
    if filename.endswith(".lock") and filename not in LOCK_WHITELIST:
        return True, f"unwhitelisted lock file: {filename}"

    return False, ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Block runtime artifacts from entering git index."
    )
    parser.add_argument(
        "--json", action="store_true", help="Output JSON report"
    )
    args = parser.parse_args()

    workspace_root = get_workspace_root()
    staged = get_staged_files(workspace_root)
    allowlist = load_allowlist()

    violations: list[dict[str, str]] = []

    for path in staged:
        if is_whitelisted(path, allowlist):
            continue
        is_artifact, reason = check_file(path)
        if is_artifact:
            violations.append({"path": path, "reason": reason})

    if args.json:
        print(
            json.dumps(
                {"ok": len(violations) == 0, "violations": violations},
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    if violations:
        print(
            f"❌ {len(violations)} runtime artifact(s) blocked from staging:",
            file=sys.stderr,
        )
        for v in violations:
            print(f"  - {v['path']} ({v['reason']})", file=sys.stderr)
        print(
            "\nFix: git rm --cached <file> + add to .gitignore",
            file=sys.stderr,
        )
        sys.exit(1)

    print("✓ runtime artifact gate: clean")


if __name__ == "__main__":
    main()
