#!/usr/bin/env python3
"""全链路流水线编排器 — 信号→场景→旅程→价值→进化。

连接所有组件形成闭环:
1. 扫描信号源 (日历/inbox)
2. 路由到场景卡
3. 触发 Journey 执行
4. 记录价值
5. 反馈到进化引擎

用法:
    python3 bin/gac/pipeline-orchestrator.py --run-once
    python3 bin/gac/pipeline-orchestrator.py --calendar events.ics
    python3 bin/gac/pipeline-orchestrator.py --status
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]  # bin/gac/script.py → bin/gac → bin → workspace
STATE_FILE = REPO / ".omo" / "state" / "pipeline-state.jsonl"


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO))


def scan_calendar(calendar_path: Path) -> list[dict]:
    """扫描日历并返回路由结果。"""
    if not calendar_path.exists():
        return []
    cmd = [sys.executable, str(REPO / "bin" / "bc-os" / "signal_router.py"),
           "--calendar", str(calendar_path), "--json"]
    result = run_cmd(cmd)
    if result.returncode != 0:
        return []
    try:
        data = json.loads(result.stdout)
        return data.get("routed", [])
    except json.JSONDecodeError:
        return []


def trigger_journey(scene_id: str, signal: dict) -> dict:
    """触发场景的 Journey。"""
    result = run_cmd([
        sys.executable, str(REPO / "bin" / "gac" / "signal-scene-connector.py"),
        "--scene", scene_id,
    ])
    return {
        "scene_id": scene_id,
        "signal_id": signal.get("signal_id", ""),
        "title": signal.get("title", ""),
        "ok": result.returncode == 0,
        "output": result.stdout.strip()[:200],
    }


def record_value(task_id: str, minutes: int, description: str) -> dict:
    """记录价值。"""
    result = run_cmd([
        sys.executable, str(REPO / "bin" / "gac" / "value-tracker.py"),
        "--record", str(minutes),
        "--task", task_id,
        "--description", description,
    ])
    if result.returncode == 0:
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            pass
    return {"ok": False}


def run_evolution_cycle() -> dict:
    """运行进化引擎周期。"""
    result = run_cmd([
        sys.executable, str(REPO / "bin" / "gac" / "auto-evolution-engine.py"),
        "--cycle",
    ])
    return {"ok": result.returncode == 0, "output": result.stdout.strip()[:300]}


def run_once(calendar_path: Path | None = None) -> dict:
    """运行一次完整流水线。"""
    timestamp = datetime.now(timezone.utc).isoformat()
    results = {
        "timestamp": timestamp,
        "signals_routed": 0,
        "journeys_triggered": 0,
        "value_recorded": 0,
        "evolution_cycle": False,
    }

    # Step 1: Scan calendar
    calendar = calendar_path or (REPO / ".omo" / "_delivery" / "personal-signals" / "calendars" / "events.ics")
    signals = scan_calendar(calendar)
    results["signals_routed"] = len(signals)

    # Step 2: Trigger journeys for each signal
    for signal in signals:
        scene_id = signal.get("source_scene", "")
        if scene_id and scene_id != "knowledge-ingest":
            journey_result = trigger_journey(scene_id, signal)
            if journey_result["ok"]:
                results["journeys_triggered"] += 1
                # Step 3: Record value (estimate 30 min saved per journey)
                value_result = record_value(
                    task_id=signal.get("signal_id", ""),
                    minutes=30,
                    description=f"Auto: {signal.get('title', '')}",
                )
                if value_result.get("ok"):
                    results["value_recorded"] += 1

    # Step 4: Run evolution cycle
    if results["value_recorded"] > 0:
        evo_result = run_evolution_cycle()
        results["evolution_cycle"] = evo_result.get("ok", False)

    # Save state
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(results, ensure_ascii=False) + "\n")

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="全链路流水线编排器")
    parser.add_argument("--run-once", action="store_true", help="Run one pipeline cycle")
    parser.add_argument("--calendar", type=Path, help="Path to .ics calendar file")
    parser.add_argument("--status", action="store_true", help="Show pipeline status")
    args = parser.parse_args()

    if args.run_once:
        results = run_once(args.calendar)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    if args.status:
        if STATE_FILE.exists():
            records = []
            with open(STATE_FILE, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            print(f"Pipeline runs: {len(records)}")
            if records:
                latest = records[-1]
                print(f"Latest: {latest['timestamp']}")
                print(f"  Signals: {latest['signals_routed']}")
                print(f"  Journeys: {latest['journeys_triggered']}")
                print(f"  Value: {latest['value_recorded']}")
        else:
            print("No pipeline runs yet")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
