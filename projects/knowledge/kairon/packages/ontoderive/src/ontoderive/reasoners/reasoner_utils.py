"""Reasoner utility functions — self-free helpers extracted from RuleReasoner"""

import re
from typing import Any


def default_rules() -> list[Any]:
    """内置推导规则库 — 可扩展"""
    from ontoderive.reasoners.reasoner import DerivationRule

    return [
        DerivationRule(
            name="numeric_comparison",
            premises=["D-F\\d+.*?(\\d+\\.?\\d*).*?(\\d+\\.?\\d*)"],
            conclusion_template="数值比较: {label1}={val1} vs {label2}={val2}",
            confidence=0.95,
            category="deduction",
        ),
        DerivationRule(
            name="shared_premise_alert",
            premises=[],
            conclusion_template="INF-{a}和INF-{b}共享{n}个前提事实，可能互补或矛盾",
            confidence=0.75,
            category="induction",
        ),
        DerivationRule(
            name="missing_reference",
            premises=[],
            conclusion_template="推论 {inf} 引用了不存在的事实 {fid}",
            confidence=0.99,
            category="deduction",
        ),
        DerivationRule(
            name="evidence_gap",
            premises=[],
            conclusion_template="推论 {inf} 基于{n}个前提，建议增加引用以增强可信度",
            confidence=0.80,
            category="induction",
        ),
        DerivationRule(
            name="threshold_alert",
            premises=[],
            conclusion_template="{metric}达到{value}，超过基准{threshold}",
            confidence=0.90,
            category="deduction",
        ),
    ]


def find_chain(node: Any, inferences: Any, visited: Any) -> Any:
    """递归追踪推导链 — 从当前节点到最深的依赖节点"""
    if node in visited or node not in inferences:
        return [node]
    visited.add(node)
    longest = [node]
    for parent in inferences[node].get("derives_from", []):
        if parent.startswith("INF"):
            parent_chain = find_chain(parent, inferences, visited.copy())
            if len(parent_chain) + 1 > len(longest):
                longest = [node] + parent_chain
    return longest


def calc_depth(node: Any, inferences: Any, depths: Any, visited: Any) -> Any:
    """递归计算推导深度 — 支持循环检测"""
    if node in visited or node not in inferences:
        depths[node] = 0
        return 0
    visited.add(node)
    max_parent = 0
    for parent in inferences[node].get("derives_from", []):
        if parent.startswith("INF"):
            max_parent = max(max_parent, calc_depth(parent, inferences, depths, visited))
    depths[node] = max_parent + 1
    return depths[node]


def project_profile(project: Any) -> list[Any]:
    """提取项目特征向量: [事实数/20, 推偶数/10, 平均引用数/5, 数值事实比, 政策事实比]"""
    facts = project.get("facts", {})
    infs = project.get("inferences", {})

    n_f = len(facts)
    n_i = len(infs)
    avg_df = sum(len(i.get("derives_from", [])) for i in infs.values()) / max(n_i, 1)
    num_ratio = sum(1 for f in facts.values() for v in [str(f.get("value", ""))] if re.search(r"\d", v)) / max(n_f, 1)
    pol_ratio = sum(1 for f in facts.values() if "政策" in str(f.get("desc", ""))) / max(n_f, 1)
    return [n_f / 20, n_i / 10, avg_df / 5, num_ratio, pol_ratio]


def cosine_similarity(a: Any, b: Any) -> Any:
    """两个向量的余弦相似度"""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = (sum(x * x for x in a) or 1) ** 0.5
    norm_b = (sum(x * x for x in b) or 1) ** 0.5
    return dot / (norm_a * norm_b)
