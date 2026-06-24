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


def aggregate(alerts: list[dict], storm_threshold: int = 3, total_threshold: int = 5) -> dict:
    """聚合告警.

    P67 增: storm_threshold / total_threshold 参数化, 级别 P0/P1/P2.

    级别判定:
    - P0 (critical): storm_warnings + total > total_threshold * 2
    - P1 (high):     storm_warnings + total > total_threshold
    - P2 (medium):   storm_warnings || total > total_threshold
    - P3 (low):      其余 (默认 0 告警)
    """
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

    # 告警风暴检测: 同 1h 内同类型 > storm_threshold
    for atype, items in by_type.items():
        hour_buckets = defaultdict(int)
        for item in items:
            ts = item.get("ts", "")
            if ts:
                hour = ts[:13]
                hour_buckets[hour] += 1
        for hour, count in hour_buckets.items():
            if count > storm_threshold:
                storm_warnings.append({
                    "type": atype,
                    "hour": hour,
                    "count": count,
                    "message": f"⚠️  {atype} 在 {hour} 触发 {count} 次, 告警风暴",
                })

    total = sum(len(items) for items in by_type.values())

    # P67: 级别判定
    level = "P3"
    level_reason = "no alerts"
    if total > 0:
        if storm_warnings and total > total_threshold * 2:
            level = "P0"
            level_reason = f"storm + total({total}) > {total_threshold * 2}"
        elif storm_warnings and total > total_threshold:
            level = "P1"
            level_reason = f"storm + total({total}) > {total_threshold}"
        elif storm_warnings or total > total_threshold:
            level = "P2"
            if storm_warnings:
                level_reason = f"storm detected"
            else:
                level_reason = f"total({total}) > {total_threshold}"
        else:
            level = "P3"
            level_reason = f"total({total}) ≤ {total_threshold}"

    return {
        "total_alerts": total,
        "by_type": {k: len(v) for k, v in by_type.items()},
        "by_type_detail": dict(by_type),
        "by_hour": dict(sorted(by_hour.items())),
        "storm_warnings": storm_warnings,
        "alert_count_per_type": dict(Counter(
            item["type"] for alert in alerts for item in alert.get("alerts", [])
        )),
        "level": level,
        "level_reason": level_reason,
        "thresholds": {
            "storm_threshold": storm_threshold,
            "total_threshold": total_threshold,
        },
    }


def is_suppressed(root: Path, level: str, suppression_minutes: int) -> tuple[bool, dict | None]:
    """P68 增: 告警抑制 — 检查最近 N 分钟是否已通知同级别.

    返回: (是否抑制, 最近通知记录)
    """
    notif_log = root / ".omo" / "_log" / "alert-notifications.jsonl"
    if not notif_log.exists():
        return False, None
    import json as _json
    from datetime import datetime, timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=suppression_minutes)
    try:
        with open(notif_log, encoding="utf-8") as f:
            lines = f.readlines()
        # 从后向前找最近同级别通知
        for line in reversed(lines[-50:]):  # 限制 50 行
            try:
                rec = _json.loads(line.strip())
                rec_level = rec.get("level", "P3")
                if rec_level != level:
                    continue
                ts = rec.get("timestamp", "")
                if ts:
                    rec_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if rec_dt >= cutoff:
                        return True, rec
            except Exception:
                pass
    except Exception:
        pass
    return False, None


def emit_notification(root: Path, agg: dict, window_hours: int,
                     suppression_minutes: int = 60) -> int:
    """P66 增: 主动通知 — 告警风暴时调 omo event emit.

    触发条件 (P67 级别判定):
    - P0/P1/P2 都触发
    - P3 (默认) 不触发

    P68 抑制:
    - 同级别在 suppression_minutes 内已通知 → 抑制
    - 返回: 0=未触发, 1=触发, 2=抑制
    """
    import json as _json
    from subprocess import run as _run
    level = agg.get("level", "P3")
    if level == "P3":
        return 0

    # P68 抑制检查
    suppressed, prev_record = is_suppressed(root, level, suppression_minutes)
    now_iso = datetime.now(timezone.utc).isoformat()
    if suppressed:
        # P69: 抑制记录走 OMO event log, 不再直接写 .omo/_log/
        suppress_payload = {
            "timestamp": now_iso,
            "level": level,
            "total_alerts": agg.get("total_alerts"),
            "suppression_minutes": suppression_minutes,
            "prev_record_ts": prev_record.get("timestamp") if prev_record else None,
            "storm_count": len(agg.get("storm_warnings", [])),
        }
        _emit_event(
            "governance_alert_suppressed",
            suppress_payload,
        )
        return 2  # 抑制标记

    payload = {
        "window_hours": window_hours,
        "total_alerts": agg.get("total_alerts"),
        "by_type": agg.get("by_type"),
        "storm_count": len(agg.get("storm_warnings", [])),
        "level": agg.get("level", "P3"),
        "level_reason": agg.get("level_reason", ""),
        "thresholds": agg.get("thresholds", {}),
        "timestamp": now_iso,
    }

    # 通知通过 OMO event 持久化 (SSOT: .omo/_knowledge/omo-events.jsonl)
    _emit_event("governance_alert_aggregated", payload)

    return 1


def _emit_event(kind: str, payload: dict) -> None:
    """路由事件到 OMO event log, 避免 direct-omo-io."""
    import json as _json
    from subprocess import run as _run

    try:
        _run(
            ["omo", "event", "emit",
             "--type", kind,
             "--source", "alert-aggregator",
             "--payload", _json.dumps(payload, ensure_ascii=False)],
            timeout=10, capture_output=True,
        )
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P65: 告警聚合 — 避免 alert storm"
    )
    parser.add_argument("root", nargs="?", default=".", help="workspace root")
    parser.add_argument("--window", type=int, default=24, help="时间窗口 (小时, 默认 24)")
    parser.add_argument("--storm-threshold", type=int, default=3,
                        help="P67: 风暴检测阈值 (同 1h 内同类型, 默认 3)")
    parser.add_argument("--total-threshold", type=int, default=5,
                        help="P67: 总告警阈值 (默认 5)")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    parser.add_argument("--output", help="输出文件")
    parser.add_argument("--notify", action="store_true",
                        help="P66: 告警时调 omo event emit + 写 alert-notifications.jsonl")
    parser.add_argument("--suppression-minutes", type=int, default=60,
                        help="P68: 同级别告警抑制时间窗 (分钟, 默认 60)")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not (root / ".omo").exists():
        print(f"❌ .omo/ not found at {root}")
        return 1

    alerts = load_alerts(root, args.window)
    agg = aggregate(alerts, args.storm_threshold, args.total_threshold)

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

    # P66 增: --notify 模式触发主动通知
    if args.notify:
        rc = emit_notification(root, agg, args.window, args.suppression_minutes)
        if rc == 2:
            print("🔕 同级别告警在抑制时间窗内, 跳过通知")
        return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())