#!/usr/bin/env python3
"""Risk Profile Router — infer PR risk level from staged files.

Usage:
    python3 bin/gac/risk-profile.py --staged
    python3 bin/gac/risk-profile.py --files docs/README.md projects/ecos/src/...
"""

import argparse
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]

LOW_RISK_PREFIXES = ("docs/", ".github/", "README.md", "CHANGELOG.md")
MEDIUM_RISK_PREFIXES = ("bin/gac/", "bin/ssot/", "bin/agent-workflow.py")
HIGH_RISK_PREFIXES = (".omo/", "projects/", "runtime/", "kos/", "config/")

RISK_ORDER = ("low", "medium", "high")


def _staged_files_git() -> list[str]:
    try:
        import subprocess
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except Exception:
        pass
    return []


def infer_risk(files: list[str]) -> str:
    if not files:
        return "medium"
    for path in files:
        normalized = path.strip()
        if any(normalized.startswith(prefix) for prefix in HIGH_RISK_PREFIXES):
            return "high"
        if any(normalized.startswith(prefix) for prefix in MEDIUM_RISK_PREFIXES):
            return "medium"
        if any(normalized.startswith(prefix) for prefix in LOW_RISK_PREFIXES) or normalized.endswith(".md"):
            continue
        if normalized:
            return "medium"
    return "low"


def main() -> int:
    parser = argparse.ArgumentParser(description="Risk Profile Router")
    parser.add_argument("--staged", action="store_true", help="Infer risk from git staged files")
    parser.add_argument("--files", nargs="*", help="Explicit file paths")
    args = parser.parse_args()

    files = args.files or []
    if args.staged:
        files = _staged_files_git()
    risk = infer_risk(files)
    print(risk)
    return 0


if __name__ == "__main__":
    sys.exit(main())
