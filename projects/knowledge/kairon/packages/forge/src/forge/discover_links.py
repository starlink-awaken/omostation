"""
discover_links.py — T8.2 自动关联发现

发现图谱中隐含的关系（去重 + 限制输出）

用法:
    python3 src/discover_links.py [--help]
"""

from __future__ import annotations

import json
import sys
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from forge.forge_config import GRAPH, REGISTRY  # type: ignore[import-not-found]


def _load_graph() -> dict:
    return cast("dict", json.loads(GRAPH.read_text()))


def _load_registry() -> dict:
    return cast("dict", json.loads(REGISTRY.read_text()))


def _save_registry(reg: dict) -> None:
    """原子写入注册表——写入临时文件后重命名回目标路径。"""
    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        prefix="registry_",
        dir=str(REGISTRY.parent),
        delete=False,
    )
    try:
        tmp.write(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")
        tmp.close()
        Path(tmp.name).replace(REGISTRY)
    except Exception:
        Path(tmp.name).unlink(missing_ok=True)
        raise


def _show_help() -> None:
    print("用法: python3 src/discover_links.py [--help]")
    print()
    print("自动发现图谱中隐含的关系：")
    print("  1. 同分类未关联的工具")
    print("  2. 缺口可填补")
    print("  3. 供应商生态未标注")
    print("  4. 使用模式组合")
    print()
    print("--help  显示此帮助")


def discover() -> int:
    if not GRAPH.exists():
        print("❌ graph.json 不存在，先运行 build-graph.sh")
        return 1

    g = _load_graph()
    reg = _load_registry()

    discoveries: list[dict[str, str]] = []
    seen_pairs: set[tuple[str, ...]] = set()
    seen_descs: set[str] = set()

    def add_disc(cat: str, desc: str, pair_key: tuple[str, ...] | None = None) -> None:
        if pair_key:
            pk = tuple(sorted(pair_key))
            if pk in seen_pairs:
                return
            seen_pairs.add(pk)
        if desc in seen_descs:
            return
        seen_descs.add(desc)
        discoveries.append({"category": cat, "description": desc})

    node_by_id = {n["id"]: n for n in g["nodes"]}

    # 预建边索引：type → source → [targets]
    edges_by_rel: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for e in g["edges"]:
        edges_by_rel[e["relation"]][e["source"]].append(e["target"])

    # 预建邻接集
    edge_set: dict[str, set[str]] = defaultdict(set)
    for e in g["edges"]:
        edge_set[e["source"]].add(e["target"])
        edge_set[e["target"]].add(e["source"])

    # 1. 同分类未关联 — 单次遍历边构建
    cat_tools: dict[str, list[str]] = defaultdict(list)
    for src, targets in edges_by_rel.get("IN_CATEGORY", {}).items():
        for t in targets:
            cat_tools[t].append(src)

    unlinked_count = 0
    for cat_id, tools in cat_tools.items():
        if len(tools) < 2:
            continue
        cat_label = node_by_id[cat_id]["label"]
        for i, t1 in enumerate(tools):
            for t2 in tools[i + 1 :]:
                if unlinked_count >= 6:
                    break
                if t2 not in edge_set.get(t1, set()):
                    t1_label = node_by_id[t1]["label"]
                    t2_label = node_by_id[t2]["label"]
                    add_disc("同分类未关联", f"{t1_label} ↔ {t2_label} — 同属「{cat_label}」分类, 建议关联")
                    unlinked_count += 1
            if unlinked_count >= 6:
                break

    # 2. 缺口可填补（用预建索引替代嵌套边循环）
    cap_to_tools: dict[str, list[str]] = defaultdict(list)
    for src, caps in edges_by_rel.get("HAS_CAPABILITY", {}).items():
        for cap_id in caps:
            cap_to_tools[cap_id].append(src)

    gap_nodes = [n for n in g["nodes"] if n["type"] == "Gap"]
    for gn in gap_nodes:
        gap_label = gn["label"]
        for cap_id in edges_by_rel.get("MATCHES_GAP", {}).get(gn["id"], []):
            cap_label = node_by_id.get(cap_id, {}).get("label", "")
            for tool_src in cap_to_tools.get(cap_id, []):
                tool_label = node_by_id.get(tool_src, {}).get("label", tool_src)
                add_disc(
                    "缺口可填补",
                    f"{tool_label} 可弥补 {gap_label} (通过能力: {cap_label})",
                    pair_key=(gap_label, tool_label),
                )

    # 3. 供应商生态 — 单次遍历
    prov_tools: dict[str, list[str]] = defaultdict(list)
    for src, provs in edges_by_rel.get("PROVIDED_BY", {}).items():
        for prov_id in provs:
            prov_tools[prov_id].append(src)

    for prov_id, tools in prov_tools.items():
        if len(tools) >= 3:
            prov_label = node_by_id[prov_id]["label"]
            tool_labels = "、".join([node_by_id[t]["label"] for t in tools[:5]])
            add_disc("供应商生态", f"{prov_label} 生态: {tool_labels} — 建议统一管理")

    # 4. 使用模式
    tools_with_usage = [
        (t, t.get("telemetry", {}).get("use_count", 0))
        for t in reg["tools"]
        if t.get("telemetry", {}).get("use_count", 0) > 0
    ]
    if tools_with_usage:
        tools_with_usage.sort(key=lambda x: -x[1])
        top_ids = [t["id"] for t, _ in tools_with_usage[:3]]
        top_names = [t["name"] for t, _ in tools_with_usage[:3]]
        add_disc("使用模式", f"高频: {', '.join(top_names)} — 建议生成沉淀 skill", pair_key=tuple(top_ids))

    print()
    print("关联发现")
    print()
    if not discoveries:
        print("  ✅ 无新关联发现")
    else:
        print(f"  共 {len(discoveries)} 条潜在关联:")
        for i, d in enumerate(discoveries, 1):
            print()
            print(f"  {i}. [{d['category']}]")
            print(f"     {d['description']}")

    if discoveries:
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        reg.setdefault("event_log", []).append(
            {
                "type": "graph:links_discovered",
                "tool_ids": [],
                "summary": f"Auto-discovered {len(discoveries)} implicit relationships",
                "timestamp": now,
            }
        )
        _save_registry(reg)
        print()
        print("  ✅ 已写入 event_log")

    return 0


def run(args: list[str]) -> int:
    if args and args[0] in ("--help", "-h"):
        _show_help()
        return 0
    return discover()


def main() -> None:
    sys.exit(run(sys.argv[1:]))


if __name__ == "__main__":
    main()
