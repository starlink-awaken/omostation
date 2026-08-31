#!/usr/bin/env python3
"""orchestrator.py — 统一编排器入口.

合并 3 个编排器为单一入口:
- unified-orchestrator: 信号链 + 治理链 + 维护链
- pipeline-orchestrator: 信号→场景→旅程→价值→进化
- governance-orchestrator: 合规→修复→报告

用法:
    python3 bin/gac/orchestrator.py --run-all
    python3 bin/gac/orchestrator.py --chain signal
    python3 bin/gac/orchestrator.py --chain governance
    python3 bin/gac/orchestrator.py --chain maintenance
    python3 bin/gac/orchestrator.py --chain value
    python3 bin/gac/orchestrator.py --status
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Chain definitions
CHAINS = {
    "signal": {
        "description": "信号链: 日历扫描 → 信号路由 → 场景触发",
        "steps": [
            ("calendar_scan", "bin/bc-os/signal_router.py --calendar .omo/_delivery/personal-signals/calendars/events.ics --json"),
            ("scene_trigger", "bin/gac/signal-scene-connector.py --auto-trigger-all"),
        ],
    },
    "governance": {
        "description": "治理链: 合规检查 → 自动修复 → 报告",
        "steps": [
            ("compliance", "bin/gac/gac-local-gate.py"),
            ("drift_check", "bin/gac/gac-drift.py"),
        ],
    },
    "maintenance": {
        "description": "维护链: 探测器心跳 → 异常告警 → 自动修复",
        "steps": [
            ("probe_heartbeat", "bin/gac/probe-heartbeat-monitor.py --status"),
            ("auto_fix", "bin/gac/auto-fix-loop.py --dry-run"),
        ],
    },
    "value": {
        "description": "价值链: 价值记录 → 进化提案 → 实施",
        "steps": [
            ("evolution_cycle", "bin/gac/auto-evolution-engine.py --cycle"),
        ],
    },
}


def run_chain(chain_name: str, dry_run: bool = False) -> dict:
    """Run a specific chain."""
    chain = CHAINS.get(chain_name)
    if not chain:
        return {"ok": False, "error": f"Unknown chain: {chain_name}"}

    results = {
        "chain": chain_name,
        "description": chain["description"],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "steps": [],
        "ok": True,
    }

    for step_name, cmd in chain["steps"]:
        step_result = {"name": step_name, "command": cmd}
        if not dry_run:
            try:
                result = subprocess.run(
                    cmd.split(), capture_output=True, text=True,
                    cwd=str(REPO), timeout=120,
                )
                step_result["returncode"] = result.returncode
                step_result["ok"] = result.returncode == 0
                if result.returncode != 0:
                    results["ok"] = False
            except Exception as e:
                step_result["ok"] = False
                step_result["error"] = str(e)
                results["ok"] = False
        else:
            step_result["dry_run"] = True
            step_result["ok"] = True

        results["steps"].append(step_result)

    results["finished_at"] = datetime.now(timezone.utc).isoformat()
    return results


def run_all(dry_run: bool = False) -> dict:
    """Run all chains."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "chains": {
            name: run_chain(name, dry_run) for name in CHAINS
        },
    }


def show_status() -> int:
    """Show orchestrator status."""
    print("统一编排器状态")
    print("=" * 60)
    print()
    for name, chain in CHAINS.items():
        print(f"  [{name}] {chain['description']}")
        for step_name, cmd in chain["steps"]:
            print(f"    - {step_name}: {cmd.split()[0]}")
        print()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="统一编排器入口")
    parser.add_argument("--run-all", action="store_true", help="运行所有链")
    parser.add_argument("--chain", choices=list(CHAINS.keys()), help="运行指定链")
    parser.add_argument("--status", action="store_true", help="显示状态")
    parser.add_argument("--dry-run", action="store_true", help="干跑")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    if args.status:
        return show_status()

    if args.chain:
        result = run_chain(args.chain, args.dry_run)
    else:
        result = run_all(args.dry_run)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if args.chain:
            print(f"链 [{result['chain']}]: {'OK' if result['ok'] else 'FAIL'}")
            for step in result["steps"]:
                status = "OK" if step.get("ok") else "FAIL"
                print(f"  [{status}] {step['name']}")
        else:
            for name, chain in result.get("chains", {}).items():
                status = "OK" if chain.get("ok") else "FAIL"
                print(f"  [{status}] {name}: {chain.get('description', '')}")

    return 0 if (args.chain and result.get("ok")) or (not args.chain) else 1


if __name__ == "__main__":
    sys.exit(main())
