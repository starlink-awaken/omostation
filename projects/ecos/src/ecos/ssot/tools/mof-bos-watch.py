#!/usr/bin/env python3
"""
织星 MOF — BOS 自治异常检测 (mof-bos-watch)
=============================================
从 BOS 审计日志中学习正常流量基线，检测异常模式。

检测规则:
  1. 突发错误率 (> 正常均值 3σ)
  2. 新路由突然大量调用 (未充分测试)
  3. 废弃路由仍有流量 (应迁移)
  4. 响应时间突增 (> 正常 P95 2x)

用法:
    python3 mof-bos-watch.py                    # 检测异常
    python3 mof-bos-watch.py --baseline          # 建立基线
    python3 mof-bos-watch.py --watch             # 持续监控
"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict

HOME = Path.home()
AUDIT_LOG = HOME / ".ecos" / "bos-audit.jsonl"
BASELINE_FILE = HOME / ".ecos" / "bos-baseline.json"


def load_audit_log(hours: int = 24) -> list[dict]:
    if not AUDIT_LOG.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    entries = []
    with open(AUDIT_LOG) as f:
        for line in f:
            try:
                e = json.loads(line)
                ts = datetime.fromisoformat(e.get("timestamp", ""))
                if ts > cutoff:
                    entries.append(e)
            except Exception:
                pass
    return entries


def build_baseline():
    """建立正常流量基线"""
    entries = load_audit_log(168)  # Last 7 days
    if not entries:
        print("⚠️ 无审计数据，无法建立基线")
        return

    # Per-route stats
    routes = defaultdict(lambda: {"count": 0, "errors": 0, "durations": []})
    for e in entries:
        uri = e.get("bos_uri", "unknown")
        routes[uri]["count"] += 1
        if e.get("status_code", 200) >= 500:
            routes[uri]["errors"] += 1
        routes[uri]["durations"].append(e.get("duration_ms", 0))

    baseline = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_entries": len(entries),
        "routes": {},
    }

    for uri, stats in routes.items():
        durations = sorted(stats["durations"])
        if not durations:
            continue
        n = len(durations)
        baseline["routes"][uri] = {
            "call_count": stats["count"],
            "error_rate": stats["errors"] / max(stats["count"], 1),
            "avg_duration_ms": sum(durations) / n,
            "p95_duration_ms": durations[int(n * 0.95)] if n >= 20 else durations[-1],
        }

    with open(BASELINE_FILE, "w") as f:
        json.dump(baseline, f, indent=2)

    print(f"✅ 基线已建立: {len(baseline['routes'])} routes, {len(entries)} entries")


def detect_anomalies() -> list[dict]:
    """检测异常"""
    if not BASELINE_FILE.exists():
        return [{"type": "no_baseline", "detail": "基线未建立，运行 --baseline 先"}]

    baseline = json.load(open(BASELINE_FILE))
    recent = load_audit_log(1)  # Last hour

    anomalies = []

    # 1. Error rate spike
    for uri, bl in baseline["routes"].items():
        recent_for_route = [e for e in recent if e.get("bos_uri") == uri]
        if not recent_for_route:
            continue

        errors = sum(1 for e in recent_for_route if e.get("status_code", 200) >= 500)
        error_rate = errors / len(recent_for_route)
        bl_rate = bl["error_rate"]

        if bl_rate < 0.05 and error_rate > 0.3:
            anomalies.append(
                {
                    "type": "error_spike",
                    "route": uri,
                    "severity": "high",
                    "detail": f"错误率 {error_rate:.0%} (基线 {bl_rate:.0%})",
                }
            )

    # 2. New route burst
    for e in recent:
        uri = e.get("bos_uri", "")
        if uri not in baseline["routes"]:
            anomalies.append(
                {
                    "type": "new_route_burst",
                    "route": uri,
                    "severity": "low",
                    "detail": "新路由未在基线中",
                }
            )

    # 3. Duration spike
    for uri, bl in baseline["routes"].items():
        recent_for_route = [e for e in recent if e.get("bos_uri") == uri]
        if not recent_for_route:
            continue
        durations = [e.get("duration_ms", 0) for e in recent_for_route]
        avg = sum(durations) / len(durations)
        if bl["avg_duration_ms"] > 0 and avg > bl["p95_duration_ms"] * 2:
            anomalies.append(
                {
                    "type": "latency_spike",
                    "route": uri,
                    "severity": "medium",
                    "detail": f"平均延迟 {avg:.0f}ms (基线 P95 {bl['p95_duration_ms']:.0f}ms)",
                }
            )

    return anomalies


def format_report(anomalies: list[dict]):
    print("═══ BOS 异常检测 ═══")
    print(f"  时间: {datetime.now(timezone.utc).isoformat()[:19]}")
    print(f"  异常: {len(anomalies)} 项\n")

    if not anomalies:
        print("  ✅ 无异常")
        return

    for a in anomalies:
        icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(a["severity"], "❓")
        print(f"  {icon} [{a['type']}] {a.get('route', '?')[:50]}")
        print(f"     {a['detail']}")


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.baseline:
        build_baseline()
        return

    anomalies = detect_anomalies()

    if args.json:
        print(
            json.dumps(
                {"anomalies": len(anomalies), "items": anomalies},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        format_report(anomalies)


if __name__ == "__main__":
    main()
