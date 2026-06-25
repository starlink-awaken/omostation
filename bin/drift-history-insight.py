#!/usr/bin/env python3
"""P83 R2: drift history insight tool.

读取 .omo/_control/evolution/drift/ 目录下所有时间戳 JSON, 输出:
- 每天 drift_count 趋势
- drift 类型分布 (entry_drift / doc_drift / etc)
- 最新 5 个 drift 报告
- 持续 drift (跨多次出现)

使用:
  python3 bin/drift-history-insight.py
  python3 bin/drift-history-insight.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def parse_drift_files(drift_dir: Path) -> list[dict]:
    """读取 drift/ 下所有 JSON, 返回报告列表."""
    reports: list[dict] = []
    if not drift_dir.exists():
        return reports
    for f in sorted(drift_dir.glob("*.json")):
        try:
            with f.open(encoding="utf-8") as fh:
                data = json.load(fh)
            data["_file"] = f.name
            reports.append(data)
        except Exception:
            continue
    return reports


def analyze(reports: list[dict]) -> dict:
    """分析 drift 报告."""
    if not reports:
        return {"error": "no reports"}

    by_date: dict[str, list[dict]] = defaultdict(list)
    kind_counts: Counter = Counter()
    drift_by_kind: Counter = Counter()  # kinds where drift=True
    persistent_drifts: dict[str, int] = defaultdict(int)  # kind:key → count

    for r in reports:
        date = r.get("generated_at", "")[:10] or "?"
        by_date[date].append(r)
        results = r.get("results", [])
        for entry in results:
            kind = entry.get("kind", "?")
            kind_counts[kind] += 1
            if entry.get("drift"):
                drift_by_kind[kind] += 1
                # 持久化 drift: 用 (kind, key) 标记
                key = entry.get("plan_ref") or entry.get("expected") or entry.get("name") or ""
                persistent_drifts[f"{kind}:{key}"] += 1

    # 趋势: 每天 drift_count
    trend = []
    for d in sorted(by_date.keys()):
        day_reports = by_date[d]
        max_drift = max((r.get("drift_count", 0) for r in day_reports), default=0)
        avg_drift = sum(r.get("drift_count", 0) for r in day_reports) / len(day_reports) if day_reports else 0
        trend.append({
            "date": d,
            "reports": len(day_reports),
            "max_drift": max_drift,
            "avg_drift": round(avg_drift, 2),
        })

    return {
        "total_reports": len(reports),
        "date_range": f"{min(by_date)} ~ {max(by_date)}" if by_date else "?",
        "kind_distribution": dict(kind_counts),
        "drift_by_kind": dict(drift_by_kind),
        "persistent_drifts": dict(sorted(
            persistent_drifts.items(), key=lambda x: -x[1]
        )[:10]),
        "trend": trend,
        "latest_5": [
            {
                "file": r.get("_file"),
                "ts": r.get("generated_at"),
                "drift_count": r.get("drift_count", 0),
                "kinds": r.get("kinds", 0),
            }
            for r in reports[-5:]
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="P83: drift history insight")
    parser.add_argument(
        "--drift-dir",
        default=".omo/_control/evolution/drift",
        help="drift JSON 目录",
    )
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    drift_dir = Path(args.drift_dir)
    if not drift_dir.exists():
        print(f"❌ {drift_dir} 不存在")
        return 1

    reports = parse_drift_files(drift_dir)
    result = analyze(reports)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if "error" in result:
        print(f"❌ {result['error']}")
        return 1

    print("=" * 60)
    print("📊 P83 drift history insight")
    print("=" * 60)
    print(f"📁 报告总数: {result['total_reports']}")
    print(f"📅 时间范围: {result['date_range']}")
    print()
    print(f"🔍 类别分布: {result['kind_distribution']}")
    print(f"⚠️  漂移按类别: {result['drift_by_kind']}")
    print()
    if result["persistent_drifts"]:
        print("🔁 持续漂移 (按出现次数 top 10):")
        for k, c in result["persistent_drifts"].items():
            print(f"   {k:<60s} {c:>3d}")
        print()
    print("📈 趋势 (按日期):")
    for t in result["trend"][-15:]:  # 最近 15 天
        bar = "█" * t["max_drift"] if t["max_drift"] <= 30 else "█" * 30 + "..."
        print(f"   {t['date']}  reports={t['reports']:>3d}  max={t['max_drift']:>3d}  avg={t['avg_drift']:>5.2f}  {bar}")
    print()
    print("📌 最近 5 个报告:")
    for r in result["latest_5"]:
        print(f"   {r['ts']}  drift={r['drift_count']}  kinds={r['kinds']}  ({r['file']})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
