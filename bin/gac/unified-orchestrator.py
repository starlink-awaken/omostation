#!/usr/bin/env python3
"""Unified Orchestration Engine — 统一编排引擎."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STATE_FILE = REPO / ".omo" / "state" / "orchestrator-state.json"


def _run(cmd: list[str], timeout: int = 60) -> dict:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return {"ok": result.returncode == 0, "stdout": result.stdout.strip()[:300]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def run_signal_chain() -> dict:
    """信号 → 场景 → Journey → 价值 → 进化."""
    r1 = _run(["python3", str(REPO / "bin/gac/signal-scene-connector.py"), "--auto-trigger-all"])
    r2 = _run(["python3", str(REPO / "bin/gac/value-tracker.py"), "--record", "15", "--task", "signal-chain"])
    r3 = _run(["python3", str(REPO / "bin/bc-os/evolution-proposal-triage.py"), "--generate"])
    return {"chain": "signal", "steps": [r1, r2, r3], "passed": sum(1 for r in [r1, r2, r3] if r.get("ok"))}


def run_governance_chain() -> dict:
    """防腐 → 收件箱 → 升级 → 批准."""
    r1 = _run(["python3", str(REPO / "bin/gac/corrosion-pipeline-connector.py"), "--dry-run"])
    r2 = _run(["python3", str(REPO / "bin/gac/corrosion-pipeline-connector.py"), "--to-inbox"])
    r3 = _run(["python3", str(REPO / "bin/gac/decision-inbox-sla.py"), "--escalate"])
    r4 = _run(["python3", str(REPO / "bin/bc-os/evolution-proposal-triage.py"), "--auto-approve"])
    return {"chain": "governance", "steps": [r1, r2, r3, r4], "passed": sum(1 for r in [r1, r2, r3, r4] if r.get("ok"))}


def run_maintenance_chain() -> dict:
    """心跳 → 休眠扫描 → 回顾 → 进化."""
    r1 = _run(["python3", str(REPO / "bin/gac/probe-heartbeat-monitor.py"), "--status"])
    r2 = _run(["python3", str(REPO / "bin/gac/dormant-cleanup-scanner.py"), "--scan"])
    r3 = _run(["python3", str(REPO / "bin/gac/weekly-review.py"), "--generate"])
    r4 = _run(["python3", str(REPO / "bin/gac/self-evolution-loop.py"), "--cycle"])
    return {"chain": "maintenance", "steps": [r1, r2, r3, r4], "passed": sum(1 for r in [r1, r2, r3, r4] if r.get("ok"))}


def run_all() -> dict:
    chains = [run_signal_chain(), run_governance_chain(), run_maintenance_chain()]
    total_passed = sum(c["passed"] for c in chains)
    total_steps = sum(len(c["steps"]) for c in chains)
    connectivity = round(total_passed / total_steps * 100, 1) if total_steps else 0
    return {"connectivity": connectivity, "chains": chains}


def main() -> int:
    parser = argparse.ArgumentParser(description="统一编排引擎")
    parser.add_argument("--run-all", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    if args.run_all:
        result = run_all()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.status:
        print(json.dumps({"status": "active", "version": "1.0"}, indent=2))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
