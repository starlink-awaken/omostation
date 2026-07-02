#!/usr/bin/env python3
"""GaC M1 实例同步器 (ADR-0106, 机制 7, Phase 4B).

从 governance-checks.yaml::gac.rules 自动生成/同步 M1 GAC-RULE-*.yaml 实例节点.
M1 节点是 derived (非手工), SSOT 仍在 governance-checks.yaml.

派生链 (NORTH-STAR 不变量 5, stage3-4-design):
  M2 gac_rule.yaml (schema)  ←  mof-schema-validate.py 校验
  M1 GAC-RULE-*.yaml (实例)  ←  本工具从 registry 生成
  SSOT governance-checks.yaml ←  gac-validate/gac-drift 检测

用法:
  python3 bin/gac-m1-sync.py              # diff: 报告 registry vs M1 差异
  python3 bin/gac-m1-sync.py --sync      # 同步: 生成缺失 + 更新过期 + 删除多余
  python3 bin/gac-m1-sync.py --json      # JSON 输出 (cron/仪表盘)
"""

from __future__ import annotations

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
REGISTRY = WORKSPACE / ".omo" / "_truth" / "registry" / "governance-checks.yaml"
M1_DIR = WORKSPACE / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "governance"

# F-5 (ADR-0122 S1 2026-07-02): 治本 — M1 写操作默认 advisory, 需 GAC_M1_SYNC_WRITE=1 显式确认
# 主仓不直接写 submodule 内文件 (违反"主仓不写 submodule" 架构边界).
# 默认 dry-run 仅生成 actions 列表, 真正的 submodule commit 由维护者走 submodule 自己的 PR.
# GAC_M1_SYNC_WRITE=1 显式声明 "我知道这是跨边界写, 我接受" 才执行实际写.
import os
M1_WRITE_ENABLED = os.environ.get("GAC_M1_SYNC_WRITE", "0") == "1"


