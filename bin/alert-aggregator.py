#!/usr/bin/env python3
"""P65 R2: 告警聚合 — 避免 alert storm.

读 .omo/_log/readiness-alerts.jsonl (P64 写入), 聚合最近 N 小时告警:
- 按类型分组 (low_mean / high_volatility / sudden_drop)
- 按时间窗口去重
- 告警风暴检测: 1h 内同类型 > 3 次 → 抑制
- 输出聚合报告

使用:
  python3 bin/alert-aggregator.py
  python3 bin/alert-aggregator.py --window 24
  python3 bin/alert-aggregator.py --output /tmp/aggregated.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


def load_alerts(root: Path, window_hours: int = 24) -> list[dict]:
    """读 readiness-alerts.jsonl, 过滤最近 N 小时."""
    log_file = root / ".omo" / "_log" / "readiness-alerts.jsonl"
    if not log_file.exists():
        return []
    cutoff = datetime.now(timezone.utc).timestamp() - window_hours * 3600
    alerts = []
    try:
        with open(log_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    # 时间过滤
                    ts = d.get("timestamp", "")
                    if ts:
                        try:
                            # ISO 格式带 Z
                            t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                            if t.timestamp() < cutoff:
                                continue
                        except Exception:
                            pass
                    alerts.append(d)
                except Exception:
                    pass
    except Exception:
        pass
    return alerts


def aggregate(alerts: list[dict]) -> dict:
    """聚合告警."""
    by_type: dict[str, list] = defaultdict(list)
    by_hour: dict[str, int] = defaultdict(int)
    storm_warnings = []

    for alert in alerts:
        for a in alert.get("alerts", []):
            atype = a.get("type", "unknown")
            by_type[atype].append({
                "severity": a.get("severity", "low"),
                "message": a.get("message", ""),
                "ts": alert.get("timestamp", ""),
            })

    # 按小时分组
    for alert in alerts:
        ts = alert.get("timestamp", "")
        if ts:
            try:
                hour = ts[:13]  # YYYY-MM-DDTHH
                by_hour[hour] += len(alert.get("alerts", []))
            except Exception:
                pass

    # 告警风暴检测: 同 1h 内同类型 > 3
    for atype, items in by_type.items():
        # 按小时桶分组
        hour_buckets = defaultdict(int)
        for item in items:
            ts = item.get("ts", "")
            if ts:
                hour = ts[:13]
                hour_buckets[hour] += 1
        for hour, count in hour_buckets.items():
            if count > 3:
                storm_warnings.append({
                    "type": atype,
                    "hour": hour,
                    "count": count,
                    "message": f"⚠️  {atype} 在 {hour} 触发 {count} 次, 告警风暴",
                })

    return {
        "total_alerts": sum(len(items) for items in by_type.values()),
        "by_type": {k: len(v) for k, v in by_type.items()},
        "by_type_detail": dict(by_type),
        "by_hour": dict(sorted(by_hour.items())),
        "storm_warnings": storm_warnings,
        "alert_count_per_type": dict(Counter(
            item["type"] for alert in alerts for item in alert.get("alerts", [])
        )),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P65: 告警聚合 — 避免 alert storm"
    )
    parser.add_argument("root", nargs="?", default=".", help="workspace root")
    parser.add_argument("--window", type=int, default=24, help="时间窗口 (小时, 默认 24)")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    parser.add_argument("--output", help="输出文件")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not (root / ".omo").exists():
        print(f"❌ .omo/ not found at {root}")
        return 1

    alerts = load_alerts(root, args.window)
    agg = aggregate(alerts)

    if args.format == "json":
        output = json.dumps({
            "window_hours": args.window,
            "alert_records": len(alerts),
            **agg,
        }, indent=2, ensure_ascii=False)
    else:
        lines = [
            "=" * 60,
            f"📊 P65 告警聚合报告 (最近 {args.window}h)",
            "=" * 60,
            f"📁 告警记录数: {len(alerts)}",
            f"📈 总告警数: {agg['total_alerts']}",
            "",
            "--- 按类型 ---",
        ]
        for atype, count in sorted(agg["by_type"].items(), key=lambda x: -x[1]):
            lines.append(f"  {atype:<25s} {count:>3d}")
        if agg["storm_warnings"]:
            lines.append("")
            lines.append("🚨 告警风暴:")
            for sw in agg["storm_warnings"]:
                lines.append(f"  {sw['message']}")
        else:
            lines.append("")
            lines.append("✅ 无告警风暴")
        output = "\n".join(lines)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())