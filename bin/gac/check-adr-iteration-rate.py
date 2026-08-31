#!/usr/bin/env python3
"""check-adr-iteration-rate.py — ADR 迭代速率限制.

防止 ADR 版本快速迭代 (>2/h). ADR-4443 教训:
3h 内 v4→v8 导致 PITFALL-GAT-004/005 反复豁免.

rule_id: CR-X4-ADR-ITERATION-RATE

逻辑:
  1. git log --since="1 hour ago" --diff-filter=M -- ".omo/_knowledge/decisions/*.md"
  2. 统计修改次数 (空行分隔的 commit 粒度)
  3. > 2 次/小时 → exit 1
  4. --adr-iteration-approval 可绕过

用法:
    python3 bin/gac/check-adr-iteration-rate.py
    python3 bin/gac/check-adr-iteration-rate.py --json
    python3 bin/gac/check-adr-iteration-rate.py --adr-iteration-approval
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ADR_GLOB = ".omo/_knowledge/decisions/*.md"
MAX_CHANGES_PER_HOUR = 2


def _run_git(args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            cwd=str(REPO),
            check=False,
            timeout=10,
        )
        return result.stdout
    except Exception:
        return ""


def count_adr_changes_last_hour() -> int:
    """Count ADR file modifications in the last hour."""
    log = _run_git([
        "log",
        "--since=1 hour ago",
        "--diff-filter=M",
        "--pretty=format:%H",
        "--", ADR_GLOB,
    ])
    # Each line is a commit hash that touched an ADR file
    commits = [line.strip() for line in log.splitlines() if line.strip()]
    return len(commits)


def main() -> int:
    parser = argparse.ArgumentParser(description="ADR 迭代速率限制")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument(
        "--adr-iteration-approval",
        action="store_true",
        help="绕过 ADR 迭代速率限制 (需要审批理由)",
    )
    parser.add_argument(
        "--max-per-hour",
        type=int,
        default=MAX_CHANGES_PER_HOUR,
        help=f"每小时最大 ADR 修改次数 (default: {MAX_CHANGES_PER_HOUR})",
    )
    args = parser.parse_args()

    # Check bypass
    bypass = args.adr_iteration_approval or os.environ.get("ADR_ITERATION_APPROVAL") == "1"
    if bypass:
        result = {
            "status": "bypassed",
            "changes_last_hour": 0,
            "max_per_hour": args.max_per_hour,
            "note": "ADR iteration rate limit bypassed via --adr-iteration-approval",
        }
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("ADR 迭代速率: BYPASSED (--adr-iteration-approval)")
        return 0

    changes = count_adr_changes_last_hour()
    exceeds = changes > args.max_per_hour

    result = {
        "status": "fail" if exceeds else "pass",
        "changes_last_hour": changes,
        "max_per_hour": args.max_per_hour,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        status = "FAIL" if exceeds else "PASS"
        print(f"ADR 迭代速率: {changes}/{args.max_per_hour} changes/hour [{status}]")
        if exceeds:
            print(f"  超过限制: {changes} > {args.max_per_hour}")
            print("  建议: 使用 --adr-iteration-approval 绕过 (需要审批)")

    return 1 if exceeds else 0


if __name__ == "__main__":
    sys.exit(main())
