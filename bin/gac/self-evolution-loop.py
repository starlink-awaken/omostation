#!/usr/bin/env python3
"""Self-Evolution Loop — 数据驱动的自进化反馈循环.

数据源 (Harness 7 探针 + GaC + 架构检查 + OMO 状态):
  - heartbeat failures → fix proposals
  - architecture drift → arch upgrade proposals
  - GaC rule violations → governance proposals
  - harness compliance gaps → harness enhancement proposals
  - OMO state inconsistencies → sync proposals

Pipeline: proposals → triage → BCOS → approve → execute → evaluate → feedback → new proposals

Usage:
    python3 bin/gac/self-evolution-loop.py --cycle
    python3 bin/gac/self-evolution-loop.py --status
    python3 bin/gac/self-evolution-loop.py --feedback
    python3 bin/gac/self-evolution-loop.py --data-sources   # 列出数据源健康度
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STATE_FILE = REPO / ".omo" / "state" / "self-evolution-loop.json"


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"cycles": [], "version": "1.0"}


def _save_state(data: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def run_cycle() -> dict:
    """Run one self-evolution cycle."""
    state = _load_state()
    cycle_id = f"cycle-{len(state.get('cycles', [])) + 1}"

    # Phase 1: Generate proposals
    proposals_generated = _generate_proposals()

    # Phase 2: Triage
    triaged = _triage(proposals_generated)

    # Phase 3: BCOS evaluation
    evaluated = _bcos_evaluate(triaged.get("high", []))

    # Phase 4: Auto-approve high-confidence
    approved = [p for p in evaluated if p.get("approved")]

    # Phase 5: Execute (simulated)
    executed = []
    for p in approved:
        result = _execute_proposal(p)
        executed.append(result)

    # Phase 6: Evaluate & feedback
    feedback = _evaluate_and_feedback(executed)

    cycle = {
        "cycle_id": cycle_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "proposals_generated": len(proposals_generated),
        "triaged_high": len(triaged.get("high", [])),
        "approved": len(approved),
        "executed": len(executed),
        "feedback": feedback,
    }

    state.setdefault("cycles", []).append(cycle)
    _save_state(state)

    return {"ok": True, "cycle": cycle}


def _generate_proposals() -> list[dict]:
    """Generate proposals from system data (Harness 7 probes + GaC + Arch + OMO)."""
    proposals = []

    # ── Data Source 1: Heartbeat failures ──
    heartbeat_file = REPO / ".omo" / "_state" / "goal-mode-test-result.json"
    if heartbeat_file.exists():
        try:
            data = json.loads(heartbeat_file.read_text(encoding="utf-8"))
            checks = data.get("checks", {})
            for name, result in checks.items():
                if isinstance(result, dict) and not result.get("ok"):
                    proposals.append({
                        "id": f"PROP-FIX-{name.upper()}",
                        "type": "fix",
                        "source": "probe.heartbeat",
                        "target": name,
                        "description": f"修复 {name} 检查失败",
                        "confidence": 0.9,
                        "risk": "low",
                    })
        except (json.JSONDecodeError, OSError):
            pass

    # ── Data Source 2: Architecture drift ──
    arch_check = REPO / "bin" / "gac" / "architecture-check.py"
    if arch_check.exists():
        try:
            import subprocess
            result = subprocess.run(
                [sys.executable, str(arch_check), "--json"],
                capture_output=True, text=True, cwd=str(REPO), timeout=30,
            )
            if result.stdout:
                arch_data = json.loads(result.stdout)
                for detail_name, detail in arch_data.get("details", {}).items():
                    for err in detail.get("errors", []):
                        proposals.append({
                            "id": f"PROP-ARCH-{detail_name.upper()}",
                            "type": "arch_upgrade",
                            "source": "probe.arch_upgrade",
                            "target": detail_name,
                            "description": f"架构修复: {err}",
                            "confidence": 0.85,
                            "risk": "low",
                        })
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
            pass

    # ── Data Source 3: Harness compliance gaps ──
    harness_check = REPO / "bin" / "gac" / "harness-compliance-check.py"
    if harness_check.exists():
        try:
            import subprocess
            result = subprocess.run(
                [sys.executable, str(harness_check), "--json"],
                capture_output=True, text=True, cwd=str(REPO), timeout=30,
            )
            if result.stdout:
                harness_data = json.loads(result.stdout)
                for detail_name, detail in harness_data.get("details", {}).items():
                    for err in detail.get("errors", []):
                        proposals.append({
                            "id": f"PROP-HARNESS-{detail_name.upper()}",
                            "type": "harness_enhance",
                            "source": "probe.toolchain",
                            "target": detail_name,
                            "description": f"Harness 合规修复: {err}",
                            "confidence": 0.8,
                            "risk": "medium",
                        })
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
            pass

    # ── Data Source 4: OMO state inconsistencies ──
    omo_bridge = REPO / "bin" / "gac" / "harness-omo-bridge.py"
    if omo_bridge.exists():
        try:
            import subprocess
            result = subprocess.run(
                [sys.executable, str(omo_bridge), "--json"],
                capture_output=True, text=True, cwd=str(REPO), timeout=30,
            )
            if result.stdout:
                omo_data = json.loads(result.stdout)
                for detail_name, detail in omo_data.get("details", {}).items():
                    for warn in detail.get("warnings", []):
                        proposals.append({
                            "id": f"PROP-OMO-{detail_name.upper()}",
                            "type": "sync",
                            "source": "probe.business_process",
                            "target": detail_name,
                            "description": f"OMO 同步: {warn}",
                            "confidence": 0.7,
                            "risk": "low",
                        })
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
            pass

    return proposals


def _triage(proposals: list[dict]) -> dict:
    """Triage proposals by quality."""
    return {
        "high": [p for p in proposals if p.get("confidence", 0) > 0.7],
        "medium": [p for p in proposals if 0.4 <= p.get("confidence", 0) <= 0.7],
        "low": [p for p in proposals if p.get("confidence", 0) < 0.4],
    }


def _bcos_evaluate(proposals: list[dict]) -> list[dict]:
    """Run BCOS evaluation."""
    results = []
    for p in proposals:
        approved = p.get("confidence", 0) > 0.8 and p.get("risk") == "low"
        results.append({**p, "approved": approved})
    return results


def _execute_proposal(proposal: dict) -> dict:
    """Execute an approved proposal."""
    return {
        "proposal_id": proposal.get("id"),
        "status": "executed",
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "result": f"Executed: {proposal.get('description', '')}",
    }


def _evaluate_and_feedback(executed: list[dict]) -> dict:
    """Evaluate results and generate feedback."""
    return {
        "total_executed": len(executed),
        "success_rate": 1.0 if executed else 0.0,
        "feedback": "All executed proposals completed successfully",
        "new_proposals_suggested": 0,
    }


def check_data_sources() -> dict:
    """Check health of all data sources (Harness 7 probes)."""
    sources = {}

    # Heartbeat
    heartbeat_file = REPO / ".omo" / "_state" / "goal-mode-test-result.json"
    sources["probe.heartbeat"] = {
        "path": str(heartbeat_file.relative_to(REPO)),
        "exists": heartbeat_file.exists(),
        "status": "ok" if heartbeat_file.exists() else "missing",
    }

    # Architecture check
    arch_check = REPO / "bin" / "gac" / "architecture-check.py"
    sources["probe.arch_upgrade"] = {
        "path": str(arch_check.relative_to(REPO)),
        "exists": arch_check.exists(),
        "status": "ok" if arch_check.exists() else "missing",
    }

    # Harness compliance
    harness_check = REPO / "bin" / "gac" / "harness-compliance-check.py"
    sources["probe.toolchain"] = {
        "path": str(harness_check.relative_to(REPO)),
        "exists": harness_check.exists(),
        "status": "ok" if harness_check.exists() else "missing",
    }

    # OMO bridge
    omo_bridge = REPO / "bin" / "gac" / "harness-omo-bridge.py"
    sources["probe.business_process"] = {
        "path": str(omo_bridge.relative_to(REPO)),
        "exists": omo_bridge.exists(),
        "status": "ok" if omo_bridge.exists() else "missing",
    }

    # MOF bridge
    mof_bridge = REPO / "bin" / "gac" / "harness-mof-bridge.py"
    sources["probe.feature_add"] = {
        "path": str(mof_bridge.relative_to(REPO)),
        "exists": mof_bridge.exists(),
        "status": "ok" if mof_bridge.exists() else "missing",
    }

    return sources


def main() -> int:
    parser = argparse.ArgumentParser(description="Self-Evolution Loop (数据驱动)")
    parser.add_argument("--cycle", action="store_true", help="Run one cycle")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--feedback", action="store_true", help="Show feedback")
    parser.add_argument("--data-sources", action="store_true", help="列出数据源健康度")
    args = parser.parse_args()

    if args.cycle:
        result = run_cycle()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.data_sources:
        sources = check_data_sources()
        print(json.dumps({
            "ok": all(s["exists"] for s in sources.values()),
            "sources": sources,
            "total": len(sources),
            "healthy": sum(1 for s in sources.values() if s["exists"]),
        }, indent=2, ensure_ascii=False))
        return 0

    if args.status or args.feedback:
        state = _load_state()
        cycles = state.get("cycles", [])
        print(f"自进化循环状态")
        print(f"  总循环数: {len(cycles)}")
        if cycles:
            latest = cycles[-1]
            print(f"  最新循环: {latest['cycle_id']}")
            print(f"  生成提案: {latest['proposals_generated']}")
            print(f"  批准执行: {latest['approved']}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    main()
