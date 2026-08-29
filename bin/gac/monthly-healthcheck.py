#!/usr/bin/env python3
"""Monthly Health Check — 每月架构健康检查.

Continuous iteration mechanism:
- Daily: probe-heartbeat-monitor
- Weekly: weekly-review
- Monthly: monthly-healthcheck (full GaC gate + maturity)
- Quarterly: BET review

Usage:
    python3 bin/gac/monthly-healthcheck.py --full
    python3 bin/gac/monthly-healthcheck.py --maturity
    python3 bin/gac/monthly-healthcheck.py --report
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REPORT_FILE = REPO / ".omo" / "_state" / "monthly-healthcheck-latest.json"


def _run_cmd(cmd: list[str]) -> dict:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
        return {"ok": result.returncode == 0, "stdout": result.stdout[:500], "stderr": result.stderr[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def assess_maturity() -> dict:
    """Assess architecture maturity across all dimensions."""
    checks = {
        "probe-heartbeat": _run_cmd(["python3", str(REPO / "bin/gac/probe-heartbeat-monitor.py"), "--status"]),
        "bridge-runtime": _run_cmd(["python3", str(REPO / "bin/gac/bridge-runtime.py"), "--status"]),
        "corrosion": _run_cmd(["python3", str(REPO / "bin/gac/corrosion-pipeline-connector.py"), "--dry-run"]),
        "decision-inbox": _run_cmd(["python3", str(REPO / "bin/cockpit"), "decide", "status"]),
        "value-tracker": _run_cmd(["python3", str(REPO / "bin/gac/value-tracker.py"), "--report"]),
        "self-evolution": _run_cmd(["python3", str(REPO / "bin/gac/self-evolution-loop.py"), "--status"]),
    }
    passed = sum(1 for v in checks.values() if v.get("ok"))
    total = len(checks)
    return {
        "score": f"{passed}/{total}",
        "percentage": round(passed * 100 / total, 1) if total else 0,
        "checks": {k: v.get("ok", False) for k, v in checks.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Monthly Health Check")
    parser.add_argument("--full", action="store_true", help="Full health check")
    parser.add_argument("--maturity", action="store_true", help="Maturity assessment")
    parser.add_argument("--report", action="store_true", help="Show latest report")
    args = parser.parse_args()

    if args.full or args.maturity:
        result = assess_maturity()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.report:
        if not REPORT_FILE.exists():
            print("No report found. Run --full first.")
            return 1
        report = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    main()
