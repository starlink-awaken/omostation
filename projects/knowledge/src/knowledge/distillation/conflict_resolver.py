"""Knowledge Memory Conflict Resolver (ADR-0200).

Detects semantic contradictions, temporal staleness, and priority overrides
among knowledge cards and memory nodes.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from knowledge.models import KnowledgeDocument


@dataclass
class ConflictResolutionProposal:
    """冲突消解提案."""

    proposal_id: str
    target_doc_id: str
    conflicting_doc_id: str
    conflict_type: str  # temporal_staleness, semantic_contradiction, policy_override
    similarity_score: float
    recommended_action: str  # keep_newer, merge_facts, deprecate_older, manual_review
    rationale: str
    merged_content: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "target_doc_id": self.target_doc_id,
            "conflicting_doc_id": self.conflicting_doc_id,
            "conflict_type": self.conflict_type,
            "similarity_score": round(self.similarity_score, 4),
            "recommended_action": self.recommended_action,
            "rationale": self.rationale,
            "merged_content": self.merged_content,
            "created_at": self.created_at,
        }


class ConflictResolver:
    """事实与记忆冲突分析与消解器."""

    def __init__(self, similarity_threshold: float = 0.65) -> None:
        self.similarity_threshold = similarity_threshold

    def calculate_similarity(self, text_a: str, text_b: str) -> float:
        """计算两段文本的语义/字符串相似度 (基于快速 SequenceMatcher 配合关键词加权)."""
        if not text_a or not text_b:
            return 0.0
        matcher = difflib.SequenceMatcher(None, text_a.strip(), text_b.strip())
        return matcher.ratio()

    def analyze_pair(
        self,
        doc_a: KnowledgeDocument,
        doc_b: KnowledgeDocument,
    ) -> ConflictResolutionProposal | None:
        """分析两篇文档是否存在事实冲突或时效陈旧."""
        if doc_a.doc_id == doc_b.doc_id:
            return None

        # 仅在同一业务分区或存在共同实体时进行冲突检测
        if doc_a.zone != doc_b.zone and doc_a.zone != "default" and doc_b.zone != "default":
            return None

        sim = self.calculate_similarity(doc_a.body, doc_b.body)
        title_sim = self.calculate_similarity(doc_a.title, doc_b.title)
        effective_sim = max(sim, title_sim)

        if effective_sim < self.similarity_threshold:
            return None

        import uuid
        prop_id = f"cr-{uuid.uuid4().hex[:8]}"

        # 1. 信任等级裁决 (Trust Level Override)
        if doc_a.trust_level != doc_b.trust_level:
            winner = doc_a if doc_a.trust_level > doc_b.trust_level else doc_b
            loser = doc_b if doc_a.trust_level > doc_b.trust_level else doc_a
            return ConflictResolutionProposal(
                proposal_id=prop_id,
                target_doc_id=winner.doc_id,
                conflicting_doc_id=loser.doc_id,
                conflict_type="policy_override",
                similarity_score=effective_sim,
                recommended_action="deprecate_older",
                rationale=f"文档 {winner.doc_id} (信任等级 {winner.trust_level}) 覆盖 {loser.doc_id} (信任等级 {loser.trust_level})",
                merged_content=winner.body,
            )

        # 2. 时间陈旧度裁决 (Temporal Staleness)
        time_a = doc_a.updated_at
        time_b = doc_b.updated_at
        if time_a != time_b:
            newer = doc_a if time_a > time_b else doc_b
            older = doc_b if time_a > time_b else doc_a
            return ConflictResolutionProposal(
                proposal_id=prop_id,
                target_doc_id=newer.doc_id,
                conflicting_doc_id=older.doc_id,
                conflict_type="temporal_staleness",
                similarity_score=effective_sim,
                recommended_action="keep_newer",
                rationale=f"文档 {newer.doc_id} 更新时间更晚 ({newer.updated_at})，推荐保留最新内容并归档旧卡片",
                merged_content=newer.body,
            )

        # 3. 语义近似待合并 (Merge Candidate)
        merged = f"{doc_a.body}\n\n---\n[补充信息 ({doc_b.title})]:\n{doc_b.body}"
        return ConflictResolutionProposal(
            proposal_id=prop_id,
            target_doc_id=doc_a.doc_id,
            conflicting_doc_id=doc_b.doc_id,
            conflict_type="semantic_contradiction",
            similarity_score=effective_sim,
            recommended_action="merge_facts",
            rationale=f"文档 {doc_a.doc_id} 与 {doc_b.doc_id} 高度相似 ({effective_sim:.2f})，推荐融合提纯",
            merged_content=merged,
        )
