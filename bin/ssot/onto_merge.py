#!/usr/bin/env python3
"""onto_merge.py — ontology 缺口审阅并入（生成 M3 正确归类）

依据 .omo/_knowledge/patterns/doc-l0-mof-mapping-governance.md Wave 2:
把 OntoEKG bootstrap 检出的缺口概念按 M3 四大元素正确归类，
生成可审阅的 generalizations 条目，审阅后并入 m2_ontology。

用法:
    python3 bin/ssot/onto_merge.py --preview   # 生成归类建议（不写入）
    python3 bin/ssot/onto_merge.py --apply     # 并入 ontology.yaml
"""

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY = ROOT / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "ontology.yaml"

# 缺口概念 → (M3 父类型, 说明)
# M3 四大元素: DescriptiveElement / BehavioralElement / GovernanceElement / StructuralElement
GAP_MERGES = {
    "adr": ("DescriptiveElement", "架构决策记录（ADRs 作为描述性知识资产）"),
    "agent-workflow": ("BehavioralElement", "Agent 工作流（可执行治理流程）"),
    "frontmatter": ("DescriptiveElement", "文档前置元数据（描述性标注）"),
    "governance-check": ("GovernanceElement", "治理检查（GaC 规则执行）"),
    "submodule-pointer": ("StructuralElement", "子模块指针（结构引用）"),
    "mcp-tool": ("BehavioralElement", "MCP 工具（可调用能力）"),
    "layer-contract": ("GovernanceElement", "分层契约（跨层约束声明）"),
    "bos-uri": ("BehavioralElement", "BOS URI 路由（协议路由）"),
    "runtime-projection": ("StructuralElement", "运行时投影（状态快照）"),
    "debt-item": ("GovernanceElement", "治理债务条目（待偿项）"),
    "approval-flow": ("BehavioralElement", "审批流程（决策流水线）"),
}


def existing_children(ontology: dict) -> set[str]:
    """ontology 现有 generalizations 的 child 集合。"""
    g = ontology.get("m2_ontology", {}).get("generalizations", [])
    children = set()
    for item in g:
        if isinstance(item, dict) and item.get("child"):
            children.add(str(item["child"]))
    return children


def build_merges(existing: set[str]) -> list[dict]:
    """缺口概念 → 归类条目（跳过已存在）。"""
    merges = []
    for name, (parent, note) in GAP_MERGES.items():
        if name not in existing:
            merges.append({"child": name, "parent": parent, "note": note})
    return merges


def preview(merges: list[dict]) -> str:
    lines = ["# Ontology 缺口并入建议（M3 归类）", ""]
    for m in merges:
        lines.append(f"- {m['child']} → {m['parent']} — {m['note']}")
    lines.append("")
    lines.append(f"共 {len(merges)} 条待并入（跳过已存在）")
    return "\n".join(lines)


def apply_merges(ontology: dict, merges: list[dict]) -> dict:
    """并入 generalizations（追加）。"""
    mo = ontology.setdefault("m2_ontology", {})
    g = mo.setdefault("generalizations", [])
    g.extend(merges)
    mo["generalizations"] = g
    return ontology


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--preview", action="store_true", help="只打印归类建议")
    ap.add_argument("--apply", action="store_true", help="并入 ontology.yaml")
    args = ap.parse_args()
    ontology = yaml.safe_load(ONTOLOGY.read_text(encoding="utf-8"))
    merges = build_merges(existing_children(ontology))
    if not merges:
        print("[OK] 无缺口待并入（全部已存在）")
        return 0
    if args.preview or not args.apply:
        print(preview(merges))
        return 0
    merged = apply_merges(ontology, merges)
    ONTOLOGY.write_text(
        yaml.safe_dump(merged, allow_unicode=True, sort_keys=False))
    print(f"[OK] 并入 {len(merges)} 条 generalizations → {ONTOLOGY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
