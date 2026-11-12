#!/usr/bin/env python3
"""Governance Orchestrator — 治理编排器.

体系化治理重整:
- 统一治理入口
- 自动化治理工作流
- 自进化治理规则
- 全量合规检查

Usage:
    python3 bin/gac/governance-orchestrator.py --full-governance-cycle
    python3 bin/gac/governance-orchestrator.py --compliance-check
    python3 bin/gac/governance-orchestrator.py --auto-remediate
    python3 bin/gac/governance-orchestrator.py --governance-report
    python3 bin/gac/governance-orchestrator.py --status
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]  # bin/gac/x.py → bin/gac → bin → workspace
# 2026-11-12 修: 原为 parents[1] (= <root>/bin), 于是下面所有
# REPO / "bin/..." 都指向 <root>/bin/bin/... —— 与两个同类编排器
# (unified-orchestrator / pipeline-orchestrator 均为 parents[2]) 不一致。
STATE_FILE = REPO / ".omo" / "state" / "governance-orchestrator-state.json"


def _run(cmd: list[str], timeout: int = 60) -> dict:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return {"ok": result.returncode == 0, "output": result.stdout.strip()[:300]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


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


def compliance_check() -> dict:
    """Run full compliance check suite."""
    checks = {
        "gac_validate": _run(["python3", str(REPO / "bin/gac/gac-validate.py"), "--gate"]),
        "script_registry": _run(["python3", str(REPO / "bin/ssot/script-registry.py"), "validate"]),
        "doc_governance": _run(["python3", str(REPO / "bin/ssot/doc-governance-check.py"), "--no-new-warnings"]),
        "interface_check": _run(["python3", str(REPO / "bin/ssot/check-interfaces.py")]),
        "drift_check": _run(["python3", str(REPO / "bin/gac/gac-drift.py")]),
    }

    passed = sum(1 for v in checks.values() if v.get("ok"))
    total = len(checks)

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": {k: v.get("ok", False) for k, v in checks.items()},
        "passed": passed,
        "total": total,
        "compliance_rate": round(passed / total * 100, 1) if total > 0 else 0,
    }


def auto_remediate() -> dict:
    """Auto-remediate common issues."""
    results = []

    # 1. Escalate overdue decisions
    r = _run(["python3", str(REPO / "bin/gac/decision-inbox-sla.py"), "--escalate"])
    results.append({"action": "escalate_decisions", **r})

    # 2. Auto-approve high-confidence proposals
    r = _run(["python3", str(REPO / "bin/bc-os/evolution-proposal-triage.py"), "--auto-approve"])
    results.append({"action": "auto_approve_proposals", **r})

    # 3. Sync drift
    r = _run(["python3", str(REPO / "bin/gac/gac-drift.py")])
    results.append({"action": "drift_sync", **r})

    # 4. Refresh heartbeat
    r = _run(["python3", str(REPO / "bin/gac/probe-heartbeat-monitor.py"), "--status"])
    results.append({"action": "heartbeat_refresh", **r})

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "results": results,
        "remediated": sum(1 for r in results if r.get("ok")),
        "total": len(results),
    }


def generate_governance_report(*, compliance: dict, remediation: dict) -> dict:
    """Assemble a report from already-collected results — no side effects of its own.

    2026-11-12: 原实现自己调 `compliance_check()` + `auto_remediate()`, 于是
    `full_governance_cycle()` 的 Phase 2 刚跑完一遍自动修复, Phase 3 又跑一遍 ——
    升级决策 / 自动批准提案 / 漂移同步 / 心跳刷新全部**双份副作用**。改为由调用方
    传入, 报告组装不再触发任何动作。
    """

    # Get system stats
    services = _run(["grep", "-c", "bos://", str(REPO / ".omo/_truth/registry/services.yaml")])

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "compliance": compliance,
        "remediation": remediation,
        "stats": {
            "total_bos_uris": int(services.get("output", "0")) if services.get("ok") else 0,
            "compliance_rate": compliance.get("compliance_rate", 0),
        },
        "recommendations": [],
    }

    # Generate recommendations
    if compliance.get("compliance_rate", 0) < 80:
        report["recommendations"].append("合规率低于 80%，需要修复治理检查")

    if remediation.get("remediated", 0) < remediation.get("total", 0):
        report["recommendations"].append("部分自动修复失败，需要人工干预")

    if not report["recommendations"]:
        report["recommendations"].append("系统治理状态良好，继续保持")

    return report


def full_governance_cycle() -> dict:
    """Run full governance cycle."""
    print("=" * 60)
    print("治理编排器 — 全量治理循环")
    print("=" * 60)

    # Phase 1: Compliance check
    print("\n[1/3] 合规检查...")
    compliance = compliance_check()
    print(f"  合规率: {compliance['compliance_rate']}% ({compliance['passed']}/{compliance['total']})")

    # Phase 2: Auto-remediation
    print("\n[2/3] 自动修复...")
    remediation = auto_remediate()
    print(f"  修复: {remediation['remediated']}/{remediation['total']}")

    # Phase 3: Report
    print("\n[3/3] 生成报告...")
    report = generate_governance_report(compliance=compliance, remediation=remediation)
    print(f"  建议: {len(report['recommendations'])} 项")

    # Save state
    state = _load_state()
    state.setdefault("cycles", []).append({
        "timestamp": datetime.now(UTC).isoformat(),
        "compliance_rate": compliance["compliance_rate"],
        "remediated": remediation["remediated"],
    })
    _save_state(state)

    print(f"\n{'=' * 60}")
    print("治理循环完成")

    return {"compliance": compliance, "remediation": remediation, "report": report}


def main() -> int:
    parser = argparse.ArgumentParser(description="Governance Orchestrator")
    parser.add_argument("--full-governance-cycle", action="store_true")
    parser.add_argument("--compliance-check", action="store_true")
    parser.add_argument("--auto-remediate", action="store_true")
    parser.add_argument("--governance-report", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    if args.full_governance_cycle:
        result = full_governance_cycle()
        return 0

    if args.compliance_check:
        result = compliance_check()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.auto_remediate:
        result = auto_remediate()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.governance_report:
        compliance = compliance_check()
        remediation = auto_remediate()
        result = generate_governance_report(compliance=compliance, remediation=remediation)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.status:
        state = _load_state()
        cycles = state.get("cycles", [])
        print("治理编排器状态")
        print(f"  总循环数: {len(cycles)}")
        if cycles:
            latest = cycles[-1]
            # 早期版本的状态文件可能缺键 —— 用 get 而不是下标, 否则 --status 会 KeyError。
            print(f"  最新循环: {latest.get('timestamp', 'unknown')}")
            print(f"  合规率: {latest.get('compliance_rate', 'unknown')}%")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
