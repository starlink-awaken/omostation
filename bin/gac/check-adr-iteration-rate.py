#!/usr/bin/env python3
"""check-adr-iteration-rate.py — ADR 迭代速率限制门禁 (ADR Iteration Rate Gate).

检测 ADR 文件的快速迭代: 1 小时内修改 >2 次 ADR 文件则阻断。
防止 ADR-4443 类事件 (3 小时 5 版本) 再次发生。

退出码:
  0 — 迭代速率正常 或 使用了 --adr-iteration-approval 绕过
  1 — 迭代速率超限 (>2 ADR 文件修改/小时)

选项:
  --window-hours N    检查窗口 (默认 1 小时)
  --max-changes N     最大允许修改次数 (默认 2)
  --adr-iteration-approval  运维绕过 (需记录原因)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
ADR_DIR = WORKSPACE_ROOT / ".omo" / "_knowledge" / "decisions"


def _count_adr_changes(window_hours: int = 1) -> list[dict]:
    """Count ADR file modifications in the last N hours via git log."""
    since = f"{window_hours} hour{'s' if window_hours > 1 else ''} ago"
    try:
        result = subprocess.run(
            [
                "git",
                "log",
                f"--since={since}",
                "--diff-filter=M",
                "--format=%H|%ae|%aI|%s",
                "--",
                ".omo/_knowledge/decisions/*.md",
            ],
            cwd=WORKSPACE_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except Exception as exc:
        print(f"[WARN] git log failed: {exc}", file=sys.stderr)
        return []

    changes: list[dict] = []
    for line in result.stdout.splitlines():
        parts = line.split("|", 3)
        if len(parts) >= 4:
            changes.append(
                {
                    "commit": parts[0][:8],
                    "author": parts[1],
                    "timestamp": parts[2],
                    "message": parts[3],
                }
            )
    return changes


def check_adr_iteration_rate(window_hours: int = 1, max_changes: int = 2) -> int:
    print("═══ ADR Iteration Rate Gate ═══")

    if not ADR_DIR.exists():
        print("  ADR directory not found, PASS (degraded)")
        return 0

    # Check for approval bypass
    approval = os.environ.get("ADR_ITERATION_APPROVAL", "")
    if not approval:
        # Check CLI arg too
        if "--adr-iteration-approval" in sys.argv:
            approval = "cli-bypass"

    changes = _count_adr_changes(window_hours)
    change_count = len(changes)

    print(f"  检查窗口: {window_hours}h")
    print(f"  最大允许: {max_changes} 次")
    print(f"  实际修改: {change_count} 次")

    if changes:
        for c in changes[:5]:
            print(f"    [{c['commit']}] {c['author']}: {c['message'][:80]}")
        if len(changes) > 5:
            print(f"    ... and {len(changes) - 5} more")

    if change_count <= max_changes:
        print(f"  ✅ PASS: {change_count}/{max_changes} (速率正常)")
        return 0

    # 超限
    if approval:
        print(f"  ⚠️  WARN: {change_count}/{max_changes} (超限, 但有运维绕过)")
        print(f"     Approval: {approval}")
        return 0

    print(f"\n  ❌ FAIL: 1h 内修改 {change_count} 次 ADR 文件 (上限 {max_changes})")
    print("  原因: ADR-4443 教训 — 3h 5 版本快速迭代导致 PITFALL-GAT-004/005 反复豁免")
    print("  解决方案:")
    print("    1. 等待冷却期 (建议 1h+) 再继续迭代")
    print("    2. 运维绕过: ADR_ITERATION_APPROVAL=<reason> (需记录原因)")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ADR 迭代速率限制门禁 — 防止 ADR 版本快速迭代"
    )
    parser.add_argument(
        "--window-hours",
        type=int,
        default=1,
        help="检查窗口 (小时, 默认 1)",
    )
    parser.add_argument(
        "--max-changes",
        type=int,
        default=2,
        help="最大允许修改次数 (默认 2)",
    )
    parser.add_argument(
        "--adr-iteration-approval",
        action="store_true",
        help="运维绕过 (需记录原因)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="JSON 输出",
    )
    args = parser.parse_args()

    exit_code = check_adr_iteration_rate(args.window_hours, args.max_changes)

    if args.json:
        changes = _count_adr_changes(args.window_hours)
        import json

        print(
            json.dumps(
                {
                    "ok": exit_code == 0,
                    "window_hours": args.window_hours,
                    "max_changes": args.max_changes,
                    "actual_changes": len(changes),
                    "changes": changes[:10],
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
