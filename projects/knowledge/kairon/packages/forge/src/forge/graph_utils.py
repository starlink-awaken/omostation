#!/usr/bin/env python3
"""
graph_utils.py — 图谱共享工具函数
供 build_graph.py 和 entropy-converge.sh 等共用
"""

import json
import re
from collections import Counter
from pathlib import Path
from typing import cast


def kebab(s: str) -> str:
    """Convert string to kebab-case ID."""
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def compute_capability_overlap(
    tools: list[dict],
    min_similarity: float = 0.6,
    pre_filter: bool = True,
) -> list[tuple[str, str, float]]:
    """
    计算工具间的 capabilities Jaccard 相似度。

    Args:
        tools: 工具列表（每个须有 id 和 capabilities 字段）
        min_similarity: 阈值（默认 0.6），低于此的不返回
        pre_filter: 是否用 id token 预过滤（性能优化）

    Returns:
        [(id1, id2, similarity), ...] 已去重，按相似度降序
    """
    if len(tools) < 2:
        return []

    # 预建 token 集用于过滤
    name_tokens = {t["id"]: set(t["id"].lower().split("-")) for t in tools}

    pairs = []
    for i, t1 in enumerate(tools):
        for j, t2 in enumerate(tools):
            if i >= j:
                continue
            if pre_filter and not (name_tokens[t1["id"]] & name_tokens[t2["id"]]):
                continue

            caps1 = set(c.lower() for c in t1.get("capabilities", []))
            caps2 = set(c.lower() for c in t2.get("capabilities", []))
            if not caps1 or not caps2:
                continue

            overlap = len(caps1 & caps2)
            total = len(caps1 | caps2)
            if total > 0:
                sim = overlap / total
                if sim >= min_similarity:
                    pairs.append((t1["id"], t2["id"], sim))

    # 按相似度降序
    pairs.sort(key=lambda x: -x[2])
    return pairs


def get_edge_degree(g: dict) -> Counter:
    """计算图节点关联度"""
    counts: Counter = Counter()
    for e in g["edges"]:
        counts[e["source"]] += 1
        counts[e["target"]] += 1
    return counts


def get_related_by_type(
    g: dict,
    node_ids: set[str],
    group_types: list[str] | None = None,
) -> dict[str, list[dict]]:
    """
    获取与给定节点集关联的节点，按类型分组。

    Args:
        g: 图数据（含 nodes, edges）
        node_ids: 起点节点 ID 集合
        group_types: 只返回这些类型的节点（None 表示全返回）

    Returns:
        {type: [nodes]}
    """
    related_ids = set()
    for e in g["edges"]:
        if e["source"] in node_ids:
            related_ids.add(e["target"])
        if e["target"] in node_ids:
            related_ids.add(e["source"])

    by_type: dict[str, list[dict]] = {}
    for n in g["nodes"]:
        if n["id"] in related_ids:
            t = n["type"]
            if group_types is None or t in group_types:
                by_type.setdefault(t, []).append(n)
    return by_type


def load_registry(path: str | Path) -> dict:
    """加载 tools-registry.json"""
    return cast("dict", json.loads(Path(path).read_text()))


def load_graph(path: str | Path) -> dict:
    """加载 graph.json"""
    return cast("dict", json.loads(Path(path).read_text()))
