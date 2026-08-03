#!/usr/bin/env python3
"""MOF 本体论推理引擎 — 影响分析 + 状态推理 + 价值推理"""

import sys
from pathlib import Path

import yaml

M1_DIR = Path(__file__).parent.parent / "mof" / "m1"
M2_DIR = Path(__file__).parent.parent / "mof" / "m2"


def load_m1(node_id: str) -> dict | None:
    """加载 M1 节点"""
    for yaml_file in M1_DIR.rglob("*.yaml"):
        if yaml_file.name.startswith("_"):
            continue
        try:
            data = yaml.safe_load(yaml_file.read_text())
            if isinstance(data, dict) and data.get("id") == node_id:
                return data
        except Exception:  # defensive fallback
            pass
    return None


def load_m2(schema_type: str) -> dict | None:
    """加载 M2 schema"""
    yaml_file = M2_DIR / f"{schema_type}.yaml"
    if yaml_file.exists():
        try:
            data = yaml.safe_load(yaml_file.read_text())
            if isinstance(data, dict):
                for key in data:
                    if isinstance(data[key], dict) and "stateMachine" in data[key]:
                        return data[key]
        except Exception:  # defensive fallback
            pass
    return None


def find_dependents(node_id: str, project_name: str = None) -> list[dict]:  # type: ignore[reportArgumentType]
    """查找所有依赖指定节点的 M1 节点"""
    dependents = []
    search_terms = [node_id]
    if project_name:
        search_terms.append(project_name)

    for yaml_file in M1_DIR.rglob("*.yaml"):
        if yaml_file.name.startswith("_"):
            continue
        try:
            data = yaml.safe_load(yaml_file.read_text())
            if not isinstance(data, dict):
                continue
            # Check depends_on
            relations = data.get("relations", {})
            depends_on = relations.get("depends_on", [])
            for term in search_terms:
                if term in depends_on:
                    dependents.append(data)
                    break
            # Check subcomponents
            subcomponents = relations.get("subcomponents", [])
            for term in search_terms:
                if term in subcomponents:
                    dependents.append(data)
                    break
        except Exception:  # defensive fallback
            pass
    return dependents


def reason_impact(node_id: str) -> dict:
    """推导变更影响链"""
    node = load_m1(node_id)
    if not node:
        return {"error": f"Node {node_id} not found"}

    project_name = node.get("project", node.get("name", ""))

    impacts = {
        "direct": [],
        "indirect": [],
        "services": [],
        "subcomponents": [],
    }

    # 直接依赖
    relations = node.get("relations", {})
    for dep in relations.get("depends_on", []):
        dep_node = load_m1(dep)
        if dep_node:
            impacts["direct"].append(
                {
                    "id": dep,
                    "name": dep_node.get("name", ""),
                    "layer": dep_node.get("layer", ""),
                }
            )

    # 服务
    for svc in relations.get("provides", []):
        svc_node = load_m1(svc)
        if svc_node:
            impacts["services"].append(
                {
                    "id": svc,
                    "name": svc_node.get("name", ""),
                    "port": svc_node.get("port", ""),
                }
            )

    # 子组件
    for sub in relations.get("subcomponents", []):
        sub_node = load_m1(sub)
        if sub_node:
            impacts["subcomponents"].append(
                {
                    "id": sub,
                    "name": sub_node.get("name", ""),
                }
            )

    # 间接依赖（谁依赖我）
    for dep in find_dependents(node_id, project_name):
        if dep.get("id") != node_id:
            impacts["indirect"].append(
                {
                    "id": dep.get("id", ""),
                    "name": dep.get("name", ""),
                    "type": dep.get("type", ""),
                }
            )

    return impacts


def reason_state(node_id: str, target_state: str = None) -> dict:  # type: ignore[reportArgumentType]
    """推导状态转换是否合法"""
    node = load_m1(node_id)
    if not node:
        return {"error": f"Node {node_id} not found"}

    current_status = node.get("status", "unknown")
    schema = load_m2(node.get("type", ""))

    result = {
        "current_status": current_status,
        "state_history": node.get("state_history", []),
    }

    if schema and "stateMachine" in schema:
        sm = schema["stateMachine"]
        if current_status in sm:
            legal_transitions = sm[current_status].get("transitions", [])
            result["legal_transitions"] = legal_transitions
            result["is_legal"] = (
                target_state in legal_transitions if target_state else None
            )
        else:
            result["legal_transitions"] = []
            result["is_legal"] = False

    return result


def reason_value(node_id: str) -> dict:
    """推导价值指标"""
    node = load_m1(node_id)
    if not node:
        return {"error": f"Node {node_id} not found"}

    return {
        "value_metrics": node.get("value_metrics", {}),
        "cost_model": node.get("cost_model", {}),
        "strategic_importance": node.get("value_metrics", {}).get(
            "strategic_importance", "unknown"
        ),
    }


def main():
    if len(sys.argv) < 3:
        print("Usage: mof-reason.py <command> <node_id> [target_state]")
        print("Commands: impact, state, value")
        sys.exit(1)

    command = sys.argv[1]
    node_id = sys.argv[2]
    target_state = sys.argv[3] if len(sys.argv) > 3 else None

    if command == "impact":
        result = reason_impact(node_id)
        print(f"=== Impact Analysis: {node_id} ===")
        print(f"\nDirect dependencies ({len(result.get('direct', []))}):")
        for d in result.get("direct", []):
            print(f"  → {d['id']} ({d['name']}, {d['layer']})")
        print(f"\nServices provided ({len(result.get('services', []))}):")
        for s in result.get("services", []):
            print(f"  → {s['id']} ({s['name']}, port={s['port']})")
        print(f"\nSubcomponents ({len(result.get('subcomponents', []))}):")
        for s in result.get("subcomponents", []):
            print(f"  → {s['id']} ({s['name']})")
        print(f"\nIndirect dependents ({len(result.get('indirect', []))}):")
        for d in result.get("indirect", []):
            print(f"  → {d['id']} ({d['name']}, {d['type']})")

    elif command == "state":
        result = reason_state(node_id, target_state)  # type: ignore[reportArgumentType]
        print(f"=== State Analysis: {node_id} ===")
        print(f"Current status: {result.get('current_status', 'unknown')}")
        print(f"Legal transitions: {result.get('legal_transitions', [])}")
        if target_state:
            print(f"Is {target_state} legal? {result.get('is_legal', 'unknown')}")

    elif command == "value":
        result = reason_value(node_id)
        print(f"=== Value Analysis: {node_id} ===")
        for k, v in result.get("value_metrics", {}).items():
            print(f"  {k}: {v}")
        for k, v in result.get("cost_model", {}).items():
            print(f"  cost.{k}: {v}")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
