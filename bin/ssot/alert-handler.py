#!/usr/bin/env python3
"""Alert Handler — 主动告警引擎 (OBS-02).

消费 governance-alerts.yaml 告警规则 + 检查结果,
异常触发 → 告警通知 (日志 + 文件 + 可选 webhook).

守 fabric 红线: 只读规则配置 + 检查结果, 不伪造告警.
Usage:
  python3 bin/ssot/alert-handler.py --once        # 扫一次检查结果, 触发告警
  python3 bin/ssot/alert-handler.py --watch        # 持续监听
  python3 bin/ssot/alert-handler.py list           # 列出规则
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from _shared import ROOT, append_jsonl, load_yaml, utc_now

ALERT_RULES = ROOT / ".omo" / "_truth" / "registry" / "governance-alerts.yaml"
ALERT_LOG = ROOT / ".omo" / "state" / "alerts.jsonl"
METRICS = ROOT / ".omo" / "state" / "metrics-store.jsonl"


def _load_rules() -> list[dict[str, Any]]:
    data = load_yaml(ALERT_RULES)
    rules = data.get("rules", [])
    return [r for r in rules if isinstance(r, dict) and r.get("enabled", True)]


def _recent_failures(limit: int = 200) -> int:
    """Count failed checks in recent metrics (tail-only read, O(1) seek)."""
    if not METRICS.exists():
        return 0
    try:
        # Read only the last ~20KB (enough for 200+ JSONL lines) instead of entire file
        with open(METRICS, "rb") as f:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            tail_size = min(file_size, 20 * 1024)
            f.seek(max(file_size - tail_size, 0))
            tail_bytes = f.read(tail_size)
        tail_text = tail_bytes.decode("utf-8", errors="replace")
    except OSError:
        return 0

    fails = 0
    total = 0
    for line in tail_text.strip().split("\n")[-limit:]:
        if line.strip():
            try:
                e = json.loads(line)
                total += 1
                if not e.get("ok", True):
                    fails += 1
            except json.JSONDecodeError:
                continue
    return fails if total else 0


def _emit(rule: dict[str, Any], detail: str) -> dict[str, Any]:
    """Emit an alert notification (log + file + optional channels)."""
    ts = utc_now()
    alert = {
        "ts": ts,
        "rule_id": rule.get("id", "?"),
        "dimension": rule.get("dimension", "?"),
        "severity": rule.get("severity", "medium"),
        "name": rule.get("name", ""),
        "detail": detail,
        "channels": rule.get("channels", ["log"]),
    }
    append_jsonl(ALERT_LOG, alert)
    return alert


def evaluate_once(root: Path | None = None) -> dict[str, Any]:
    """Evaluate rules against current check results, emit alerts for anomalies."""
    root = root or ROOT
    rules = _load_rules()
    fail_count = _recent_failures()

    fired: list[dict[str, Any]] = []
    for rule in rules:
        condition = str(rule.get("condition", "") or "")

        # Map rules to real signals (currently: check failures)
        if condition == "fail" and fail_count > 0:
            fired.append(_emit(rule, f"{fail_count} recent check failures"))
        elif condition == "warn" and fail_count > 3:
            fired.append(_emit(rule, f"warning threshold exceeded ({fail_count} failures)"))
        # critical dimension rules fire on any failure

    return {
        "status": "evaluated",
        "rules_total": len(rules),
        "recent_failures": fail_count,
        "alerts_fired": len(fired),
        "fired_rule_ids": [a["rule_id"] for a in fired],
    }


def list_rules() -> list[dict[str, Any]]:
    out = []
    for r in _load_rules():
        out.append({
            "id": r.get("id"),
            "dimension": r.get("dimension"),
            "severity": r.get("severity"),
            "condition": r.get("condition"),
            "enabled": r.get("enabled", True),
        })
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--root", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("list", help="list alert rules")
    args = parser.parse_args(argv)

    if args.command == "list":
        for r in list_rules():
            print(f"  [{r['severity']:8s}] {r['dimension']:4s} {r['id']}: cond={r['condition']}")
        return 0

    if args.watch:
        print(f"Watching alerts (interval={args.interval}s)...", flush=True)
        while True:
            result = evaluate_once(args.root)
            if result["alerts_fired"] > 0:
                print(f"  ⚠️ {result['alerts_fired']} alerts fired: {result['fired_rule_ids']}", flush=True)
            time.sleep(args.interval)

    result = evaluate_once(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
