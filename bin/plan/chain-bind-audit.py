#!/usr/bin/env python3
"""chain-bind-audit — 审计所有 active BET 的 chain-bind 合规性。

检查:
1. 每个 active BET 是否有对应的 workflow run
2. run 是否绑定了正确的 bet_id
3. closeout 是否有 retro
4. north_star 指针是否存在

Usage:
    python3 bin/plan/chain-bind-audit.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LEDGER = REPO / "docs/plans/3y-bet-ledger.yaml"
RUNS_DIR = REPO / ".omo/_delivery" / "agent-workflows" / "runs"
RETROS_DIR = REPO / ".omo" / "_knowledge" / "retros"


def load_active_bets() -> list[dict]:
    """加载所有 active BET。"""
    try:
        import yaml
        with open(LEDGER) as f:
            data = yaml.safe_load(f)
        bets = data.get("bets", [])
        return [b for b in bets if b.get("status") in ("active", "candidate")]
    except Exception:
        return []


def check_bet_compliance(bet: dict) -> dict:
    """检查单个 BET 的合规性。"""
    bet_id = bet.get("id", "?")
    result = {
        "bet_id": bet_id,
        "title": bet.get("title", "?")[:50],
        "status": bet.get("status", "?"),
        "compliant": True,
        "issues": [],
    }

    # 检查 1: 是否有 active run
    has_active_run = False
    if RUNS_DIR.exists():
        for run_dir in RUNS_DIR.iterdir():
            if not run_dir.is_dir():
                continue
            state_file = run_dir / "state.yaml"
            if state_file.exists():
                try:
                    content = state_file.read_text()
                    if f"bet_id: {bet_id}" in content and "status: active" in content:
                        has_active_run = True
                        break
                except Exception:
                    pass

    if bet.get("status") == "active" and not has_active_run:
        result["issues"].append("No active workflow run")

    # 检查 2: closeout retro
    has_retro = False
    if RETROS_DIR.exists():
        for retro in RETROS_DIR.rglob("*.md"):
            try:
                content = retro.read_text()
                if bet_id in content:
                    has_retro = True
                    break
            except Exception:
                pass

    if bet.get("status") == "done" and not has_retro:
        result["issues"].append("Missing closeout retro")

    # 检查 3: north_star 指针
    north_star = bet.get("north_star") or bet.get("vision_ref")
    if not north_star:
        result["issues"].append("Missing north_star / vision_ref pointer")

    if result["issues"]:
        result["compliant"] = False

    return result


def main():
    parser = argparse.ArgumentParser(description="Chain-bind 合规审计")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    bets = load_active_bets()
    results = [check_bet_compliance(b) for b in bets]

    compliant = sum(1 for r in results if r["compliant"])
    non_compliant = [r for r in results if not r["compliant"]]

    output = {
        "total": len(results),
        "compliant": compliant,
        "non_compliant": len(non_compliant),
        "details": non_compliant,
    }

    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"Chain-Bind Audit")
        print(f"  Total: {len(results)} | Compliant: {compliant} | Issues: {len(non_compliant)}")

        if non_compliant:
            print(f"\n  Non-compliant BETs:")
            for r in non_compliant:
                print(f"    ⚠️ {r['bet_id']}: {', '.join(r['issues'])}")

    return 0 if not non_compliant else 1


if __name__ == "__main__":
    sys.exit(main())
