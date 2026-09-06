#!/usr/bin/env python3
"""
危险 rebase 检测 — pre-rebase hook.

使用:
  python bin/gac/check-dangerous-rebase.py --base <base> --onto <onto>

退出码:
  0 = 安全
  1 = 危险 (阻断)
"""

import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="危险 rebase 检测")
    parser.add_argument("--base", required=True, help="rebase base")
    parser.add_argument("--onto", default="", help="rebase onto")
    args = parser.parse_args()

    # 检查 rebase 目标是否为 main
    if args.onto in ("main", "origin/main", "upstream/main"):
        print(f"❌ 拒绝 rebase onto {args.onto}", file=sys.stderr)
        print("   应走 merge/PR 合流，而非 rebase", file=sys.stderr)
        return 1

    # 检查 base 是否为 HEAD 的祖先
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", args.base, "HEAD"],
        capture_output=True,
    )
    if result.returncode != 0:
        print(f"❌ base {args.base} 不是 HEAD 的祖先", file=sys.stderr)
        print("   rebase 会重写历史，请先确认", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
