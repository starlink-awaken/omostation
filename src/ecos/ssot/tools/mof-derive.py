#!/usr/bin/env python3
"""
织星 MOF — 本体推理引擎 (mof-derive)
=====================================
基于 M2 本体映射中的推导规则，对 M1 节点进行本体论推理。
产出: 风险链·缺口发现·影响分析·跨域实体关联

推导类型:
  1. 传递推理 — A→B, B→C ∴ A→C
  2. 风险推理 — 基于推导规则的自动风险评估
  3. 缺口发现 — 检测 M2 类型覆盖不足
  4. 影响分析 — 给定变更，推导波及范围

用法:
    python3 mof-derive.py                    # 全量推理
    python3 mof-derive.py --risks            # 仅风险推理
    python3 mof-derive.py --impact=PROTOCOL-MCP  # 影响分析
    python3 mof-derive.py --json             # JSON 输出
"""

import sys
import json
import yaml
import argparse
from pathlib import Path
from datetime import datetime, timezone

DOCS = Path.home() / "Documents"
NODES_DIR = DOCS / "驾驶舱" / "元模型" / "nodes"
ONTO_FILE = DOCS / "驾驶舱" / "元模型" / "M2-本体映射.yaml"
CONSTRAINTS_FILE = DOCS / "学习进化" / "2-knowledge" / "基建架构" / "L0-constraints.yaml"


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f)


def load_m1_nodes() -> list[dict]:
    nodes = []
    if not NODES_DIR.exists():
        return nodes
    for f in sorted(NODES_DIR.glob("*.yaml")):
        data = load_yaml(f)
        if isinstance(data, dict) and "id" in data:
            nodes.append(data)
    return nodes


def load_ontology() -> dict:
    data = load_yaml(ONTO_FILE)
    return data.get("m2_ontology", data)


def get_m0_protocol_state() -> dict:
    data = load_yaml(CONSTRAINTS_FILE)
    registry = data.get("protocol_registry", [])
    now = datetime.now()
    state = {}
    for p in registry:
        intro = datetime.strptime(p["introduced"], "%Y-%m-%d")
        age = (now - intro).days
        half = p["half_life_days"]
        decay = min(1.0, age / half) if half > 0 else 1.0
        state[p["id"]] = {"decay": decay, "age_days": age}
    return state


def derive_risks(nodes: list[dict], onto: dict) -> list[dict]:
    """基于推导规则进行风险评估"""
    risks = []
    rules = onto.get("derivation_rules", [])
    m0 = get_m0_protocol_state()

    # 按节点类型索引
    by_type = {}
    for n in nodes:
        by_type.setdefault(n.get("type", "?"), []).append(n)

    for rule in rules:
        rid = rule.get("id", "?")
        desc = rule.get("description", "")
        rule_text = rule.get("rule", "")
        priority = rule.get("priority", "medium")

        # DR-01: 协议衰减 → 依赖组件风险
        if "DR-01" in rid:
            protocols = by_type.get("Protocol", [])
            for p in protocols:
                pid = p["id"].replace("PROTOCOL-", "")
                decay = m0.get(pid, {}).get("decay", 0)
                if decay > 0.5:
                    # Find components that use this protocol
                    artifacts = by_type.get("Artifact", [])
                    affected = [a["id"] for a in artifacts if pid.lower() in a.get("name", "").lower() or
                                pid.lower() in a.get("description", "").lower()]
                    if affected:
                        risks.append({"rule": rid, "severity": "medium", "description": desc,
                                     "source": p["id"], "affected": affected,
                                     "detail": f"协议 {pid} 衰减 {decay:.0%}, 影响 {len(affected)} 个组件"})

        # DR-04: 架构演化但模型未更新
        if "DR-04" in rid:
            archs = by_type.get("Architecture", [])
            models = by_type.get("Model", [])
            for arch in archs:
                arch_mtime = arch.get("properties", {}).get("mtime", arch.get("created", ""))
                for model in models:
                    model_mtime = model.get("created", "")
                    if arch_mtime > model_mtime:
                        risks.append({"rule": rid, "severity": "high", "description": desc,
                                     "source": arch["id"], "affected": [model["id"]],
                                     "detail": f"架构 {arch['id']} 更新于 {arch_mtime}, 模型 {model['id']} 创建于 {model_mtime}"})

        # DR-08: M1 节点缺失检测
        if "DR-08" in rid:
            m2_types = ["Model", "Architecture", "Mechanism", "Protocol", "Pattern", "Specification", "Process", "Entity"]
            for mt in m2_types:
                count = len(by_type.get(mt, []))
                if count == 0:
                    risks.append({"rule": rid, "severity": "high", "description": desc,
                                 "source": mt, "affected": [],
                                 "detail": f"M2 类型 '{mt}' 无 M1 实例——模型覆盖缺口"})

    return risks


