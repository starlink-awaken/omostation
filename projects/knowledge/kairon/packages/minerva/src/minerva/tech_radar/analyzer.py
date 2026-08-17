"""Tech Radar 相关性分析 — 基于关键词匹配评分 omostation 升级候选度。"""

from __future__ import annotations

from minerva.tech_radar.fetcher import TechItem

# omostation 架构关键词（I0-L4 各层）
_KEYWORDS: dict[str, float] = {
    # L3 Agent 层
    "agent": 0.9,
    "multi-agent": 1.0,
    "multiagent": 1.0,
    "agentic": 0.9,
    "mcp": 1.0,
    "tool-use": 0.9,
    "tool use": 0.9,
    "function calling": 0.8,
    "orchestration": 0.8,
    "orchestrator": 0.8,
    # L1 知识工程
    "knowledge graph": 0.9,
    "knowledge base": 0.8,
    "ontology": 0.9,
    "rag": 0.9,
    "retrieval-augmented": 0.9,
    "retrieval augmented": 0.9,
    "embedding": 0.7,
    "vector": 0.7,
    "semantic search": 0.8,
    # LLM 推理
    "reasoning": 0.8,
    "chain-of-thought": 0.8,
    "cot": 0.7,
    "planning": 0.8,
    "reflection": 0.7,
    "self-correction": 0.8,
    "llm": 0.7,
    "language model": 0.7,
    "transformer": 0.6,
    # 基础设施
    "workflow": 0.7,
    "pipeline": 0.7,
    "scheduler": 0.6,
    "async": 0.5,
    "fastapi": 0.6,
    "python": 0.4,
    # 新兴热点
    "model context protocol": 1.0,
    "context protocol": 0.9,
    "tool registry": 0.9,
    "tool discovery": 0.9,
    "memory": 0.7,
    "long-term memory": 0.8,
    "autonomous": 0.7,
    "ai assistant": 0.6,
    # 架构模式
    "monorepo": 0.5,
    "microservice": 0.5,
    "service mesh": 0.7,
    "circuit breaker": 0.6,
    "gateway": 0.6,
}

# 完全不相关的过滤词（命中则降分）
_NOISE_WORDS = {"finance", "medical imaging", "drug discovery", "climate", "weather", "sports"}


def score_item(item: TechItem) -> float:
    """对单条技术情报计算 omostation 相关度 [0.0, 1.0]。"""
    text = (item.title + " " + item.description + " " + " ".join(item.tags)).lower()

    score = 0.0
    matched: set[str] = set()

    for kw, weight in _KEYWORDS.items():
        if kw in text and kw not in matched:
            score += weight
            matched.add(kw)

    # 噪音惩罚
    for noise in _NOISE_WORDS:
        if noise in text:
            score *= 0.5

    # 归一化到 [0, 1]，上限 = 5 分
    return min(round(score / 5.0, 3), 1.0)


def analyze_items(items: list[TechItem], threshold: float = 0.15) -> list[TechItem]:
    """批量评分，过滤低相关度条目，标记升级候选。

    Returns: 按 relevance_score 降序排列的过滤后条目。
    """
    scored: list[TechItem] = []
    for item in items:
        item.relevance_score = score_item(item)
        if item.relevance_score >= threshold:
            item.upgrade_candidate = item.relevance_score >= 0.4
            scored.append(item)

    scored.sort(key=lambda x: x.relevance_score, reverse=True)
    return scored
