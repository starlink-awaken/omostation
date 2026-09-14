#!/usr/bin/env python3
"""
build_graph.py — T7.1 图谱构建器核心逻辑
从 tools-registry.json + KOS + skills + gaps 构建 graph.json
"""

import fcntl
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

# 将当前目录加入 sys.path, 便于直接执行
_src_dir = Path(__file__).resolve().parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

# Import local helpers after path setup
from forge.graph_utils import compute_capability_overlap, kebab


def build(reg_path: str, graph_path: str, dry_run: bool = False) -> dict:
    reg = json.loads(Path(reg_path).read_text())
    # 加共享锁读
    with Path(reg_path).open("rb") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        reg = json.load(f)
    tools = [t for t in reg["tools"] if t.get("status") != "candidate"]

    nodes = []
    edges = []
    seen_nodes = set()

    def add_node(nid: str, ntype: str, label: str) -> None:
        if nid not in seen_nodes:
            seen_nodes.add(nid)
            nodes.append({"id": nid, "type": ntype, "label": str(label)[:120]})

    def add_edge(src: str, tgt: str, rel: str) -> None:
        edges.append({"source": src, "target": tgt, "relation": rel})

    # --- Tool 节点 ---
    for t in tools:
        add_node(t["id"], "Tool", t.get("name", t["id"]))

    # --- Category 节点 + 边 ---
    cats_seen = set()
    for t in tools:
        for cat in t.get("category", []):
            cid = f"cat:{kebab(cat)}"
            if cid not in cats_seen:
                cats_seen.add(cid)
                add_node(cid, "Category", cat)
            add_edge(t["id"], cid, "IN_CATEGORY")

    # --- Capability 节点 + 边 ---
    caps_seen = {}
    for t in tools:
        for cap in t.get("capabilities", []):
            cap_key = cap[:80].lower()
            if cap_key not in caps_seen:
                cid = f"cap:{kebab(cap[:40])}"
                caps_seen[cap_key] = cid
                add_node(cid, "Capability", cap[:80])
            add_edge(t["id"], caps_seen[cap_key], "HAS_CAPABILITY")

    # --- Provider 节点 + 边 ---
    provs_seen = {}
    for t in tools:
        prov = (t.get("source", {}) or {}).get("provider", "") or ""
        if prov and prov != "auto-detected" and prov != "开源工具":
            pk = prov.lower().strip()
            if pk not in provs_seen:
                pid = f"prov:{kebab(prov[:30])}"
                provs_seen[pk] = pid
                add_node(pid, "Provider", prov)
            add_edge(t["id"], provs_seen[pk], "PROVIDED_BY")

    # --- Skill 节点 + 边 ---
    for t in tools:
        if t.get("type") == "skill":
            sid = t["id"]
            add_node(sid, "Skill", t.get("name", sid))
            add_edge(t["id"], sid, "HAS_SKILL")
            skill_caps = set(c.lower() for c in t.get("capabilities", []))
            for other in tools:
                if other["id"] == t["id"] or other.get("type") == "skill":
                    continue
                other_caps = set(c.lower() for c in other.get("capabilities", []))
                if skill_caps & other_caps:
                    add_edge(sid, other["id"], "COMPLEMENTS")

    # --- Gap 节点 ---
    gaps = reg.get("gap_analysis", {}) or {}
    gaps_list = gaps.get("gaps", []) or []
    for g in gaps_list:
        gname = (g or {}).get("capability", "") or ""
        if gname:
            gid = f"gap:{kebab(gname[:30])}"
            add_node(gid, "Gap", f"缺口: {gname}")
            for cap_key, cap_id in caps_seen.items():
                if gname.lower() in cap_key:
                    add_edge(cap_id, gid, "MATCHES_GAP")

    # --- Tool COMPETES_WITH（能力重叠 ≥0.6） ---
    for id1, id2, _ in compute_capability_overlap(tools, min_similarity=0.6):
        add_edge(id1, id2, "COMPETES_WITH")

    # 统计（单次遍历，不用多个 list comprehension）
    type_counts = Counter(n["type"] for n in nodes)
    stats = {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "tool_nodes": type_counts.get("Tool", 0),
        "capability_nodes": type_counts.get("Capability", 0),
        "skill_nodes": type_counts.get("Skill", 0),
        "gap_nodes": type_counts.get("Gap", 0),
        "provider_nodes": type_counts.get("Provider", 0),
        "category_nodes": type_counts.get("Category", 0),
    }

    graph = {
        "generated": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "nodes": nodes,
        "edges": edges,
        "stats": stats,
    }

    # 输出统计
    parts = []
    for k in ["tool_nodes", "capability_nodes", "skill_nodes", "gap_nodes", "provider_nodes", "category_nodes"]:
        v = stats[k]
        if v > 0:
            parts.append(f"{k.replace('_nodes', '')} {v}")
    print(f"  nodes:   {' + '.join(parts)} = {stats['total_nodes']}")
    print(f"  edges:   {stats['total_edges']}")

    if not dry_run:
        Path(graph_path).parent.mkdir(parents=True, exist_ok=True)
        Path(graph_path).write_text(json.dumps(graph, indent=2, ensure_ascii=False) + "\n")
        print(f"  ✅ 写入 {graph_path}")

        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        reg["event_log"].append(
            {
                "type": "graph:built",
                "summary": f"Knowledge graph built: {stats['total_nodes']} nodes, {stats['total_edges']} edges",
                "timestamp": now,
            }
        )
        Path(reg_path).write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")
    else:
        print("  🔶 --dry-run 模式，未写入文件")

    return graph


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    toolbox = Path(__file__).resolve().parent.parent
    build(
        reg_path=str(toolbox / "tools-registry.json"),
        graph_path=str(toolbox / "graph" / "graph.json"),
        dry_run=dry_run,
    )
