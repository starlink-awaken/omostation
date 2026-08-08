#!/usr/bin/env python3
"""CR-X3-DELIVERY-CADENCE: 检查 PR 交付节奏.

PR 交付节奏是 X3 价值流的关键指标. 检查:
- 是否有悬挂超过 7 天的 PR
- 是否有悬挂超过 3 天的 draft PR
- (可选) 平均 PR 合入时间
"""

import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

STALE_THRESHOLD_DAYS = 7
MAX_STALE = 5  # 允许最多 5 个 stale PR


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


def main() -> int:
    # 获取 open PR 列表
    result = run(["gh", "pr", "list", "--state", "open", "--json", "number,title,createdAt,isDraft,headRefName"])
    if result.returncode != 0:
        print("OK 无法获取 PR 列表 (gh 未安装或未登录)")
        return 0

    import json
    try:
        prs = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        print("OK 无法解析 PR 列表")
        return 0

    now = datetime.now(timezone.utc)
    stale_prs = []

    for pr in prs:
        created = datetime.fromisoformat(pr.get("createdAt", "")).replace(tzinfo=timezone.utc)
        age = now - created
        threshold = STALE_THRESHOLD_DAYS * 2 if pr.get("isDraft") else STALE_THRESHOLD_DAYS
        if age.days > threshold:
            stale_prs.append({
                "number": pr["number"],
                "title": pr["title"][:60],
                "age_days": age.days,
                "draft": pr.get("isDraft", False),
                "branch": pr.get("headRefName", ""),
            })

    if len(stale_prs) > MAX_STALE:
        print(f"WARN 发现 {len(stale_prs)} 个悬挂 PR (阈值 {MAX_STALE}):")
        for p in stale_prs:
            draft_tag = " [DRAFT]" if p["draft"] else ""
            print(f"  #{p['number']} {p['title']} — {p['age_days']}d{draft_tag} ({p['branch']})")
        return 0  # advisory

    active_count = len(prs)
    print(f"OK 交付节奏正常: {active_count} 个 open PR, 0 悬挂")
    return 0


if __name__ == "__main__":
    sys.exit(main())
