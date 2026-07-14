#!/usr/bin/env python3
"""P83 R1: governance history insight tool.

读取 .omo/_knowledge/governance-history.jsonl (gov entries 含 total_score),
输出:
- 评分趋势 (按日聚合 A+/A/B/C/D/F 分布)
- 非 100 分数异常点 (含时间戳 + 当时的 watchlist)
- 等级变迁 (从首条到最后一条)
- 月度汇总 + 80%+ 健康率统计

使用:
  python3 bin/gac/governance-history-insight.py
  python3 bin/gac/governance-history-insight.py --days 30
  python3 bin/gac/governance-history-insight.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def parse_entries(path: Path) -> list[dict]:
    """解析 governance-history.jsonl, 兼容单行 + 多行 JSON.

    策略: 用 json.JSONDecoder().raw_decode() 增量扫描, 它能在任意位置找到下一个完整 JSON object.
    """
    entries: list[dict] = []
    decoder = json.JSONDecoder()
    with path.open(encoding="utf-8") as f:
        text = f.read()
    pos = 0
    n = len(text)
    while pos < n:
        # 跳过空白
        while pos < n and text[pos] in " \t\r\n":
            pos += 1
        if pos >= n:
            break
        if text[pos] != "{":
            # 跳到下一个 '{'
            pos += 1
            continue
        try:
            obj, end = decoder.raw_decode(text, pos)
            if isinstance(obj, dict) and "total_score" in obj:
                entries.append(obj)
            pos = end
        except json.JSONDecodeError:
            # 当前位置 '{' 不是完整 JSON 起点, 跳过
            pos += 1
    return entries


def analyze(entries: list[dict], days: int | None = None) -> dict:
    """分析 gov entries, 返回聚合结果."""
    if not entries:
        return {"error": "no entries"}

    # 按日期 + 等级 分组
    by_date_grade: dict[str, Counter] = defaultdict(Counter)
    scores: list[tuple[str, float]] = []  # (timestamp, score)
    watchlist_counts: list[tuple[str, int]] = []
    non_100: list[dict] = []

    for e in entries:
        ts = e.get("timestamp", "")
        date = e.get("date", ts[:10] if ts else "?")
        score = e.get("total_score", 0.0)
        grade = e.get("grade", "?")
        watchlist = e.get("watchlist_count", 0)
        by_date_grade[date][grade] += 1
        scores.append((ts, score))
        watchlist_counts.append((ts, watchlist))
        if score != 100.0:
            non_100.append({
                "timestamp": ts,
                "date": date,
                "score": score,
                "grade": grade,
                "watchlist": watchlist,
                "failing_checks": [
                    c.get("name") for c in e.get("checks", [])
                    if c.get("severity") in ("warn", "fail")
                ],
            })

    # 排序日期
    dates_sorted = sorted(by_date_grade.keys())

    # 最近 N 天
    if days is not None and dates_sorted:
        # 保留最后 N 个日期
        recent_dates = dates_sorted[-days:]
        by_date_grade = {d: by_date_grade[d] for d in recent_dates}

    # 总计
    total = sum(sum(c.values()) for c in by_date_grade.values())
    a_plus_total = sum(c.get("A+", 0) for c in by_date_grade.values())
    a_plus_rate = (a_plus_total / total * 100) if total else 0.0

    # 首尾对比
    first_entry = entries[0]
    last_entry = entries[-1]

    return {
        "total_entries": total,
        "first": {
            "timestamp": first_entry.get("timestamp"),
            "score": first_entry.get("total_score"),
            "grade": first_entry.get("grade"),
        },
        "last": {
            "timestamp": last_entry.get("timestamp"),
            "score": last_entry.get("total_score"),
            "grade": last_entry.get("grade"),
        },
        "a_plus_rate": round(a_plus_rate, 1),
        "grade_distribution": dict(Counter(
            g for c in by_date_grade.values() for g in c.elements()
        )),
        "by_date": {d: dict(c) for d, c in by_date_grade.items()},
        "non_100_count": len(non_100),
        "non_100_sample": non_100[:10],  # 最近 10 个非 100
        "watchlist_max": max((w for _, w in watchlist_counts), default=0),
        "watchlist_avg": round(
            sum(w for _, w in watchlist_counts) / len(watchlist_counts), 2
        ) if watchlist_counts else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="P83: governance history insight")
    parser.add_argument(
        "--file",
        default=".omo/_knowledge/governance-history.jsonl",
        help="governance history jsonl path",
    )
    parser.add_argument("--days", type=int, default=None, help="最近 N 天")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"❌ {path} 不存在")
        return 1

    entries = parse_entries(path)
    result = analyze(entries, args.days)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if "error" in result:
        print(f"❌ {result['error']}")
        return 1

    print("=" * 60)
    print("📊 P83 governance history insight")
    print("=" * 60)
    print(f"📁 解析条目: {result['total_entries']}")
    print()
    print(f"🕐 首条: {result['first']['timestamp']} score={result['first']['score']} grade={result['first']['grade']}")
    print(f"🕐 末条: {result['last']['timestamp']} score={result['last']['score']} grade={result['last']['grade']}")
    print()
    print(f"🏆 A+ 率: {result['a_plus_rate']}%")
    print(f"📈 等级分布: {result['grade_distribution']}")
    print()
    print(f"⚠️  非 100 分数: {result['non_100_count']} 个")
    if result["non_100_sample"]:
        print("   最近 10 个:")
        for s in result["non_100_sample"][:5]:
            failing = ", ".join(s.get("failing_checks", [])) or "(无)"
            print(f"     {s['timestamp']} {s['grade']} ({s['score']}) watchlist={s['watchlist']} 失败: {failing}")
    print()
    print(f"👀 Watchlist: max={result['watchlist_max']} avg={result['watchlist_avg']}")
    print()
    # 日期趋势 (按 A+ 比例排序显示 top + bottom)
    by_date = result["by_date"]
    if by_date:
        # 按日期排序, 每天展示 grade 分布
        print("📅 最近每日等级分布 (按时间正序):")
        for d in sorted(by_date.keys())[-10:]:
            grades = by_date[d]
            grade_str = " ".join(f"{g}:{c}" for g, c in sorted(grades.items()))
            print(f"   {d}  {grade_str}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
