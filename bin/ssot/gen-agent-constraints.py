#!/usr/bin/env python3
"""Gen Agent Constraints — 模型驱动: 从Agent本体yaml自动生成约束制品 (ADR-0403 P1).

读 .omo/_truth/registry/agents/*.yaml → 产出:
  - constraint-gate规则 (每个agent的governance_bindings)
  - permission-matrix条目 (每个agent的action_tier)
  - Agent Card (A2A发现用, JSON-LD格式)
  - PR审查维度 (从constraints推导)
  - 本体一致性验证 (SHACL-like)

Usage:
  python3 bin/ssot/gen-agent-constraints.py              # 生成全部
  python3 bin/ssot/gen-agent-constraints.py --validate    # 只验证一致性
  python3 bin/ssot/gen-agent-constraints.py --json        # JSON输出
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _shared import ROOT, load_yaml

AGENTS_DIR = ROOT / ".omo/_truth/registry/agents"


def load_all_agents() -> list[dict]:
    """Load all agent ontology files."""
    agents = []
    for path in sorted(AGENTS_DIR.glob("*.yaml")):
        data = load_yaml(path)
        if data.get("schema") == "digital_agent/v2":
            data["_path"] = str(path.relative_to(ROOT))
            agents.append(data)
    return agents


def gen_constraint_gate_rules(agents: list[dict]) -> list[dict]:
    """Extract governance bindings → constraint-gate rules."""
    rules = []
    for agent in agents:
        aid = agent.get("id", "?")
        constraints = agent.get("constraints", {})
        for binding in constraints.get("governance_bindings", []):
            rules.append({
                "agent_id": aid,
                "check_id": binding.get("check_id", ""),
                "enforcement": binding.get("enforcement", "advisory"),
                "violation_action": binding.get("violation_action", "warn"),
            })
    return rules


def gen_permission_entries(agents: list[dict]) -> list[dict]:
    """Extract action_tier → permission-matrix entries."""
    entries = []
    for agent in agents:
        constraints = agent.get("constraints", {})
        tier = constraints.get("action_tier", "graylist")
        entries.append({
            "agent_id": agent.get("id"),
            "action_tier": tier,
            "capabilities": agent.get("identity", {}).get("capabilities", []),
        })
    return entries


def gen_agent_cards(agents: list[dict]) -> list[dict]:
    """Generate A2A Agent Cards (JSON-LD format for agent discovery)."""
    cards = []
    for agent in agents:
        identity = agent.get("identity", {})
        cards.append({
            "@type": "AgentCard",
            "id": agent.get("id"),
            "name": agent.get("display_name", agent.get("id")),
            "description": agent.get("description", ""),
            "role": identity.get("role"),
            "capabilities": identity.get("capabilities", []),
            "knowledge_sources": agent.get("knowledge_sources", []),
            "supervised_by": agent.get("constraints", {}).get("relationships", {}).get("supervised_by", []),
            "bos_uri": f"bos://agent/{agent.get('id')}",
        })
    return cards


def gen_review_dimensions(agents: list[dict]) -> list[str]:
    """Derive PR review dimensions from agent capabilities."""
    dims = set()
    for agent in agents:
        role = agent.get("identity", {}).get("role", "")
        if role == "governor":
            dims.update(["policy", "risk"])
        elif role == "advisor":
            dims.update(["mental_model"])
        elif role == "curator":
            dims.update(["function"])
    dims.update(["security", "architecture"])  # always present
    return sorted(dims)


def validate_ontology(agents: list[dict]) -> list[str]:
    """SHACL-like validation: check ontology consistency."""
    issues = []
    agent_ids = {a.get("id") for a in agents}

    for agent in agents:
        aid = agent.get("id", "?")

        # Required fields
        if not agent.get("identity", {}).get("role"):
            issues.append(f"{aid}: missing identity.role")
        if not agent.get("identity", {}).get("capabilities"):
            issues.append(f"{aid}: missing identity.capabilities")
        if not agent.get("runtime", {}).get("executor_class"):
            issues.append(f"{aid}: missing runtime.executor_class")

        # Relationship integrity
        rels = agent.get("constraints", {}).get("relationships", {})
        for supervisor in rels.get("supervised_by", []):
            if supervisor not in agent_ids:
                issues.append(f"{aid}: supervised_by '{supervisor}' not found in registry")

        # Constraint consistency
        tier = agent.get("constraints", {}).get("action_tier")
        if tier not in ("whitelist", "graylist", "blacklist"):
            issues.append(f"{aid}: invalid action_tier '{tier}'")

    # Governor must exist (top-level supervisor)
    if "governor" not in agent_ids:
        issues.append("CRITICAL: no governor agent in registry")

    return issues


def generate_all() -> dict:
    """Generate all constraint artifacts from agent ontologies."""
    agents = load_all_agents()
    if not agents:
        return {"status": "noop", "reason": "no agent ontologies found"}

    return {
        "schema": "agent-constraints/v1",
        "agents_loaded": len(agents),
        "agent_ids": [a["id"] for a in agents],
        "constraint_gate_rules": gen_constraint_gate_rules(agents),
        "permission_entries": gen_permission_entries(agents),
        "agent_cards": gen_agent_cards(agents),
        "review_dimensions": gen_review_dimensions(agents),
        "validation_issues": validate_ontology(agents),
        "validation_passed": len(validate_ontology(agents)) == 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    result = generate_all()

    if args.validate:
        issues = result["validation_issues"]
        if issues:
            print(f"❌ {len(issues)} validation issues:")
            for issue in issues:
                print(f"  - {issue}")
            return 1
        print(f"✅ All {result['agents_loaded']} agents validated successfully.")
        return 0

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Agent Constraints: {result['agents_loaded']} agents loaded")
        print(f"  IDs: {result['agent_ids']}")
        print(f"  gate_rules: {len(result['constraint_gate_rules'])}")
        print(f"  permission_entries: {len(result['permission_entries'])}")
        print(f"  agent_cards: {len(result['agent_cards'])}")
        print(f"  review_dimensions: {result['review_dimensions']}")
        print(f"  validation: {'✅ passed' if result['validation_passed'] else '❌ ' + str(len(result['validation_issues'])) + ' issues'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
