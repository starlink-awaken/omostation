#!/usr/bin/env python3
"""
query_graph — 图谱查询（替代 scripts/query-graph.sh）

用法:
  python3 src/query_graph.py <关键词> [--json] [--topo]
"""

from __future__ import annotations

import json
import sys
from collections import Counter

from forge.forge_config import GRAPH  # type: ignore[import-not-found]


def _load() -> dict:
    return json.loads(GRAPH.read_text()) if GRAPH.exists() else {"nodes": [], "edges": []}


def topo_analysis() -> None:
    g = _load()
    edge_count: Counter = Counter()
    for e in g.get("edges", []):
        edge_count[e["source"]] += 1
        edge_count[e["target"]] += 1
    node_labels = {n["id"]: n["label"] for n in g.get("nodes", [])}
    node_types = {n["id"]: n["type"] for n in g.get("nodes", [])}
    print("=== 拓扑分析: Hub 节点 ===")
    print("关联度最高的节点:")
    for nid, count in edge_count.most_common(15):
        label = node_labels.get(nid, nid)
        ntype = node_types.get(nid, "")
        print(f"  {count:3d} 条边 | {ntype:12s} | {label}")


def query(q: str, json_mode: bool = False) -> None:
    g = _load()
    ql = q.lower()
    matched = [n for n in g.get("nodes", []) if ql in n["label"].lower() or ql in n["id"].lower()]
    if not matched:
        if json_mode:
            print(json.dumps({"query": q, "tools": [], "knowledge": [], "skills": [], "gaps": []}))
        else:
            print("未找到匹配")
        return
    matched_ids = {n["id"] for n in matched}
    related_edges = [e for e in g.get("edges", []) if e["source"] in matched_ids or e["target"] in matched_ids]
    related_ids: set[str] = set()
    for e in related_edges:
        related_ids.add(e["source"])
        related_ids.add(e["target"])
    related_nodes = [n for n in g.get("nodes", []) if n["id"] in related_ids]
    by_type: dict[str, list[dict]] = {}
    for n in related_nodes:
        by_type.setdefault(n["type"], []).append(n)

    if json_mode:
        result: dict[str, object] = {"query": q}
        for t in ["Tool", "Knowledge", "Skill", "Capability", "Gap", "Category", "Provider"]:
            result[t.lower() + "s"] = [{"id": n["id"], "label": n["label"]} for n in by_type.get(t, [])]
        print(json.dumps(result, ensure_ascii=False))
    else:
        labels = {
            "Tool": "工具",
            "Knowledge": "知识",
            "Skill": "技能",
            "Capability": "能力",
            "Gap": "缺口",
            "Category": "分类",
            "Provider": "供应商",
        }
        print(f"\n「{q}」相关\n")
        for t, label in labels.items():
            items = by_type.get(t, [])
            if items:
                print(f"  {label}:")
                for n in items[:10]:
                    print(f"    {n['id']} — {n['label'][:60]}")
                print()
        print(f"  共 {len(related_nodes)} 个关联节点, {len(related_edges)} 条边")


def run(args: list[str]) -> int:
    json_mode = "--json" in args
    topo_mode = "--topo" in args
    q = next((a for a in args if a not in ("--json", "--topo", "--help", "-h")), "")

    if "--help" in args or "-h" in args:
        print("用法: python3 src/query_graph.py <关键词> [--json] [--topo]")
        return 0
    if topo_mode:
        topo_analysis()
        return 0
    if not q:
        print("❌ 请提供查询关键词")
        return 1
    query(q, json_mode)
    return 0


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
