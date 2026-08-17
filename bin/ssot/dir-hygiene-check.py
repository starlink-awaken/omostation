#!/usr/bin/env python3
"""Directory hygiene check — detects root-level directories that are
neither tracked by git nor ignored by .gitignore.

This catches "phantom directories" created by AI tools or scripts that
appear at the workspace root without being accounted for.

Run: python3 bin/ssot/dir-hygiene-check.py [--json]
Exit 0 = clean, Exit 1 = violations found.
"""

import json
import subprocess
import sys
from pathlib import Path


def is_tracked(path: str) -> bool:
    r = subprocess.run(
        ["git", "ls-files", "--error-unmatch", path],
        capture_output=True,
        text=True,
    )
    return r.returncode == 0


def is_ignored(path: str) -> bool:
    r = subprocess.run(
        ["git", "check-ignore", path],
        capture_output=True,
        text=True,
    )
    return r.returncode == 0


def main() -> int:
    root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
    scanner = root / "bin/ssot/root-directory-governance-scan.py"
    result = subprocess.run(
        [sys.executable, str(scanner), "--json", "--check"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.stdout:
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            print(result.stdout, end="")
            return result.returncode
    else:
        payload = {"stats": {}, "rows": []}

    violations = [row for row in payload.get("rows", []) if row.get("violation")]
    if "--json" in sys.argv:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if violations else 0

    if not violations:
        print("dir-hygiene: PASS (root directories satisfy governance policy)")
        return 0

    print(f"dir-hygiene: FAIL ({len(violations)} root directory violation(s))")
    for row in violations:
        print(f"  ?? {row['path']}/ ({row['disposition']})")
    print()
    print("Register the directory in the root governance policy, or remove/track the shadow surface.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
