#!/usr/bin/env python3
"""gac-rule-gate-mapping.py — 规则↔Gate 映射生成 (BET-Y1Q2-T6-01).

扫描 governance-checks.yaml 的规则和 gac-local-gate.py 的 gate checks,
通过 source_ref 匹配建立双向映射.

Output: .omo/_truth/registry/rule-gate-mapping.yaml

Usage:
    python3 bin/gac/gac-rule-gate-mapping.py              # 生成映射
    python3 bin/gac/gac-rule-gate-mapping.py --json        # JSON 输出
    python3 bin/gac/gac-rule-gate-mapping.py --stats       # 统计摘要
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
CHECKS_YAML = WORKSPACE_ROOT / ".omo" / "_truth" / "registry" / "governance-checks.yaml"
GATE_PY = WORKSPACE_ROOT / "bin" / "gac" / "gac-local-gate.py"
OUTPUT_PATH = WORKSPACE_ROOT / ".omo" / "_truth" / "registry" / "rule-gate-mapping.yaml"


def _load_rules() -> list[dict]:
    with open(CHECKS_YAML, encoding="utf-8") as f:
        docs = list(yaml.safe_load_all(f))
    for doc in docs:
        if doc and isinstance(doc, dict):
            if "rules" in doc:
                return doc["rules"]
            if "gac" in doc and isinstance(doc["gac"], dict):
                rules = doc["gac"].get("rules", [])
                if rules:
                    return rules
            if "checkers" in doc:
                return doc["checkers"]
    return []


def _load_gate_ids() -> dict[str, list[str]]:
    """Extract gate_id → [command scripts] from gac-local-gate.py."""
    content = GATE_PY.read_text(encoding="utf-8")
    gates_section = re.search(r'"gates":\s*\[(.*?)\n\s*\]\s*\}', content, re.DOTALL)
    if not gates_section:
        return {}

    block = gates_section.group(0)
    entries = re.findall(
        r'\{"id":\s*"([^"]+)".*?"command":\s*\[([^\]]+)\]',
        block,
        re.DOTALL,
    )

    result = {}
    for gate_id, cmd_str in entries:
        scripts = re.findall(r'"([^"]+(?:\.py|/gac/[^"]+))"', cmd_str)
        result[gate_id] = scripts
    return result


def _build_mapping(
    rules: list[dict], gates: dict[str, list[str]]
) -> dict[str, list[str]]:
    """Map rule_id → [gate_check_ids] by matching source_ref to gate commands."""
    rule_to_gates: dict[str, list[str]] = {}

    for rule in rules:
        rule_id = rule.get("id", "")
        source_ref = rule.get("source_ref", "")
        if not source_ref:
            continue

        source_script = source_ref.split("::")[0] if "::" in source_ref else source_ref

        matched_gates = []
        for gate_id, scripts in gates.items():
            for script in scripts:
                if source_script in script or script in source_script:
                    matched_gates.append(gate_id)
                    break

        if matched_gates:
            rule_to_gates[rule_id] = sorted(set(matched_gates))

    return rule_to_gates


def _build_inverse(mapping: dict[str, list[str]]) -> dict[str, list[str]]:
    """Invert rule→gates to gates→rules."""
    inverse: dict[str, list[str]] = {}
    for rule_id, gate_ids in mapping.items():
        for gid in gate_ids:
            inverse.setdefault(gid, []).append(rule_id)
    return {k: sorted(v) for k, v in sorted(inverse.items())}


def main() -> int:
    parser = argparse.ArgumentParser(description="GaC Rule↔Gate mapping generator")
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Write to registry file")
    args = parser.parse_args()

    rules = _load_rules()
    gates = _load_gate_ids()
    mapping = _build_mapping(rules, gates)
    inverse = _build_inverse(mapping)

    mapped_count = len(mapping)
    unmapped = [r["id"] for r in rules if r.get("id") and r["id"] not in mapping]
    active_unmapped = [
        r["id"]
        for r in rules
        if r.get("id") not in mapping
        and r.get("lifecycle") == "active"
        and r.get("enforcement") in ("required", "error")
    ]

    result = {
        "rule_to_gates": mapping,
        "gate_to_rules": inverse,
        "stats": {
            "total_rules": len(rules),
            "mapped_rules": mapped_count,
            "unmapped_rules": len(unmapped),
            "active_required_unmapped": len(active_unmapped),
            "total_gates": len(gates),
            "gates_with_rules": len(inverse),
        },
    }

    if args.stats:
        print(f"Rules: {len(rules)} total, {mapped_count} mapped, {len(unmapped)} unmapped")
        print(f"  Active required/error unmapped: {len(active_unmapped)}")
        print(f"Gates: {len(gates)} total, {len(inverse)} with rule mappings")
        if active_unmapped:
            print(f"\nActive required/error unmapped rules:")
            for rid in active_unmapped[:20]:
                print(f"  - {rid}")
        return 0

    if args.json_output:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.apply:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            yaml.dump(result, f, default_flow_style=False, allow_unicode=True)
        print(f"Written to {OUTPUT_PATH}")
        print(f"  Mapped: {mapped_count}/{len(rules)} rules")
        print(f"  Active required unmapped: {len(active_unmapped)}")
        return 0

    print("=== GaC Rule↔Gate Mapping ===")
    print(f"Mapped: {mapped_count}/{len(rules)} rules → {len(inverse)} gates")
    print(f"Active required/error unmapped: {len(active_unmapped)}")
    print("\nUse --apply to write registry, --stats for details, --json for machine output.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