def load_rules() -> list[dict]:
    """读 gac.rules (SSOT)."""
    import yaml

    if not REGISTRY.exists():
        return []
    docs = [d for d in yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8")) if d]
    if not docs:
        return []
    return docs[-1].get("gac", {}).get("rules", [])


def load_m1_nodes() -> dict[str, dict]:
    """读已有 M1 GAC-RULE-*.yaml 节点 (排除 METAMODEL)."""
    import yaml

    nodes = {}
    if not M1_DIR.exists():
        return nodes
    for f in sorted(M1_DIR.glob("GAC-RULE-*.yaml")):
        if f.name == "GAC-RULE-METAMODEL.yaml":
            continue
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        if data and data.get("type") == "GacRule":
            rid = data.get("properties", {}).get("id") or data.get("id", "")
            nodes[rid] = {"data": data, "path": f}
    return nodes


def rule_to_m1_yaml(rule: dict) -> str:
    """把 GaC registry 规则转为 M1 YAML 文本 (derived, 非手工编辑)."""
    import yaml as yaml_mod

    rid = rule.get("id", "UNKNOWN")
    dimension = rule.get("dimension", "")
    layer = rule.get("layer", "")
    check_type = rule.get("check_type", "")
    executor = rule.get("executor", [])
    lifecycle = rule.get("lifecycle", "active")
    version = rule.get("version", "1.0.0")
    created_at = rule.get("created_at", "")
    target = rule.get("target", "")
    forbid_copy_in = rule.get("forbid_copy_in", [])
    adr = rule.get("adr", "")
    source_type = rule.get("source_type", "native")
    source_ref = rule.get("source_ref", "")
    enforcement = rule.get("enforcement", "")
    name = rule.get("name", rid)
    description = rule.get("description", "")
    relates_to = rule.get("relates_to", [])

    m1 = {
        "id": f"GAC-RULE-{rid}",
        "type": "GacRule",
        "name": name if name != rid else f"GaC 规则 {rid}",
        "description": description or f"GaC 治理规则 {rid} ({dimension}/{layer}/{check_type})",
        "status": "active" if lifecycle == "active" else lifecycle,
        "domain": "meta",
        "layer": layer,
        "created": created_at,
        "version": version,
        "properties": {
            "m3_parent": "GovernanceElement.GacRule",
            "id": rid,
            "dimension": dimension,
            "layer": layer,
            "check_type": check_type,
            "executor": executor,
            "lifecycle": lifecycle,
            "version": version,
            "created_at": created_at,
        },
        "source": ".omo/_truth/registry/governance-checks.yaml",
        "model_driven_refs": {
            "source_file": "projects/ecos/src/ecos/ssot/mof/m2/gac_rule.yaml",
            "m3_type": "GacRule",
            "registry_ssot": ".omo/_truth/registry/governance-checks.yaml::gac.rules",
            "derived_by": "bin/gac-m1-sync.py",
        },
        "state_history": [
            {"state": lifecycle, "timestamp": f"{created_at}T00:00:00Z", "reason": "M1 实例由 gac-m1-sync.py 从 registry 派生"},
        ],
    }

    if target:
        m1["properties"]["target"] = target
    if forbid_copy_in:
        m1["properties"]["forbid_copy_in"] = forbid_copy_in
    if adr:
        m1["properties"]["adr"] = adr
    if source_type:
        m1["properties"]["source_type"] = source_type
    if source_ref:
        m1["properties"]["source_ref"] = source_ref
    if enforcement:
        m1["properties"]["enforcement"] = enforcement
    if relates_to:
        m1["properties"]["relates_to"] = relates_to

    header = (
        "# M1 GacRule instance — DERIVED by gac-m1-sync.py\n"
        "# SSOT: .omo/_truth/registry/governance-checks.yaml::gac.rules\n"
        "# DO NOT edit manually — re-run: python3 bin/gac-m1-sync.py --sync\n"
    )
    return header + yaml_mod.dump(m1, default_flow_style=False, allow_unicode=True, sort_keys=False)


def compute_diff(rules: list[dict], m1_nodes: dict[str, dict]) -> dict:
    """计算 registry vs M1 差异."""
    registry_ids = {r.get("id") for r in rules}
    m1_ids = set(m1_nodes.keys())

    missing_in_m1 = registry_ids - m1_ids
    orphan_in_m1 = m1_ids - registry_ids

    stale = []
    for rule in rules:
        rid = rule.get("id")
        if rid not in m1_nodes:
            continue
        m1_props = m1_nodes[rid]["data"].get("properties", {})
        for field in ["dimension", "layer", "check_type", "executor", "lifecycle", "version"]:
            reg_val = rule.get(field)
            m1_val = m1_props.get(field)
            if reg_val != m1_val:
                stale.append({"id": rid, "field": field, "registry": reg_val, "m1": m1_val})

    return {
        "missing_in_m1": sorted(missing_in_m1),
        "orphan_in_m1": sorted(orphan_in_m1),
        "stale": stale,
    }


def do_sync(rules: list[dict], m1_nodes: dict[str, dict], diff: dict) -> dict:
    """执行同步: 生成缺失 + 更新过期 + 删除多余.

    F-5 (ADR-0122 S1 2026-07-02): 默认 dry-run (advisory), 不实际写 submodule 内文件.
    需 GAC_M1_SYNC_WRITE=1 环境变量才执行实际写.
    治根"主仓不写 submodule" 架构边界: 默认 advisory 防止误写, 真写需显式声明.
    """
    actions = {"created": [], "updated": [], "deleted": []}

    if not M1_WRITE_ENABLED:
        # dry-run 模式: 模拟 actions 列表, 不写文件
        for rule in rules:
            rid = rule.get("id")
            if rid in diff["missing_in_m1"]:
                actions["created"].append(rid)
        for rule in rules:
            rid = rule.get("id")
            if rid in m1_nodes and rid not in diff["missing_in_m1"]:
                stale_fields = {s["field"] for s in diff["stale"] if s["id"] == rid}
                if stale_fields:
                    actions["updated"].append(rid)
        for rid in diff["orphan_in_m1"]:
            actions["deleted"].append(rid)
        return actions

    # 实际写模式 (GAC_M1_SYNC_WRITE=1)
    for rule in rules:
        rid = rule.get("id")
        if rid in diff["missing_in_m1"]:
            content = rule_to_m1_yaml(rule)
            fpath = M1_DIR / f"GAC-RULE-{rid}.yaml"
            # audit-exempt: non-atomic-write — M1 同步走 advisory 默认, 真写需 GAC_M1_SYNC_WRITE=1 显式声明
            fpath.write_text(content, encoding="utf-8")
            actions["created"].append(rid)

    for rule in rules:
        rid = rule.get("id")
        if rid in m1_nodes and rid not in diff["missing_in_m1"]:
            stale_fields = {s["field"] for s in diff["stale"] if s["id"] == rid}
            if stale_fields:
                content = rule_to_m1_yaml(rule)
                fpath = M1_DIR / f"GAC-RULE-{rid}.yaml"
                # audit-exempt: non-atomic-write — M1 同步走 advisory 默认, 真写需 GAC_M1_SYNC_WRITE=1 显式声明
                fpath.write_text(content, encoding="utf-8")
                actions["updated"].append(rid)

    for rid in diff["orphan_in_m1"]:
        fpath = M1_DIR / f"GAC-RULE-{rid}.yaml"
        if fpath.exists():
            fpath.unlink()
        actions["deleted"].append(rid)

    return actions


def main() -> int:
    args = sys.argv[1:]
    sync_mode = "--sync" in args
    json_mode = "--json" in args

    if not REGISTRY.exists():
        print(f"❌ 注册表不存在: {REGISTRY}")
        return 1

    rules = load_rules()
    m1_nodes = load_m1_nodes()
    diff = compute_diff(rules, m1_nodes)

    if json_mode:
        import json

        result = {
            "registry_rules": len(rules),
            "m1_instances": len(m1_nodes),
            "diff": diff,
        }
        if sync_mode:
            result["actions"] = do_sync(rules, m1_nodes, diff)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print("=== GaC M1 实例同步器 (gac-m1-sync.py) ===")
    print(f"Registry 规则数: {len(rules)}")
    print(f"M1 实例数: {len(m1_nodes)}")

    total_drift = (
        len(diff["missing_in_m1"]) + len(diff["orphan_in_m1"]) + len(diff["stale"])
    )

    if diff["missing_in_m1"]:
        print(f"\n  缺失 (registry 有, M1 无): {len(diff['missing_in_m1'])}")
        for rid in diff["missing_in_m1"][:10]:
            print(f"    - {rid}")
        if len(diff["missing_in_m1"]) > 10:
            print(f"    ... ({len(diff['missing_in_m1']) - 10} more)")

    if diff["orphan_in_m1"]:
        print(f"\n  多余 (M1 有, registry 无): {len(diff['orphan_in_m1'])}")
        for rid in diff["orphan_in_m1"]:
            print(f"    - {rid}")

    if diff["stale"]:
        print(f"\n  过期 (字段不一致): {len(diff['stale'])}")
        for s in diff["stale"][:10]:
            print(f"    - {s['id']}.{s['field']}: registry={s['registry']} m1={s['m1']}")

    if total_drift == 0:
        print("\n✅ M1 实例与 registry 完全同步 (0 drift)")

    if sync_mode:
        actions = do_sync(rules, m1_nodes, diff)
        print("\n同步完成:")
        print(f"  创建: {len(actions['created'])}")
        print(f"  更新: {len(actions['updated'])}")
        print(f"  删除: {len(actions['deleted'])}")
        m1_nodes_after = load_m1_nodes()
        print(f"  M1 实例数: {len(m1_nodes_after)}")

    return 1 if total_drift else 0


if __name__ == "__main__":
    sys.exit(main())
