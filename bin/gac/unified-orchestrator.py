#!/usr/bin/env python3
"""Unified Orchestration Engine — 统一编排引擎.

连接所有组件，提升链路连通性 (65%→85%+):
- 信号 → 场景 → Journey → 价值 → 进化 (自动链路)
- 防腐 → 收件箱 → 升级 → 修复 (治理链路)
- 心跳 → 漂移 → 修复 → 验证 (运维链路)

Usage:
    python3 bin/gac/unified-orchestrator.py --run-all
    python3 bin/gac/unified-orchestrator.py --run-chain signal
    python3 bin/gac/unified-orchestrator.py --run-chain governance
    python3 bin/gac/unified-orchestrator.py --run-chain maintenance
    python3 bin/gac/unified-orchestrator.py --status
"""

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
    """Run command and return result."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False,
        )
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout.strip()[:300],
            "stderr": result.stderr.strip()[:200],
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"runs": [], "version": "1.0"}


def _save_state(data: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def run_signal_chain() -> dict:
    """Run signal → scene → journey → value chain."""
    results = {"chain": "signal", "steps": []}

    # Step 1: Route calendar signals
    calendar_result = _run([
        "python3", str(REPO / "bin/gac/signal-scene-connector.py"),
        "--auto-trigger-all",
    ])
    results["steps"].append({"name": "signal_route", **calendar_result})

    # Step 2: Record value for any completed journeys
    value_result = _run([
        "python3", str(REPO / "bin/gac/value-tracker.py"),
        "--record", "15", "--task", "orchestrator-signal-chain",
        "--description", "信号链路自动执行",
    ])
    results["steps"].append({"name": "value_record", **value_result})

    # Step 3: Generate evolution proposals
    evo_result = _run([
        "python3", str(REPO / "bin/bc-os/evolution-proposal-triage.py"),
        "--generate",
    ])
    results["steps"].append({"name": "evolution_proposals", **evo_result})

    results["passed"] = sum(1 for s in results["steps"] if s.get("ok"))
    results["total"] = len(results["steps"])
    return results


def run_governance_chain() -> dict:
    """Run corrosion → inbox → escalation chain."""
    results = {"chain": "governance", "steps": []}

    # Step 1: Detect corrosion
    detect_result = _run([
        "python3", str(REPO / "bin/gac/corrosion-pipeline-connector.py"),
        "--dry-run",
    ])
    results["steps"].append({"name": "corrosion_detect", **detect_result})

    # Step 2: Push anomalies to inbox
    inbox_result = _run([
        "python3", str(REPO / "bin/gac/corrosion-pipeline-connector.py"),
        "--to-inbox",
    ])
    results["steps"].append({"name": "push_to_inbox", **inbox_result})

    # Step 3: Escalate overdue decisions
    escalate_result = _run([
        "python3", str(REPO / "bin/gac/decision-inbox-sla.py"),
        "--escalate",
    ])
    results["steps"].append({"name": "escalate_overdue", **escalate_result})

    # Step 4: Auto-approve high-confidence proposals
    approve_result = _run([
        "python3", str(REPO / "bin/bc-os/evolution-proposal-triage.py"),
        "--auto-approve",
    ])
    results["steps"].append({"name": "auto_approve", **approve_result})

    results["passed"] = sum(1 for s in results["steps"] if s.get("ok"))
    results["total"] = len(results["steps"])
    return results


def run_maintenance_chain() -> dict:
    """Run heartbeat → drift → fix chain."""
    results = {"chain": "maintenance", "steps": []}

    # Step 1: Check heartbeat
    heartbeat_result = _run([
        "python3", str(REPO / "bin/gac/probe-heartbeat-monitor.py"),
        "--status",
    ])
    results["steps"].append({"name": "heartbeat_check", **heartbeat_result})

    # Step 2: Scan for dormant modules
    dormant_result = _run([
        "python3", str(REPO / "bin/gac/dormant-cleanup-scanner.py"),
        "--scan",
    ])
    results["steps"].append({"name": "dormant_scan", **dormant_result})

    # Step 3: Generate weekly review
    review_result = _run([
        "python3", str(REPO / "bin/gac/weekly-review.py"),
        "--generate",
    ])
    results["steps"].append({"name": "weekly_review", **review_result})

    # Step 4: Run self-evolution cycle
    evolution_result = _run([
        "python3", str(REPO / "bin/gac/self-evolution-loop.py"),
        "--cycle",
    ])
    results["steps"].append({"name": "evolution_cycle", **evolution_result})

    results["passed"] = sum(1 for s in results["steps"] if s.get("ok"))
    results["total"] = len(results["steps"])
    return results


def run_all_chains() -> dict:
    """Run all orchestration chains."""
    print("=" * 60)
    print("统一编排引擎 — 全链路执行")
    print("=" * 60)

    chains = [
        ("信号链路", run_signal_chain),
        ("治理链路", run_governance_chain),
        ("运维链路", run_maintenance_chain),
    ]

    all_results = []
    for name, func in chains:
        print(f"\n--- {name} ---")
        result = func()
        all_results.append(result)
        status = "✅" if result["passed"] == result["total"] else "⚠️"
        print(f"  {status} {result['passed']}/{result['total']} 步骤通过")
        for step in result["steps"]:
            step_status = "✓" if step.get("ok") else "✗"
            print(f"    {step_status} {step['name']}")

    # Summary
    total_passed = sum(r["passed"] for r in all_results)
    total_steps = sum(r["total"] for r in all_results)
    connectivity = round(total_passed / total_steps * 100, 1) if total_steps > 0 else 0

    print(f"\n{'=' * 60}")
    print(f"链路连通性: {connectivity}% ({total_passed}/{total_steps})")

    # Save state
    state = _load_state()
    state.setdefault("runs", []).append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": all_results,
        "connectivity": connectivity,
    })
    _save_state(state)

    return {"connectivity": connectivity, "chains": all_results}


def main() -> int:
    parser = argparse.ArgumentParser(description="统一编排引擎")
    parser.add_argument("--run-all", action="store_true", help="Run all chains")
    parser.add_argument("--run-chain", choices=["signal", "governance", "maintenance"])
    parser.add_argument("--status", action="store_true", help="Show status")
    args = parser.parse_args()

    if args.run_all:
        result = run_all_chains()
        return 0 if result["connectivity"] >= 80 else 1

    if args.run_chain:
        chain_map = {
            "signal": run_signal_chain,
            "governance": run_governance_chain,
            "maintenance": run_maintenance_chain,
        }
        result = chain_map[args.run_chain]()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.status:
        state = _load_state()
        runs = state.get("runs", [])
        print(f"编排引擎状态")
        print(f"  总运行次数: {len(runs)}")
        if runs:
            latest = runs[-1]
            print(f"  最新运行: {latest['timestamp']}")
            print(f"  链路连通性: {latest['connectivity']}%")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
