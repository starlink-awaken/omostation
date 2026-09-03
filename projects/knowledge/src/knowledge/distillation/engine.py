"""Memory Self-Distillation Engine (ADR-0200).

Orchestrates nightly batch scanning, proactive contradiction elimination,
and Golden Truth Card distillation using P2 idle compute.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from knowledge.distillation.conflict_resolver import ConflictResolutionProposal, ConflictResolver
from knowledge.models import KnowledgeDocument

logger = logging.getLogger("knowledge.distillation")


class MemoryDistillationEngine:
    """记忆自蒸馏与冲突自愈引擎 (Memory Distillation Engine)."""

    def __init__(self, conflict_resolver: ConflictResolver | None = None) -> None:
        self.resolver = conflict_resolver or ConflictResolver()

    def distill_documents(
        self,
        documents: list[KnowledgeDocument],
        auto_apply: bool = False,
    ) -> dict[str, Any]:
        """对输入文档集执行蒸馏与冲突消解分析."""
        t0 = time.monotonic()
        proposals: list[ConflictResolutionProposal] = []
        golden_cards: list[KnowledgeDocument] = []
        seen_pairs: set[tuple[str, str]] = set()

        doc_count = len(documents)
        for i in range(doc_count):
            for j in range(i + 1, doc_count):
                doc_a = documents[i]
                doc_b = documents[j]
                pair_key = (min(doc_a.doc_id, doc_b.doc_id), max(doc_a.doc_id, doc_b.doc_id))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                prop = self.resolver.analyze_pair(doc_a, doc_b)
                if prop:
                    proposals.append(prop)

        # 生成黄金提纯卡片 (Golden Truth Cards)
        for doc in documents:
            # 过滤掉作为冲突被淘汰的 doc_id
            deprecated_ids = {p.conflicting_doc_id for p in proposals if p.recommended_action in ("keep_newer", "deprecate_older")}
            if doc.doc_id in deprecated_ids:
                continue

            golden_cards.append(
                KnowledgeDocument(
                    doc_id=f"golden-{doc.doc_id}",
                    title=f"⭐ [Golden] {doc.title}",
                    body=doc.body,
                    zone=doc.zone,
                    trust_level=min(5, doc.trust_level + 1),
                    metadata={**doc.metadata, "distilled": True, "source_id": doc.doc_id},
                )
            )

        elapsed_ms = round((time.monotonic() - t0) * 1000, 2)
        summary = {
            "status": "completed",
            "scanned_docs": doc_count,
            "conflicts_detected": len(proposals),
            "golden_cards_generated": len(golden_cards),
            "proposals": [p.to_dict() for p in proposals],
            "auto_applied": auto_apply,
            "elapsed_ms": elapsed_ms,
        }
        logger.info(f"Distillation completed: {doc_count} docs, {len(proposals)} conflicts in {elapsed_ms}ms")
        return summary
