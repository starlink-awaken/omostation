#!/usr/bin/env python3
"""Unified Governance View — 统一治理视图."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> dict:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
        return {"ok": result.returncode == 0, "output": result.stdout.strip()[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_status() -> dict:
    """Get unified governance status."""
    checks = {
        "probe-heartbeat": _run(["python3", str(REPO / "bin/gac/probe-heartbeat-monitor.py"), "--status"]),
        "bridge-runtime": _run(["python3", str(REPO / "bin/gac/bridge-runtime.py"), "--status"]),
        "corrosion": _run(["python3", str(REPO / "bin/gac/corrosion-pipeline-connector.py"), "--dry-run"]),
        "decision-inbox": _run(["python3", str(REPO / "bin/cockpit"), "decide", "status"]),
        "value-tracker": _run(["python3", str(REPO / "bin/gac/value-tracker.py"), "--report"]),
        "self-evolution": _run(["python3", str(REPO / "bin/gac/self-evolution-loop.py"), "--status"]),
    }
    passed = sum(1 for v in checks.values() if v.get("ok"))
    total = len(checks)
    return {"score": f"{passed}/{total}", "percentage": round(passed / total * 100, 1) if total else 0}


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified Governance View")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    if args.full or args.status:
        result = get_status()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
