#!/usr/bin/env python3
"""Pre-commit gate: detect tracked files that match gitignore rules.

Files that are tracked but match .gitignore patterns indicate stale
tracking. This gate prevents the situation where a .gitignore rule is
added after files were already committed.

Fix: git rm --cached <files>
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


DEFAULT_WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


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


def get_ignored_tracked(workspace_root: Path) -> list[str]:
    """Return files that are tracked but match gitignore rules."""
    # Use check-ignore to find tracked files that should be ignored
    r = git(["ls-files"], cwd=workspace_root)
    if r.returncode != 0:
        print(f"ERROR: git ls-files failed: {r.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    tracked = [ln for ln in r.stdout.splitlines() if ln.strip()]

    if not tracked:
        return []

    # Pipe tracked files into check-ignore
    proc = subprocess.run(
        ["git", "check-ignore", "--stdin"],
        cwd=workspace_root,
        input="\n".join(tracked),
        capture_output=True,
        text=True,
        check=False,
    )
    return [ln for ln in proc.stdout.splitlines() if ln.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detect tracked files that match gitignore rules."
    )
    parser.add_argument(
        "--json", action="store_true", help="Output JSON report"
    )
    args = parser.parse_args()

    workspace_root = get_workspace_root()
    ignored_tracked = get_ignored_tracked(workspace_root)

    if args.json:
        print(
            json.dumps(
                {
                    "ok": len(ignored_tracked) == 0,
                    "drift_count": len(ignored_tracked),
                    "files": ignored_tracked[:100],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    if ignored_tracked:
        display = ignored_tracked[:20]
        print(
            f"❌ {len(ignored_tracked)} tracked file(s) match .gitignore (drift):",
            file=sys.stderr,
        )
        for f in display:
            print(f"  - {f}", file=sys.stderr)
        if len(ignored_tracked) > 20:
            print(
                f"  ... and {len(ignored_tracked) - 20} more",
                file=sys.stderr,
            )
        print(
            "\nFix: git rm --cached <files> + verify .gitignore covers them",
            file=sys.stderr,
        )
        sys.exit(1)

    print("✓ gitignore drift: clean")


if __name__ == "__main__":
    main()
