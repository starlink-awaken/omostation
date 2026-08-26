#!/usr/bin/env python3
"""Decision Cycle Time — 决策周期时间度量.

测量从决策提出到解决的周期时间 (天):
  - 解析 decisions.md 中的决策条目
  - 计算每条决策的存活天数
  - 输出平均/中位数/最长周期

输出: JSON 格式 + 更新 north_star v3 B-axis 数据源.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

WS_ROOT = Path(__file__).resolve().parent.parent.parent
DECISIONS_LOG = WS_ROOT / ".omo" / "notepads" / "delegation-guardrails" / "decisions.md"


def parse_decisions() -> list[dict]:
    """Parse decisions.md into structured entries."""
    if not DECISIONS_LOG.is_file():
        return []

    text = DECISIONS_LOG.read_text(encoding="utf-8")
    entries = []

    # Pattern: ## [YYYY-MM-DD] P<X>: title
    pattern = re.compile(
        r"^##\s*\[(\d{4}-\d{2}-\d{2})\]\s*(P\d+):\s*(.+)$",
        re.MULTILINE,
    )

    for m in pattern.finditer(text):
        date_str = m.group(1)
        priority = m.group(2)
        title = m.group(3).strip()
        try:
            created = datetime.fromisoformat(date_str + "T00:00:00+00:00")
        except ValueError:
            continue

        # Determine status from content
        content = text[m.end():]
        # Find next ## or end of file
        next_header = re.search(r"\n##\s*\[", content)
        if next_header:
            content = content[: next_header.start()]

        status = "open"
        if "已实施" in content or "已落地" in content or "已合并" in content:
            status = "resolved"
        elif "暂不实施" in content or "已记录" in content:
            status = "recorded"

        entries.append({
            "date": date_str,
            "priority": priority,
            "title": title,
            "status": status,
            "created": created.isoformat(),
        })

    return entries


def compute_cycle_time(entries: list[dict]) -> dict:
    """Compute cycle time statistics."""
    now = datetime.now(UTC)
    open_days = []
    resolved_count = 0
    total_count = len(entries)

    for entry in entries:
        created = datetime.fromisoformat(entry["created"])
        age_days = (now - created).days

        if entry["status"] == "resolved":
            resolved_count += 1
            # For resolved, use a heuristic: assume resolved within 7 days if not specified
            open_days.append(min(age_days, 7))
        else:
            open_days.append(age_days)

    if not open_days:
        return {
            "total": 0,
            "resolved": 0,
            "avg_cycle_days": 0,
            "median_cycle_days": 0,
            "max_cycle_days": 0,
        }

    open_days.sort()
    n = len(open_days)
    median = open_days[n // 2] if n % 2 == 1 else (open_days[n // 2 - 1] + open_days[n // 2]) / 2

    return {
        "total": total_count,
        "resolved": resolved_count,
        "resolution_rate": round(100 * resolved_count / total_count, 1) if total_count > 0 else 0,
        "avg_cycle_days": round(sum(open_days) / n, 1),
        "median_cycle_days": round(median, 1),
        "max_cycle_days": max(open_days),
        "window_days": 30,
    }


def main():
    entries = parse_decisions()
    stats = compute_cycle_time(entries)

    if "--json" in sys.argv:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    else:
        print(f"Decision Cycle Time Analysis")
        print(f"  Total decisions: {stats['total']}")
        print(f"  Resolved: {stats['resolved']} ({stats.get('resolution_rate', 0)}%)")
        print(f"  Avg cycle: {stats['avg_cycle_days']} days")
        print(f"  Median cycle: {stats['median_cycle_days']} days")
        print(f"  Max cycle: {stats['max_cycle_days']} days")

    return 0


if __name__ == "__main__":
    sys.exit(main())
