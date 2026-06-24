#!/usr/bin/env python3
"""P68 R2: 告警历史趋势报告.

读 .omo/_log/alert-notifications.jsonl (P66 写入), 生成跨 N 天趋势:
- 按天统计告警数 + 级别分布
- P0/P1/P2 频次 + 触发时间
- 抑制命中率
- 与 P0/P1 频率异常高的日期

使用:
  python3 bin/alert-history.py
  python3 bin/alert-history.py --days 7
  python3 bin/alert-history.py --format json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


def load_notifications(root: Path, days: int) -> list[dict]:
    """读 alert-notifications.jsonl, 过滤最近 N 天."""
    log_file = root / ".omo" / "_log" / "alert-notifications.jsonl"
    if not log_file.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    records = []
    try:
        with open(log_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    ts = d.get("timestamp", "")
                    if ts:
                        rec_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        if rec_dt >= cutoff:
                            records.append(d)
                except Exception:
                    pass
    except Exception:
        pass
    return records


def load_suppressions(root: Path, days: int) -> list[dict]:
    """P69 增: 读 alert-suppressions.jsonl (P69 新增)."""
    log_file = root / ".omo" / "_log" / "alert-suppressions.jsonl"
    if not log_file.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    records = []
    try:
        with open(log_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    ts = d.get("timestamp", "")
                    if ts:
                        rec_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        if rec_dt >= cutoff:
                            records.append(d)
                except Exception:
                    pass
    except Exception:
        pass
    return records


def render_ascii_bar(value: int, max_value: int, width: int = 40) -> str:
    """P69: ASCII 柱状图."""
    if max_value <= 0:
        return ""
    bar_len = int(value / max_value * width)
    return "█" * bar_len + "░" * (width - bar_len)


def analyze_history(records: list[dict], suppressions: list[dict]) -> dict:
    """分析告警历史 (P69 加 suppressions)."""
    by_day: dict[str, Counter] = defaultdict(Counter)
    by_level: Counter = Counter()
    by_type: Counter = Counter()
    peak_days = []

    for rec in records:
        ts = rec.get("timestamp", "")
        day = ts[:10] if ts else "unknown"
        level = rec.get("level", "P3")
        by_day[day][level] += 1
        by_level[level] += 1
        for bt, count in rec.get("by_type", {}).items():
            by_type[bt] += count

    for day, counts in by_day.items():
        critical = counts.get("P0", 0) + counts.get("P1", 0)
        if critical >= 3:
            peak_days.append({"day": day, "critical_count": critical, "breakdown": dict(counts)})

    # P69: 抑制率
    total_actual = sum(by_level.values())
    suppress_count = len(suppressions)
    suppression_rate = suppress_count / (total_actual + suppress_count) if (total_actual + suppress_count) > 0 else 0

    return {
        "total_notifications": total_actual,
        "by_level": dict(by_level),
        "by_type": dict(by_type),
        "by_day": {day: dict(counts) for day, counts in sorted(by_day.items())},
        "peak_days": peak_days,
        "suppression_count": suppress_count,
        "suppression_rate": round(suppression_rate, 3),
        "record_count": len(records),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P68: 告警历史趋势报告"
    )
    parser.add_argument("root", nargs="?", default=".", help="workspace root")
    parser.add_argument("--days", type=int, default=7, help="时间窗口 (天, 默认 7)")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not (root / ".omo").exists():
        print(f"❌ .omo/ not found at {root}")
        return 1

    records = load_notifications(root, args.days)
    suppressions = load_suppressions(root, args.days)
    hist = analyze_history(records, suppressions)

    if args.format == "json":
        output = json.dumps({
            "days": args.days,
            **hist,
        }, indent=2, ensure_ascii=False)
    else:
        lines = [
            "=" * 60,
            f"📊 P69 告警历史趋势报告 (最近 {args.days} 天)",
            "=" * 60,
            f"📁 通知记录数: {hist['record_count']}",
            f"📈 总通知数: {hist['total_notifications']}",
            f"🔕 抑制记录: {hist['suppression_count']}",
            f"📊 抑制率: {hist['suppression_rate'] * 100:.1f}%",
            "",
            "--- 按级别 ---",
        ]
        for level, count in sorted(hist["by_level"].items()):
            lines.append(f"  {level:<8s} {count:>3d}")
        if hist["by_type"]:
            lines.append("")
            lines.append("--- 按类型 ---")
            for atype, count in sorted(hist["by_type"].items(), key=lambda x: -x[1]):
                lines.append(f"  {atype:<25s} {count:>3d}")
        if hist["by_day"]:
            lines.append("")
            lines.append("--- 按天 (最近 7d ASCII 柱状图) ---")
            recent_days = sorted(hist["by_day"].items())[-7:]
            max_total = max(sum(counts.values()) for _, counts in recent_days) if recent_days else 1
            for day, counts in recent_days:
                day_total = sum(counts.values())
                bar = render_ascii_bar(day_total, max_total)
                lines.append(f"  {day}  {bar} {day_total} {dict(counts)}")
        if hist["peak_days"]:
            lines.append("")
            lines.append("🚨 高峰日 (P0+P1 >= 3):")
            for pd in hist["peak_days"]:
                lines.append(f"  {pd['day']}: critical={pd['critical_count']} {pd['breakdown']}")
        output = "\n".join(lines)

    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())