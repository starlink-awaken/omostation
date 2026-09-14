#!/usr/bin/env python3
"""panorama-quick-check — 8D 全景入口一键检查。

快速验证 5 个全景入口的可用性:
1. cockpit panorama
2. cockpit compass trace
3. cockpit project inspect
4. cockpit journey
5. make gac-local-gate

Usage:
    python3 bin/gac/panorama-quick-check.py [--json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

ENTRIES = [
    {"name": "panorama", "command": ["cockpit", "panorama"]},
    {"name": "compass_trace", "command": ["cockpit", "compass", "trace", "GOAL-001"]},
    {"name": "project_inspect", "command": ["cockpit", "project", "inspect", "omo"]},
    {"name": "journey_validate", "command": ["make", "journey-validate"]},
    {"name": "gac_gate", "command": ["make", "gac-local-gate"]},
]


def check_entry(entry: dict) -> dict:
    """检查单个入口。"""
    try:
        result = subprocess.run(
            entry["command"],
            capture_output=True, timeout=10, cwd=REPO,
        )
        return {
            "name": entry["name"],
            "status": "ok" if result.returncode == 0 else "fail",
            "returncode": result.returncode,
        }
    except Exception as e:
        return {
            "name": entry["name"],
            "status": "error",
            "error": str(e),
        }


def main():
    parser = argparse.ArgumentParser(description="8D 全景快速检查")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    results = [check_entry(e) for e in ENTRIES]
    all_ok = all(r["status"] == "ok" for r in results)

    output = {
        "overall": "PASS" if all_ok else "FAIL",
        "entries": results,
    }

    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"Panorama Quick Check: {output['overall']}")
        for r in results:
            icon = "✅" if r["status"] == "ok" else "❌"
            print(f"  {icon} {r['name']}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