def derive_gaps(nodes: list[dict], onto: dict) -> list[dict]:
    """发现架构缺口"""
    gaps = []
    by_type = {}
    for n in nodes:
        by_type.setdefault(n.get("type", "?"), []).append(n)

    # 检查所有 M2 类型的 M1 覆盖率
    m2_types = ["Model", "Architecture", "Mechanism", "Protocol", "Pattern", "Specification", "Process", "Entity"]
    for mt in m2_types:
        count = len(by_type.get(mt, []))
        if count < 2:
            gaps.append({"type": mt, "severity": "medium" if count == 1 else "high",
                        "detail": f"仅有 {count} 个 M1 节点 (推荐 ≥2)"})

    # 检查跨层覆盖
    layers = set()
    for n in nodes:
        layer = n.get("layer", "")
        if layer:
            layers.add(layer)
    expected_layers = {"L0", "L1", "L2", "L3", "L4", "I0", "X1", "X2", "X3", "X4"}
    missing_layers = expected_layers - layers
    if missing_layers:
        gaps.append({"type": "Layer", "severity": "medium",
                    "detail": f"无 M1 节点覆盖的层: {missing_layers}"})

    return gaps


def derive_impact(nodes: list[dict], target_id: str) -> dict:
    """推导影响范围"""
    target = None
    for n in nodes:
        if n["id"] == target_id or target_id in n["id"]:
            target = n
            break
    if not target:
        return {"error": f"未找到节点: {target_id}"}

    impact = {"target": target_id, "direct": [], "indirect": [], "chain": []}

    # Direct: 同 layer 或同 domain 的节点
    target_layer = target.get("layer", "")
    target_domain = target.get("domain", "")
    for n in nodes:
        if n["id"] == target_id:
            continue
        if n.get("layer") == target_layer or n.get("domain") == target_domain:
            impact["direct"].append(n["id"])

    # Chain: 依赖链
    deps = target.get("properties", {}).get("depends_on", [])
    if deps:
        impact["chain"] = deps

    return impact


def format_report(risks: list[dict], gaps: list[dict]) -> str:
    now = datetime.now(timezone.utc)
    lines = []
    lines.append("=" * 64)
    lines.append("  织星 MOF — 本体推理报告")
    lines.append("=" * 64)
    lines.append(f"  时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    lines.append(f"  ── 风险推理 ({len(risks)} 项) ──")
    if risks:
        for r in risks:
            icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(r["severity"], "⚪")
            lines.append(f"  {icon} [{r['rule']}] {r['description'][:60]}")
            lines.append(f"     源: {r['source']} | 影响: {r.get('affected',[])}")
            lines.append(f"     {r.get('detail','')}")
    else:
        lines.append("  ✅ 未发现风险")
    lines.append("")

    lines.append(f"  ── 缺口发现 ({len(gaps)} 项) ──")
    if gaps:
        for g in gaps:
            icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(g["severity"], "⚪")
            lines.append(f"  {icon} [{g['type']}] {g['detail']}")
    else:
        lines.append("  ✅ 未发现缺口")

    lines.append(f"\n{'='*64}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--risks", action="store_true")
    parser.add_argument("--gaps", action="store_true")
    parser.add_argument("--impact", type=str)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    nodes = load_m1_nodes()
    onto = load_ontology()
    risks = derive_risks(nodes, onto) if (args.risks or not args.impact) else []
    gaps = derive_gaps(nodes, onto) if (args.gaps or not args.impact) else []

    if args.impact:
        impact = derive_impact(nodes, args.impact)
        if args.json:
            print(json.dumps(impact, ensure_ascii=False, indent=2))
        else:
            print(f"  🎯 影响分析: {args.impact}")
            print(f"  直接影响 ({len(impact.get('direct',[]))}): {impact['direct'][:5]}")
            print(f"  依赖链: {impact.get('chain',[])}")
        return

    if args.json:
        print(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(),
                          "risks": risks, "gaps": gaps}, ensure_ascii=False, indent=2))
    else:
        print(format_report(risks, gaps))


if __name__ == "__main__":
    main()
