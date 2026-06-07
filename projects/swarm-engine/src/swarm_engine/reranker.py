from __future__ import annotations

# ruff: noqa: RUF002, RUF003

"""
---
domain: D-Execution
layer: organ
status: active
Version: 1.0.0
Summary: "Semantic Reranker for context optimization and token reduction."
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Reranker ≡ Module
# 内涵 ≝ {Reranker}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Reranker)}
# 功能 ⊢ {Init_Reranker, Execute_Reranker, Validate_Reranker}
# =============================================================================

import logging
from typing import Any

try:
    from nucleus.Z_Microkernel.infrastructure.oracle.inference_oracle import (  # type: ignore[import-not-found]
        InferenceOracle,
    )
except ModuleNotFoundError:
    InferenceOracle = None  # type: ignore[assignment,misc]

_log = logging.getLogger(__name__)


class SemanticReranker:
    """
    [RFC-029] Semantic Reranker: 语义重排序引擎。
    通过动态策略（本地 vs 云端）压缩 LLM 上下文窗口。
    """

    def __init__(self) -> None:
        self.status = "active"
        self._oracle = InferenceOracle.get_instance() if InferenceOracle else None

    async def rerank(
        self, query: str, candidates: list[dict[str, Any]], eu_budget: float = 1.0
    ) -> list[dict[str, Any]]:
        """
        根据预算选择重排序策略。
        """
        if not candidates:
            return []

        # 策略阈值：超过 10 EU 则视为高价值任务，启用 LLM Reranker
        if eu_budget > 10.0:
            _log.info(f"🧠 [Reranker] High-value task (budget={eu_budget}). Using LLM-based reranking.")
            return await self._rerank_with_llm(query, candidates)
        else:
            _log.debug(f"⚡ [Reranker] Standard task (budget={eu_budget}). Using local vector-based reranking.")
            return self._rerank_with_vector(query, candidates)

    def _rerank_with_vector(self, query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        使用本地启发式算法进行重排序。 (RFC-031 Aligned)
        算法：Score = (KeywordOverlap * 0.7) + (Importance * 0.3)
        """
        query_words = set(query.lower().split())
        scored_candidates = []

        for fact in candidates:
            # 提取事实文本
            fact_text = f"{fact['sub']} {fact['pred']} {fact['obj']}".lower()
            fact_words = set(fact_text.split())

            # 计算关键词重叠度 (Jaccard-like)
            intersection = query_words.intersection(fact_words)
            overlap_score = len(intersection) / len(query_words) if query_words else 0.0

            # 综合评分
            importance = fact.get("importance", 0.5)
            final_score = (overlap_score * 0.7) + (importance * 0.3)

            scored_candidates.append((final_score, fact))

        # 降序排列并取 Top 10
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_candidates[:10]]

    async def _rerank_with_llm(self, query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        调用大模型对上下文进行精细重排序。
        """
        # 构造 Ranking Prompt
        prompt = f"Given the query: '{query}', rate the relevance of each of the following facts from 0 to 10.\n"
        for i, f in enumerate(candidates):
            prompt += f"[{i}] {f['sub']} {f['pred']} {f['obj']}\n"

        prompt += "\nOutput ONLY a comma-separated list of indices sorted by relevance (e.g., 2,0,1)."

        if self._oracle is None:
            return candidates[:5]
        res = await self._oracle.infer(prompt, provider_id=None)
        if res["status"] == "success":
            try:
                # 解析返回的索引列表
                indices = [int(i.strip()) for i in res["content"].split(",") if i.strip().isdigit()]
                reranked = []
                for idx in indices:
                    if 0 <= idx < len(candidates):
                        reranked.append(candidates[idx])
                return reranked[:15]  # LLM 模式可以稍微宽容一点
            except (ValueError, AttributeError):
                _log.warning("⚠️ [Reranker] LLM ranking parse failed. Falling back to default order.")

        return candidates[:10]
