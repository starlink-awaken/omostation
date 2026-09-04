#!/usr/bin/env python3
"""phase-link-quick-run — 链路闭环工具一键运行。

一键运行 Phase 1-3 链路闭环工具:
- 决策收件箱
- 桥接运行时
- 防腐管道
- 场景卡接线
- 价值追踪
- 自进化循环

Usage:
    python3 bin/gac/phase-link-quick-run.py [--phase <1|2|3>] [--json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

PHASE_TOOLS = {
    "phase1": [
        {"name": "decision_inbox", "command": ["python3", "bin/cockpit", "decide", "list"]},
        {"name": "bridge_runtime", "command": ["python3", "bin/gac/bridge-runtime.py", "--status"]},
    ],
    "phase2": [
        {"name": "corrosion_pipeline", "command": ["python3", "bin/gac/corrosion-pipeline-connector.py", "--to-inbox"]},
        {"name": "scene_journey", "command": ["python3", "bin/gac/scene-journey-connector.py", "--auto-create"]},
    ],
    "phase3": [
        {"name": "value_tracker", "command": ["python3", "bin/gac/value-tracker.py", "--update-north-star"]},
        {"name": "self_evolution", "command": ["python3", "bin/gac/self-evolution-loop.py", "--cycle"]},
    ],
}


def run_tool(tool: dict) -> dict:
    """运行单个工具。"""
    try:
        result = subprocess.run(
            tool["command"],
            capture_output=True, timeout=30, cwd=REPO,
        )
        return {
            "name": tool["name"],
            "status": "ok" if result.returncode == 0 else "fail",
            "returncode": result.returncode,
        }
    except Exception as e:
        return {
            "name": tool["name"],
            "status": "error",
            "error": str(e),
        }


def main():
    parser = argparse.ArgumentParser(description="链路闭环一键运行")
    parser.add_argument("--phase", choices=["1", "2", "3", "all"], default="all")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    tools = []
    if args.phase in ("1", "all"):
        tools.extend(PHASE_TOOLS["phase1"])
    if args.phase in ("2", "all"):
        tools.extend(PHASE_TOOLS["phase2"])
    if args.phase in ("3", "all"):
        tools.extend(PHASE_TOOLS["phase3"])

    results = [run_tool(t) for t in tools]
    all_ok = all(r["status"] == "ok" for r in results)

    output = {
        "overall": "PASS" if all_ok else "FAIL",
        "tools": results,
    }

    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"Phase Link Quick Run: {output['overall']}")
        for r in results:
            icon = "✅" if r["status"] == "ok" else "❌"
            print(f"  {icon} {r['name']}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
