#!/usr/bin/env python3
"""P63 R2: governance-readiness-trend 报告.

读 .omo/_log/readiness-*.json 快照, 生成趋势报告:
- 最近 N 个快照均值/中位数/标准差
- 维度 5 各自趋势
- 异常检测 (单次下降 > 5 分)
- 与 L0 规则关联
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path


def load_snapshots(root: Path, max_n: int = 30) -> list[dict]:
    """加载最近 N 个 readiness 快照."""
    log_dir = root / ".omo" / "_log"
    if not log_dir.exists():
        return []
    files = sorted(log_dir.glob("readiness-*.json"), reverse=True)[:max_n]
    snaps = []
    for f in reversed(files):  # 时序正序
        try:
            with open(f, encoding="utf-8") as fh:
                snaps.append(json.load(fh))
        except Exception:
            pass
    return snaps


def analyze_trend(snaps: list[dict]) -> dict:
    """分析快照趋势."""
    if not snaps:
        return {"count": 0, "mean": 0, "stdev": 0, "median": 0, "min": 0, "max": 0,
                "trend": "no_data", "alerts": []}

    scores = [s.get("score", 0) for s in snaps]
    result = {
        "count": len(scores),
        "mean": statistics.mean(scores),
        "median": statistics.median(scores),
        "min": min(scores),
        "max": max(scores),
        "stdev": statistics.stdev(scores) if len(scores) > 1 else 0,
    }

    # 趋势判定
    if len(scores) >= 4:
        recent = scores[-3:]
        prev = scores[:-3] if len(scores) > 3 else scores
        recent_avg = statistics.mean(recent)
        prev_avg = statistics.mean(prev)
        if recent_avg < prev_avg - 1.0:
            result["trend"] = "declining"
        elif recent_avg > prev_avg + 1.0:
            result["trend"] = "improving"
        else:
            result["trend"] = "stable"
    else:
        result["trend"] = "insufficient_data"

    # 异常检测 (单次下降 > 5)
    alerts = []
    for i in range(1, len(scores)):
        delta = scores[i] - scores[i - 1]
        if delta < -5:
            alerts.append({
                "type": "sudden_drop",
                "from": scores[i - 1],
                "to": scores[i],
                "delta": delta,
                "from_ts": snaps[i - 1].get("timestamp"),
                "to_ts": snaps[i].get("timestamp"),
            })
    result["alerts"] = alerts

    # 维度趋势
    dim_trends = {}
    if snaps:
        last = snaps[-1]
        for dim_name, dim_data in last.get("dimensions", {}).items():
            dim_trends[dim_name] = {
                "current": dim_data.get("score"),
                "max": dim_data.get("max"),
                "metric": dim_data.get("metric"),
                "percent": dim_data.get("score", 0) / max(dim_data.get("max", 1), 1) * 100,
            }
    result["dim_trends"] = dim_trends
    return result


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    if not (root / ".omo").exists():
        print(f"❌ .omo/ not found at {root}")
        return 1

    snaps = load_snapshots(root)
    trend = analyze_trend(snaps)

    print("=" * 70)
    print("📈 P63 governance-readiness-trend 报告")
    print("=" * 70)
    print()
    print(f"📊 快照数: {trend['count']}")
    if trend["count"] == 0:
        print("⚠️  无快照, 请先跑 governance-readiness.py")
        return 0

    print(f"📊 评分统计: mean={trend['mean']:.1f} median={trend['median']:.0f} "
          f"min={trend['min']} max={trend['max']} stdev={trend['stdev']:.2f}")
    print(f"📊 趋势: {trend['trend']}")
    print()

    if trend["alerts"]:
        print("⚠️  异常检测:")
        for a in trend["alerts"]:
            print(f"  - {a['from_ts']} → {a['to_ts']}: {a['from']} → {a['to']} (Δ {a['delta']})")
        print()

    if trend["dim_trends"]:
        print("─" * 70)
        print(f"{'维度':<28s}{'当前':<8s}{'上限':<8s}{'完成度':<10s}{'指标'}")
        print("─" * 70)
        for name, d in trend["dim_trends"].items():
            print(f"{name:<28s}{d['current']:>3d}/{d['max']:<5d}{d['percent']:>5.1f}%     {d['metric']}")
        print("─" * 70)
    print()

    # 与 L0 规则关联
    print("🔗 L0 规则关联:")
    if trend["mean"] >= 90:
        print("  ✅ governance 评分稳态 ≥ 90, 无需告警")
    else:
        print(f"  ⚠️  governance 评分 < 90, 建议检查: {trend['mean']:.1f}")
    if trend["stdev"] > 3:
        print(f"  ⚠️  评分波动 > 3, stdev={trend['stdev']:.2f}, 可能有未发现的不稳定因素")
    return 0


if __name__ == "__main__":
    sys.exit(main())