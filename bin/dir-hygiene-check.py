#!/usr/bin/env python3
"""Directory hygiene check — detects root-level directories that are
neither tracked by git nor ignored by .gitignore.

This catches "phantom directories" created by AI tools or scripts that
appear at the workspace root without being accounted for.

Run: python3 bin/dir-hygiene-check.py [--json]
Exit 0 = clean, Exit 1 = violations found.
"""
import json as _json
import os
import subprocess
import sys
from pathlib import Path


def is_tracked(path: str) -> bool:
    r = subprocess.run(
        ["git", "ls-files", "--error-unmatch", path],
        capture_output=True, text=True,
    )
    return r.returncode == 0


def is_ignored(path: str) -> bool:
    r = subprocess.run(
        ["git", "check-ignore", path],
        capture_output=True, text=True,
    )
    return r.returncode == 0


def main() -> int:
    root = Path(subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True
    ).strip())

    violations = []
    for entry in sorted(root.iterdir()):
        name = entry.name
        if name.startswith(".git"):
            continue
        if not entry.is_dir():
            continue

        tracked = is_tracked(str(entry) + "/")
        ignored = is_ignored(str(entry) + "/")

        if not tracked and not ignored:
            violations.append(name)

    if not violations:
        print("dir-hygiene: PASS (all root directories tracked or ignored)")
        return 0

    print(f"dir-hygiene: FAIL ({len(violations)} untracked non-ignored dir(s))")
    for v in violations:
        print(f"  ?? {v}/")
    print()
    print("Either git add these directories, or add patterns to .gitignore.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
