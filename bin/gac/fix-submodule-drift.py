#!/usr/bin/env python3
"""fix-submodule-drift.py — 检测并报告 submodule 漂移."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]


def check_submodule_drift(root: Path) -> dict:
    proc = subprocess.run(
        ["git", "submodule", "status", "--recursive"],
        capture_output=True,
        text=True,
        cwd=root,
    )
    lines = proc.stdout.strip().splitlines()
    issues = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        status = line[0] if line else ""
        parts = line.lstrip("+- ").split()
        git_hash = parts[0] if parts else ""
        path = parts[1] if len(parts) > 1 else ""
        if status in {"+", "-", "?"}:
            issues.append(
                {
                    "path": path,
                    "status": status,
                    "git_hash": git_hash,
                    "issue": {
                        "+": "modified",
                        "-": "uninitialized",
                        "?": "untracked",
                    }[status],
                }
            )
    return {
        "total_submodules": len(lines),
        "issue_count": len(issues),
        "issues": issues,
        "untracked_count": sum(1 for i in issues if i["issue"] == "untracked"),
        "modified_count": sum(1 for i in issues if i["issue"] == "modified"),
        "uninitialized_count": sum(1 for i in issues if i["issue"] == "uninitialized"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check submodule drift")
    parser.add_argument("--root", type=Path, default=WORKSPACE)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--fix", action="store_true")
    args = parser.parse_args(argv)
    report = check_submodule_drift(args.root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.check and report["issue_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
