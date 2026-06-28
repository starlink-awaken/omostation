#!/usr/bin/env python3
"""P64 R1: dashboard-readiness-summary 工具.

输出 dashboard 卡片所需数据 (JSON 格式), 可被 cockpit dashboard / 第三方工具消费.

设计:
- 读取最近 1 个 readiness 快照
- 读取 trend 报告 (10 快照)
- 输出结构化 JSON, 含 4 类卡片数据:
  1. summary_card: 总分 / 等级 / 趋势 / 异常
  2. dimensions_card: 5 维度当前完成度
  3. alerts_card: 异常告警 (sudden_drop + stdev)
  4. history_card: 最近 5 快照时序
"""

from __future__ import annotations

import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_snapshots(root: Path, max_n: int = 30) -> list[dict]:
    """加载最近 N 个 readiness 快照."""
    log_dir = root / ".omo" / "_log"
    if not log_dir.exists():
        return []
    files = sorted(log_dir.glob("readiness-*.json"), reverse=True)[:max_n]
    snaps = []
    for f in reversed(files):
        try:
            with open(f, encoding="utf-8") as fh:
                snaps.append(json.load(fh))
        except Exception:
            pass
    return snaps


def build_summary(snaps: list[dict], root: Path) -> dict:
    """构建 dashboard 摘要."""
    now = datetime.now(timezone.utc).isoformat()
    if not snaps:
        return {
            "generated_at": now,
            "summary_card": {"score": 0, "grade": "无数据", "trend": "no_data", "alerts": []},
            "dimensions_card": {},
            "alerts_card": [],
            "history_card": [],
        }

    scores = [s.get("score", 0) for s in snaps]
    last = snaps[-1]

    # 趋势判定
    trend = "insufficient_data"
    if len(scores) >= 4:
        recent = scores[-3:]
        prev = scores[:-3] if len(scores) > 3 else scores
        if statistics.mean(recent) < statistics.mean(prev) - 1.0:
            trend = "declining"
        elif statistics.mean(recent) > statistics.mean(prev) + 1.0:
            trend = "improving"
        else:
            trend = "stable"

    # 异常检测
    alerts = []
    # 1. sudden_drop
    for i in range(1, len(scores)):
        delta = scores[i] - scores[i - 1]
        if delta < -5:
            alerts.append({
                "type": "sudden_drop",
                "severity": "high",
                "from": scores[i - 1],
                "to": scores[i],
                "delta": delta,
                "from_ts": snaps[i - 1].get("timestamp"),
                "to_ts": snaps[i].get("timestamp"),
            })
    # 2. stdev 波动
    stdev = statistics.stdev(scores) if len(scores) > 1 else 0
    if stdev > 3:
        alerts.append({
            "type": "high_volatility",
            "severity": "medium",
            "stdev": round(stdev, 2),
            "samples": len(scores),
        })
    # 3. mean < 90
    mean = statistics.mean(scores)
    if mean < 90:
        alerts.append({
            "type": "low_mean",
            "severity": "high",
            "mean": round(mean, 1),
        })

    # summary_card
    summary_card = {
        "score": last.get("score", 0),
        "grade": last.get("grade", ""),
        "phase": last.get("phase", ""),
        "trend": trend,
        "snapshot_count": len(snaps),
        "last_update": last.get("timestamp", ""),
        "alerts": alerts,
    }

    # dimensions_card (5 维)
    dimensions_card = {}
    for dim_name, dim_data in last.get("dimensions", {}).items():
        dimensions_card[dim_name] = {
            "score": dim_data.get("score"),
            "max": dim_data.get("max"),
            "metric": dim_data.get("metric"),
            "percent": round(dim_data.get("score", 0) / max(dim_data.get("max", 1), 1) * 100, 1),
        }

    # history_card (最近 5 快照)
    history_card = [
        {
            "timestamp": s.get("timestamp"),
            "score": s.get("score"),
            "grade": s.get("grade"),
        }
        for s in snaps[-5:]
    ]

    return {
        "generated_at": now,
        "workspace_root": str(root),
        "summary_card": summary_card,
        "dimensions_card": dimensions_card,
        "alerts_card": alerts,
        "history_card": history_card,
        # P70 增: alerts_card (告警历史 24h 聚合)
        "alerts_card": load_alerts_card(root),
        "stats": {
            "count": len(scores),
            "mean": round(mean, 1),
            "median": statistics.median(scores),
            "min": min(scores),
            "max": max(scores),
            "stdev": round(stdev, 2),
        },
    }


def load_alerts_card(root: Path, hours: int = 24) -> dict:
    """P70 增: 告警卡片数据 — 24h 通知 + 抑制统计."""
    from datetime import datetime, timezone, timedelta
    notif_log = root / ".omo" / "_log" / "alert-notifications.jsonl"
    supp_log = root / ".omo" / "_log" / "alert-suppressions.jsonl"
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    def load_recent(path: Path) -> list[dict]:
        records = []
        if not path.exists():
            return records
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        ts = rec.get("timestamp", "")
                        if ts:
                            rec_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                            if rec_dt >= cutoff:
                                records.append(rec)
                    except Exception:
                        pass
        except Exception:
            pass
        return records

    notifs = load_recent(notif_log)
    supps = load_recent(supp_log)
    total = len(notifs) + len(supps)
    supp_rate = (len(supps) / total) if total > 0 else 0.0
    by_level = {}
    for rec in notifs:
        level = rec.get("level", "?")
        by_level[level] = by_level.get(level, 0) + 1
    return {
        "window_hours": hours,
        "notifications": len(notifs),
        "suppressions": len(supps),
        "suppression_rate": round(supp_rate, 3),
        "by_level": by_level,
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Dashboard readiness summary")
    parser.add_argument("root", nargs="?", default=".", help="workspace root")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument("--output", help="output file (default stdout)")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not (root / ".omo").exists():
        print(f"❌ .omo/ not found at {root}", file=sys.stderr)
        return 1

    snaps = load_snapshots(root)
    summary = build_summary(snaps, root)

    if args.format == "json":
        output = json.dumps(summary, indent=2, ensure_ascii=False)
    else:
        # text 格式: 简洁卡片
        sc = summary["summary_card"]
        lines = [
            "=" * 60,
            f"📊 governance readiness 摘要 @ {summary['generated_at']}",
            "=" * 60,
            f"  Score: {sc['score']}/100  Grade: {sc['grade']}",
            f"  Phase: {sc['phase']}  Trend: {sc['trend']}",
            f"  Snapshots: {sc['snapshot_count']}  Last: {sc['last_update']}",
            f"  Alerts: {len(sc['alerts'])}",
            "",
            "--- 5 维度 ---",
        ]
        for name, d in summary["dimensions_card"].items():
            lines.append(f"  {name:<20s} {d['score']:>3d}/{d['max']:<3d} ({d['percent']:.1f}%)  metric={d['metric']}")
        # P70 增: alerts_card
        ac = summary["alerts_card"]
        lines.append("")
        lines.append("--- 告警 (24h) ---")
        lines.append(f"  通知: {ac['notifications']}  抑制: {ac['suppressions']}  抑制率: {ac['suppression_rate'] * 100:.1f}%")
        if ac["by_level"]:
            levels = " ".join(f"{k}={v}" for k, v in sorted(ac["by_level"].items()))
            lines.append(f"  按级别: {levels}")
        output = "\n".join(lines)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())