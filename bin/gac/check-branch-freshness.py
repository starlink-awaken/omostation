#!/usr/bin/env python3
"""
机制 4 (2026-09-05): 分支新鲜度检测 — 超过 N 天未 rebase 的分支提醒.

使用:
  python bin/gac/check-branch-freshness.py              # 默认 7 天阈值
  python bin/gac/check-branch-freshness.py --max-age-days 3
  python bin/gac/check-branch-freshness.py --json       # JSON 输出 (供 cron/CI)

退出码:
  0 = 所有分支新鲜
  1 = 发现陈旧分支 (提醒, 不阻断)
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone


def get_remote_branches() -> list[dict]:
    """获取远程分支的最后 commit 日期."""
    result = subprocess.run(
        ["git", "for-each-ref",
         "--format=%(refname:short)|%(committerdate:short)|%(committerdate:unix)",
         "refs/remotes/origin/"],
        capture_output=True, text=True, check=True,
    )
    branches = []
    for line in result.stdout.splitlines():
        if not line or "HEAD" in line:
            continue
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        ref, date_str, unix_str = parts
        if ref == "origin/main":
            continue
        try:
            ts = int(unix_str)
        except ValueError:
            continue
        branches.append({
            "ref": ref,
            "date": date_str,
            "ts": ts,
        })
    return branches


def main() -> int:
    parser = argparse.ArgumentParser(description="分支新鲜度检测")
    parser.add_argument("--max-age-days", type=int, default=7,
                        help="超过此天数未更新的分支标记为陈旧 (默认 7)")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    cutoff_ts = (datetime.now(timezone.utc) - timedelta(days=args.max_age_days)).timestamp()
    branches = get_remote_branches()
    stale = [b for b in branches if b["ts"] < cutoff_ts]
    fresh = [b for b in branches if b["ts"] >= cutoff_ts]

    if args.json:
        output = {"stale_count": len(stale), "stale_branches": stale,
                  "fresh_count": len(fresh), "fresh_branches": fresh}
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return 0

    if stale:
        print(f"⚠️ 发现 {len(stale)} 个陈旧远程分支 (>{args.max_age_days} 天未更新):",
              file=sys.stderr)
        for b in stale:
            print(f"   {b['ref']}  (最后 commit: {b['date']})", file=sys.stderr)
        print(f"\n建议: 评估后删除或 rebase", file=sys.stderr)
        return 1

    print(f"✅ 所有 {len(branches)} 个远程分支新鲜 (<{args.max_age_days} 天)",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
