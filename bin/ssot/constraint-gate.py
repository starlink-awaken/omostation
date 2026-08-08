#!/usr/bin/env python3
"""Model-Driven Constraint Gate — 模型驱动约束查询 (GOV-03).

Agent 行动前查询治理约束 (governance-checks.yaml + task-policies.yaml),
约束作为 DATA 而非 hardcode: 修改 yaml 即可改变行为, 无需改代码.

守 KISS: 只做只读查询 + 简单规则匹配, 不做执行.
Usage:
  python3 bin/ssot/constraint-gate.py list
  python3 bin/ssot/constraint-gate.py check --check-id CR-X2-GAC-DRIFT
  python3 bin/ssot/constraint-gate.py gate --action-type <type> --action-level <level>
  python3 bin/ssot/constraint-gate.py --json list
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _shared import ROOT, load_yaml

GOVERNANCE_CHECKS = ROOT / ".omo" / "_truth" / "registry" / "governance-checks.yaml"
TASK_POLICIES = ROOT / ".omo" / "_truth" / "registry" / "task-policies.yaml"


def _load_checks() -> list[dict[str, Any]]:
    data = load_yaml(GOVERNANCE_CHECKS)
    # governance-checks.yaml schema: top-level 'checkers' key (X1-X4 checker configs)
    checkers = data.get("checkers", [])
    if not isinstance(checkers, list):
        return []
    return [c for c in checkers if isinstance(c, dict)]


def _load_policies() -> list[dict[str, Any]]:
    data = load_yaml(TASK_POLICIES)
    policies = data.get("policies", [])
    return [p for p in policies if isinstance(p, dict)]


def list_constraints() -> list[dict[str, Any]]:
    """List all constraints from SSOT files."""
    out: list[dict[str, Any]] = []
    for c in _load_checks():
        out.append({
            "source": "governance-checks",
            "id": c.get("id", c.get("name", "?")),
            "enforcement": c.get("severity", "?") or "?",
            "summary": (c.get("description", c.get("summary", "")) or "")[:120],
        })
    for p in _load_policies():
        out.append({
            "source": "task-policies",
            "id": p.get("name", "?"),
            "enforcement": "required",
            "summary": (p.get("summary", "") or "")[:120],
        })
    return out


def check_by_id(check_id: str) -> dict[str, Any] | None:
    """Look up a specific governance check by id."""
    for c in _load_checks():
        cid = c.get("id", c.get("name", ""))
        if cid == check_id:
            return c
    return None


def gate_action(action_type: str, action_level: str) -> dict[str, Any]:
    """Model-driven gate: evaluate a proposed action against SSOT constraints.

    规则 (data-driven, 全部来自 governance-checks + task-policies):
      - governance-checks severity=high → block
      - governance-checks severity=medium → warn
      - task-policies always required → warn

    NOTE (v1): action_type/action_level are accepted for API stability
    but not yet used for per-action matching.  All actions are evaluated
    against the same static rule set.  Per-action filtering is planned
    for when governance-checks gains action-scope metadata.
    """
    checks = _load_checks()

    red_rules: list[str] = []
    gray_rules: list[str] = []

    for c in checks:
        severity = str(c.get("severity", "") or "")
        cid = str(c.get("id", c.get("name", "?")))
        if severity == "high":
            red_rules.append(f"high:{cid}")
        elif severity == "medium":
            gray_rules.append(f"medium:{cid}")
        else:
            gray_rules.append(f"low:{cid}")

    for p in _load_policies():
        gray_rules.append(f"policy:{p.get('name', '?')}")

    decision = "blocked" if red_rules else "allowed"
    return {
        "schema": "constraint-gate/v1",
        "action_type": action_type,
        "action_level": action_level,
        "decision": decision,
        "red_rules": red_rules,
        "gray_rules": gray_rules,
        "rule_count": len(red_rules) + len(gray_rules),
        "source": "model-driven (governance-checks + task-policies)",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="list all constraints")

    chk = sub.add_parser("check", help="check a governance rule by id")
    chk.add_argument("--check-id", required=True)

    g = sub.add_parser("gate", help="evaluate an action against constraints")
    g.add_argument("--action-type", required=True)
    g.add_argument("--action-level", default="S2")

    args = parser.parse_args(argv)
    command = args.command or "list"

    if command == "list":
        items = list_constraints()
        if args.json:
            print(json.dumps({"total": len(items), "constraints": items}, ensure_ascii=False, indent=2))
        else:
            print(f"Constraints ({len(items)}):")
            for it in items:
                print(f"  [{it['enforcement']:8s}] {it['source']:20s} {it['id']}: {it['summary'][:70]}")
        return 0

    if command == "check":
        found = check_by_id(args.check_id)
        if not found:
            print(json.dumps({"error": f"check {args.check_id} not found"}, ensure_ascii=False))
            return 1
        print(json.dumps(found, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    if command == "gate":
        result = gate_action(args.action_type, args.action_level)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(f"Gate: {result['decision'].upper()} — {result['action_type']}/{result['action_level']}")
            for r in result["red_rules"]:
                print(f"  🔴 {r}")
            for g_ in result["gray_rules"]:
                print(f"  🟡 {g_}")
        return 0 if result["decision"] == "allowed" else 2

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
