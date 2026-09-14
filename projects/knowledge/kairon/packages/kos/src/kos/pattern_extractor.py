"""模式提取器 — 从 D_KnowledgeIntegration 提取并适配到 kos。

从 MemoryGraph 中提取知识模式，支持：
- 频繁模式挖掘
- 时序模式分析
- 因果关系推断
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from eidos.memory_graph import MemoryGraph  # type: ignore[reportMissingImports]

logger = logging.getLogger(__name__)


# ── 本地数据模型 ──────────────────────────────────────────────


@dataclass
class EvolutionPattern:
    """进化模式数据结构"""

    pattern_id: str
    pattern_type: str
    facts: list[tuple[str, str, str]]
    confidence: float
    frequency: int
    source_context: dict[str, Any]
    extracted_at: float
    validated: bool = False


# ── 主类 ─────────────────────────────────────────────────────


class PatternExtractor:
    """模式提取器实现。

    从 MemoryGraph 中提取知识模式，支持:
    - 频繁模式挖掘
    - 时序模式分析
    - 因果关系推断
    """

    def __init__(self, fact_graph: MemoryGraph, min_confidence: float = 0.7, min_frequency: int = 3) -> None:
        self.fact_graph = fact_graph
        self.min_confidence = min_confidence
        self.min_frequency = min_frequency
        self._stats = {"total_extractions": 0, "patterns_found": 0, "last_extraction": None}

    async def extract_patterns(
        self, domain: str | None = None, time_window: tuple[float, float] | None = None
    ) -> list[EvolutionPattern]:
        logger.info(f"Starting pattern extraction for domain={domain}, time_window={time_window}")

        patterns = []  # type: ignore[var-annotated]

        try:
            query_filters = {}
            if domain:
                query_filters["domain"] = domain
            if time_window:
                query_filters["start_ts"] = time_window[0]  # type: ignore[assignment]
                query_filters["end_ts"] = time_window[1]  # type: ignore[assignment]

            triples = await self._fetch_triples(query_filters)

            if not triples:
                logger.warning("No triples found for pattern extraction")
                return patterns

            freq_patterns = self._mine_frequent_patterns(triples)
            for fp in freq_patterns:
                pattern = EvolutionPattern(
                    pattern_id=str(uuid.uuid4()),
                    pattern_type="FREQUENT",
                    facts=fp["triples"],
                    confidence=fp["confidence"],
                    frequency=fp["frequency"],
                    source_context={"domain": domain, "algorithm": "frequent_itemsets"},
                    extracted_at=datetime.now().timestamp(),
                    validated=False,
                )
                patterns.append(pattern)

            assoc_patterns = self._mine_association_rules(triples)
            for ap in assoc_patterns:
                pattern = EvolutionPattern(
                    pattern_id=str(uuid.uuid4()),
                    pattern_type="CORRELATION",
                    facts=ap["triples"],
                    confidence=ap["confidence"],
                    frequency=ap["support"],
                    source_context={"domain": domain, "algorithm": "association_rules"},
                    extracted_at=datetime.now().timestamp(),
                    validated=False,
                )
                patterns.append(pattern)

            self._stats["total_extractions"] += 1  # type: ignore[operator]
            self._stats["patterns_found"] += len(patterns)  # type: ignore[operator]
            self._stats["last_extraction"] = datetime.now().isoformat()  # type: ignore[assignment]

            logger.info(f"Extracted {len(patterns)} patterns")

        except (OSError, ValueError, KeyError, RuntimeError) as e:
            logger.error(f"Pattern extraction failed: {e}")
            raise

        return patterns

    def validate_pattern(self, pattern: EvolutionPattern, test_data: list[tuple[str, str, str]]) -> bool:
        if not test_data:
            return False

        match_count = 0
        for fact in pattern.facts:
            if fact in test_data:
                match_count += 1

        if not pattern.facts:
            return False

        validation_confidence = match_count / len(pattern.facts)
        is_valid = validation_confidence >= self.min_confidence

        logger.info(f"Pattern {pattern.pattern_id} validation: {validation_confidence:.2f} (valid={is_valid})")
        return is_valid

    async def _fetch_triples(self, filters: dict[str, Any]) -> list[tuple[str, str, str]]:
        try:
            query_filters = dict(filters)
            query_filters.setdefault("_local_only", True)
            results = self.fact_graph.federated_query(query_filters)
            if isinstance(results, Awaitable):
                results = await results
            if isinstance(results, dict):
                results = results.get("results", [])
            triples = []
            for r in results:
                if "sub" in r and "pred" in r and "obj" in r:
                    triples.append((r["sub"], r["pred"], r["obj"]))
            return triples
        except (OSError, ValueError, KeyError, RuntimeError) as e:
            logger.warning(f"Failed to fetch triples: {e}")
            return []

    def _mine_frequent_patterns(self, triples: list[tuple[str, str, str]]) -> list[dict[str, Any]]:
        pred_counts: dict[str, int] = {}
        for _s, p, _o in triples:
            pred_counts[p] = pred_counts.get(p, 0) + 1

        frequent_preds = {p: c for p, c in pred_counts.items() if c >= self.min_frequency}

        patterns = []
        for pred, count in frequent_preds.items():
            related_triples = [(s, p, o) for s, p, o in triples if p == pred]
            if len(related_triples) >= self.min_frequency:
                confidence = min(count / len(triples), 1.0)
                if confidence >= self.min_confidence:
                    patterns.append(
                        {
                            "triples": related_triples[:10],
                            "confidence": confidence,
                            "frequency": count,
                        }
                    )

        return patterns

    def _mine_association_rules(self, triples: list[tuple[str, str, str]]) -> list[dict[str, Any]]:
        subject_groups: dict[str, list[tuple[str, str, str]]] = {}

        for s, p, o in triples:
            if s not in subject_groups:
                subject_groups[s] = []
            subject_groups[s].append((s, p, o))

        patterns = []
        for _subject, group in subject_groups.items():
            if len(group) >= self.min_frequency:
                support = len(group) / len(triples) if triples else 0
                confidence = min(support * 2, 1.0)

                if confidence >= self.min_confidence:
                    patterns.append({"triples": group[:10], "confidence": confidence, "support": len(group)})

        return patterns

    def get_stats(self) -> dict[str, Any]:
        return self._stats.copy()
