#!/usr/bin/env python3
"""P88 R3: governance-history 趋势报告工具.

读取 .omo/_knowledge/governance-history.jsonl (P83 governance-history-insight 的深度版),
输出:
- 按周/月聚合 (grade 分布 + score 趋势 + 失败 check 频率)
- 健康度回归检测 (近 N 次 score 趋势)
- 输出 markdown 报告 (可贴入 ADR 或 closeout)

使用:
  python3 bin/gov-trend-report.py
  python3 bin/gov-trend-report.py --window weekly
  python3 bin/gov-trend-report.py --json
  python3 bin/gov-trend-report.py --markdown > report.md
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

WINDOWS = ["daily", "weekly", "monthly"]


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


def window_key(ts: str, window: str) -> str:
    """返回日期分桶 key."""
    if not ts or len(ts) < 7:
        return "unknown"
    if window == "daily":
        return ts[:10]
    if window == "weekly":
        # ISO week: YYYY-Www
        try:
            d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            iso = d.isocalendar()
            return f"{iso[0]}-W{iso[1]:02d}"
        except Exception:
            return ts[:10]
    if window == "monthly":
        return ts[:7]
    return ts[:10]


def analyze(entries: list[dict], window: str) -> dict:
    """按 window 聚合分析."""
    if not entries:
        return {"error": "no entries"}

    by_window: dict[str, list[dict]] = defaultdict(list)
    failing_checks: Counter = Counter()
    score_by_window: dict[str, list[float]] = defaultdict(list)
    grade_by_window: dict[str, Counter] = defaultdict(Counter)
    watchlist_by_window: dict[str, list[int]] = defaultdict(list)

    for e in entries:
        ts = e.get("timestamp", "")
        key = window_key(ts, window)
        by_window[key].append(e)
        score = e.get("total_score", 0.0)
        grade = e.get("grade", "?")
        watchlist = e.get("watchlist_count", 0)
        score_by_window[key].append(score)
        grade_by_window[key][grade] += 1
        watchlist_by_window[key].append(watchlist)
        for c in e.get("checks", []):
            if c.get("severity") in ("warn", "fail"):
                failing_checks[c.get("name")] += 1

    # 排序 key
    sorted_keys = sorted(by_window.keys(), reverse=True)

    # 最近 5 窗口趋势
    recent = []
    for k in sorted_keys[:5][::-1]:
        scores = score_by_window[k]
        grades = grade_by_window[k]
        recent.append({
            "window": k,
            "count": len(by_window[k]),
            "avg_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
            "min_score": min(scores) if scores else 0.0,
            "max_score": max(scores) if scores else 0.0,
            "grades": dict(grades),
            "avg_watchlist": round(sum(watchlist_by_window[k]) / len(watchlist_by_window[k]), 2) if watchlist_by_window[k] else 0,
        })

    # 趋势检测: 最近 3 窗口 vs 之前 3 窗口
    trend_signal = "stable"
    if len(sorted_keys) >= 6:
        recent_3_avg = sum(sum(score_by_window[k]) / len(score_by_window[k]) for k in sorted_keys[:3]) / 3
        prior_3_avg = sum(sum(score_by_window[k]) / len(score_by_window[k]) for k in sorted_keys[3:6]) / 3
        diff = recent_3_avg - prior_3_avg
        if diff > 2:
            trend_signal = f"improving (+{diff:.1f})"
        elif diff < -2:
            trend_signal = f"regressing ({diff:.1f})"

    return {
        "total_entries": len(entries),
        "window": window,
        "window_count": len(by_window),
        "windows": sorted_keys,
        "recent": recent,
        "trend_signal": trend_signal,
        "top_failing_checks": dict(failing_checks.most_common(10)),
    }


def render_markdown(result: dict) -> str:
    """输出 markdown 报告."""
    if "error" in result:
        return f"# 治理趋势报告\n\n❌ {result['error']}\n"
    lines = [
        "# 治理趋势报告 (P88 R3)",
        "",
        f"**总条目**: {result['total_entries']}",
        f"**窗口**: {result['window']}",
        f"**窗口数**: {result['window_count']}",
        f"**趋势信号**: {result['trend_signal']}",
        "",
        "## 最近 5 窗口",
        "",
        "| 窗口 | 次数 | 平均分 | 最低 | 最高 | 等级分布 | 平均 watchlist |",
        "|------|------|-------|------|------|---------|--------------|",
    ]
    for r in result["recent"]:
        grades_str = " ".join(f"{g}:{c}" for g, c in sorted(r["grades"].items()))
        lines.append(
            f"| {r['window']} | {r['count']} | {r['avg_score']:.1f} | {r['min_score']:.1f} | "
            f"{r['max_score']:.1f} | {grades_str} | {r['avg_watchlist']:.2f} |"
        )
    lines.append("")
    if result["top_failing_checks"]:
        lines.append("## Top 失败 check")
        lines.append("")
        for name, count in result["top_failing_checks"].items():
            lines.append(f"- **{name}**: {count} 次")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="P88: governance trend report")
    parser.add_argument("--file", default=".omo/_knowledge/governance-history.jsonl",
                        help="governance history jsonl")
    parser.add_argument("--window", choices=WINDOWS, default="weekly",
                        help="时间窗口")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--markdown", action="store_true", help="Markdown 报告")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"❌ {path} 不存在")
        return 1

    entries = parse_entries(path)
    result = analyze(entries, args.window)

    if args.markdown:
        print(render_markdown(result))
        return 0
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    # human-readable
    print("=" * 60)
    print(f"📊 P88 governance trend report ({args.window})")
    print("=" * 60)
    if "error" in result:
        print(f"❌ {result['error']}")
        return 1
    print(f"📁 总条目: {result['total_entries']}")
    print(f"📅 窗口数: {result['window_count']}")
    print(f"📈 趋势信号: {result['trend_signal']}")
    print()
    print("最近 5 窗口:")
    for r in result["recent"]:
        grades_str = " ".join(f"{g}:{c}" for g, c in sorted(r["grades"].items()))
        print(f"  {r['window']:<12s}  count={r['count']:>3d}  "
              f"avg={r['avg_score']:.1f}  min={r['min_score']:.1f}  "
              f"max={r['max_score']:.1f}  watchlist={r['avg_watchlist']:.2f}")
        print(f"    grades: {grades_str}")
    print()
    if result["top_failing_checks"]:
        print("Top 失败 check:")
        for name, count in result["top_failing_checks"].items():
            print(f"   {name:<40s} {count:>4d} 次")
    return 0


if __name__ == "__main__":
    sys.exit(main())
