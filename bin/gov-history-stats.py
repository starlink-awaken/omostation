#!/usr/bin/env python3
"""P91 R1: governance-history 趋势深化 (30 天 + grade 变迁).

读取 .omo/_knowledge/governance-history.jsonl (P83 governance-history-insight 的深化版),
输出:
- 30 天聚合 (vs P88 weekly 窗口, 30 天有更长视野)
- Grade 变迁图 (W23→W26 演进)
- Health 类别均值变化 (lint/tests/debt/knowledge/tasks 5 类)
- 与 P88 gov-trend-report 的差异: 30 天窗口 + 类别细分

使用:
  python3 bin/gov-history-stats.py
  python3 bin/gov-history-stats.py --json
  python3 bin/gov-history-stats.py --days 30
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


def parse_entries(path: Path) -> list[dict]:
    """解析 governance-history.jsonl (兼容多行 JSON)."""
    entries: list[dict] = []
    decoder = json.JSONDecoder()
    if not path.exists():
        return entries
    text = path.read_text(encoding="utf-8")
    pos = 0
    n = len(text)
    while pos < n:
        while pos < n and text[pos] in " \t\r\n":
            pos += 1
        if pos >= n:
            break
        if text[pos] != "{":
            pos += 1
            continue
        try:
            obj, end = decoder.raw_decode(text, pos)
            if isinstance(obj, dict) and "total_score" in obj:
                entries.append(obj)
            pos = end
        except json.JSONDecodeError:
            pos += 1
    return entries


def by_date(entries: list[dict]) -> dict[str, list[dict]]:
    """按日期分组."""
    by_d: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        ts = e.get("timestamp", "")
        if len(ts) >= 10:
            by_d[ts[:10]].append(e)
    return dict(by_d)


def category_trend(entries: list[dict]) -> dict[str, list[float]]:
    """按 check 类别统计 score 趋势 (5 类)."""
    cat_by_date: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for e in entries:
        ts = e.get("timestamp", "")
        if len(ts) < 10:
            continue
        date = ts[:10]
        for c in e.get("checks", []):
            cat = c.get("category", "unknown")
            score = c.get("score", 0.0)
            cat_by_date[date][cat].append(score)
    # 计算每日类别均值
    cat_trend: dict[str, list[float]] = defaultdict(list)
    for cat in ("lint", "tests", "debt", "knowledge", "tasks", "agora"):
        trend = []
        for date in sorted(cat_by_date.keys()):
            scores = cat_by_date[date].get(cat, [])
            if scores:
                trend.append(round(sum(scores) / len(scores), 1))
        if trend:
            cat_trend[cat] = trend
    return dict(cat_trend)


def grade_transitions(by_d: dict[str, list[dict]]) -> list[dict]:
    """计算每日 grade 分布 (按 A+/A/B/C/D/F 比例)."""
    transitions = []
    for date in sorted(by_d.keys()):
        grades = Counter()
        for e in by_d[date]:
            grades[e.get("grade", "?")] += 1
        total = sum(grades.values())
        if total == 0:
            continue
        transitions.append({
            "date": date,
            "total": total,
            "a_plus_pct": round(grades.get("A+", 0) / total * 100, 1),
            "a_pct": round(grades.get("A", 0) / total * 100, 1),
            "b_pct": round(grades.get("B", 0) / total * 100, 1),
            "c_pct": round(grades.get("C", 0) / total * 100, 1),
            "d_pct": round(grades.get("D", 0) / total * 100, 1),
            "f_pct": round(grades.get("F", 0) / total * 100, 1),
        })
    return transitions


def main() -> int:
    parser = argparse.ArgumentParser(description="P91: gov history stats 深化")
    parser.add_argument("--file", default=".omo/_knowledge/governance-history.jsonl")
    parser.add_argument("--days", type=int, default=30, help="最近 N 天")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"❌ {path} 不存在")
        return 1

    entries = parse_entries(path)
    if not entries:
        print("❌ 无 governance entries")
        return 1

    # 按日期过滤最近 N 天
    now = datetime.now(tz=timezone.utc)
    cutoff = now - timedelta(days=args.days)
    recent_entries = []
    for e in entries:
        ts = e.get("timestamp", "")
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt >= cutoff:
                recent_entries.append(e)
        except Exception:
            pass

    by_d = by_date(recent_entries)
    transitions = grade_transitions(by_d)
    cat_trend = category_trend(recent_entries)

    result = {
        "window_days": args.days,
        "total_recent": len(recent_entries),
        "date_count": len(by_d),
        "transitions": transitions,
        "category_trend": cat_trend,
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print("=" * 60)
    print(f"📊 P91 gov history stats ({args.days} 天)")
    print("=" * 60)
    print(f"📁 最近 {args.days} 天: {len(recent_entries)} entries, {len(by_d)} 天")
    print()
    if transitions:
        print("📅 Grade 比例变迁:")
        print(f"  {'日期':<12s}  {'A+':>6s}  {'A':>6s}  {'B':>6s}  {'C':>6s}  {'D':>6s}  {'F':>6s}")
        for t in transitions[-15:]:  # 最近 15 天
            print(f"  {t['date']:<12s}  {t['a_plus_pct']:>5.1f}%  {t['a_pct']:>5.1f}%  "
                  f"{t['b_pct']:>5.1f}%  {t['c_pct']:>5.1f}%  {t['d_pct']:>5.1f}%  {t['f_pct']:>5.1f}%")
    print()
    if cat_trend:
        print("🔧 类别趋势 (按 check category):")
        for cat, trend in cat_trend.items():
            n_days = len(trend)
            avg = round(sum(trend) / n_days, 1) if trend else 0
            latest = trend[-1] if trend else 0
            first = trend[0] if trend else 0
            delta = round(latest - first, 1)
            sign = "+" if delta > 0 else ""
            print(f"   {cat:<12s} {n_days:>3d}天 avg={avg:>5.1f}  latest={latest:>5.1f}  delta={sign}{delta}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
