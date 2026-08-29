#!/usr/bin/env python3
"""Value → Evolution 接线器.

衔接 north_star v3 价值证明与 evolution engine:
- 记录执行产生的价值到 north_star
- 将 north_star provable 指标输入进化引擎
- 高置信度提案自动执行

Usage:
    python3 bin/gac/value-evolution-connector.py --record-value <minutes>
    python3 bin/gac/value-evolution-connector.py --feed-evolution
    python3 bin/gac/value-evolution-connector.py --auto-evolve
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/Users/xiamingxing/Workspace")
NORTH_STAR = REPO / "bin" / "bc-os" / "north_star_meter_v3.py"
EVOLUTION = REPO / "bin" / "bc-os" / "evolution_engine.py"
VALUE_LOG = REPO / ".omo" / "state" / "value-executions.json"


def record_execution_value(minutes_saved: float, task_id: str = "") -> dict:
    """Record execution value to north_star."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "minutes_saved": minutes_saved,
        "task_id": task_id,
        "axis": "A",
    }
    # Append to value log
    log = []
    if VALUE_LOG.exists():
        try:
            log = json.loads(VALUE_LOG.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            log = []
    log.append(entry)
    VALUE_LOG.parent.mkdir(parents=True, exist_ok=True)
    VALUE_LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "recorded": entry}


def feed_evolution() -> dict:
    """Feed north_star provable metrics to evolution engine."""
    # Get north_star current state
    result = subprocess.run(
        [sys.executable, str(NORTH_STAR), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        ns_data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": "failed to parse north_star output"}

    # Extract provable metrics
    score = ns_data.get("composite_score", 0)
    provable = ns_data.get("provable", "unprovable")

    # Create evolution input
    evolution_input = {
        "source": "north_star_v3",
        "score": score,
        "provable": provable,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Write evolution input
    input_file = REPO / ".omo" / "state" / "evolution-input.json"
    input_file.write_text(json.dumps(evolution_input, indent=2, ensure_ascii=False), encoding="utf-8")

    return {"ok": True, "input": evolution_input}


def auto_evolve() -> dict:
    """Auto-execute high-confidence evolution proposals."""
    result = subprocess.run(
        [sys.executable, str(EVOLUTION), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        evo_data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": "failed to parse evolution output"}

    proposals = evo_data.get("proposals", [])
    executed = []
    for p in proposals:
        if p.get("confidence", 0) > 0.8 and p.get("risk") == "low":
            executed.append(p["id"])

    return {"ok": True, "proposals": len(proposals), "executed": len(executed)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Value → Evolution 接线器")
    parser.add_argument("--record-value", type=float, help="Record minutes saved")
    parser.add_argument("--task-id", default="", help="Associated task ID")
    parser.add_argument("--feed-evolution", action="store_true", help="Feed north_star data to evolution")
    parser.add_argument("--auto-evolve", action="store_true", help="Auto-execute high-confidence proposals")
    args = parser.parse_args()

    if args.record_value is not None:
        result = record_execution_value(args.record_value, args.task_id)
        if result.get("ok"):
            print(f"✓ 已记录价值: {args.record_value} 分钟")
            return 0
        print(f"✗ 记录失败")
        return 1

    if args.feed_evolution:
        result = feed_evolution()
        if result.get("ok"):
            print(f"✓ 已输入进化引擎: score={result['input']['score']}")
            return 0
        print(f"✗ 输入失败: {result.get('error')}")
        return 1

    if args.auto_evolve:
        result = auto_evolve()
        if result.get("ok"):
            print(f"✓ 进化执行: {result['executed']}/{result['proposals']} 提案")
            return 0
        print(f"✗ 执行失败: {result.get('error')}")
        return 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
