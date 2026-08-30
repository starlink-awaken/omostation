#!/usr/bin/env python3
"""Unified Governance View — 统一治理视图.

汇总所有治理指标到单一视图:
- 规则合规性
- 服务健康度
- 链路连通性
- 进化状态
- 风险热力图

Usage:
    python3 bin/gac/unified-governance-view.py --full
    python3 bin/gac/unified-governance-view.py --compliance
    python3 bin/gac/unified-governance-view.py --health
    python3 bin/gac/unified-governance-view.py --connectivity
    python3 bin/gac/unified-governance-view.py --evolution
    python3 bin/gac/unified-governance-view.py --risks
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> dict:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
        return {"ok": result.returncode == 0, "output": result.stdout.strip()[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_compliance() -> dict:
    gac_validate = _run(["python3", str(REPO / "bin/gac/gac-validate.py"), "--gate"])
    script_registry = _run(["python3", str(REPO / "bin/ssot/script-registry.py"), "validate"])
    return {"gac_validate": gac_validate.get("ok"), "script_registry": script_registry.get("ok")}


def get_health() -> dict:
    heartbeat = _run(["python3", str(REPO / "bin/gac/probe-heartbeat-monitor.py"), "--status"])
    return {"heartbeat": heartbeat.get("ok")}


def get_connectivity() -> dict:
    orch = _run(["python3", str(REPO / "bin/gac/unified-orchestrator.py"), "--run-all"])
    return {"orchestrator": orch.get("ok")}


def get_evolution() -> dict:
    evolution = _run(["python3", str(REPO / "bin/bc-os/evolution_engine.py"), "--json"])
    proposals = _run(["python3", str(REPO / "bin/bc-os/proposal-adoption-tracker.py"), "--metrics"])
    return {"evolution_engine": evolution.get("ok"), "proposals": proposals.get("ok")}


def get_risks() -> dict:
    risks = []
    hb = _run(["python3", str(REPO / "bin/gac/probe-heartbeat-monitor.py"), "--status"])
    if not hb.get("ok"):
        risks.append({"type": "heartbeat", "severity": "P1"})
    inbox = _run(["python3", str(REPO / "bin/cockpit"), "decide", "status"])
    if not inbox.get("ok"):
        risks.append({"type": "inbox", "severity": "P2"})
    return {"risks": risks, "total": len(risks)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified Governance View")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--compliance", action="store_true")
    parser.add_argument("--health", action="store_true")
    parser.add_argument("--connectivity", action="store_true")
    parser.add_argument("--evolution", action="store_true")
    parser.add_argument("--risks", action="store_true")
    args = parser.parse_args()

    if args.full:
        dashboard = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "compliance": get_compliance(),
            "health": get_health(),
            "connectivity": get_connectivity(),
            "evolution": get_evolution(),
            "risks": get_risks(),
        }
        print(json.dumps(dashboard, indent=2, ensure_ascii=False))
        return 0

    if args.compliance:
        print(json.dumps(get_compliance(), indent=2))
    elif args.health:
        print(json.dumps(get_health(), indent=2))
    elif args.connectivity:
        print(json.dumps(get_connectivity(), indent=2))
    elif args.evolution:
        print(json.dumps(get_evolution(), indent=2))
    elif args.risks:
        print(json.dumps(get_risks(), indent=2))
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
