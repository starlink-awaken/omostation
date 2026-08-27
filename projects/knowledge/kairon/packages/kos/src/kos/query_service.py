"""知识查询服务 — 从 D_KnowledgeIntegration 提取并适配到 kos。

提供三种查询模式：semantic（语义搜索）、triple（精确三元组查询）、subject（主体递归查询）。
优先使用向量适配器，失败时回退到关键词匹配（FTS5 > LIKE）。
"""

from __future__ import annotations

import importlib
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol, cast

import numpy as np
import numpy.typing as npt

if TYPE_CHECKING:
    from eidos.memory_graph import MemoryGraph  # type: ignore[reportMissingImports]

_log = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.3
type NumericArray = npt.NDArray[np.float32] | npt.NDArray[np.float64]
RowDict = dict[str, object]
RowMapping = Mapping[str, object]
MetadataDict = dict[str, object]
QueryStats = dict[str, object]


# ── 本地数据模型 ──────────────────────────────────────────────


@dataclass
class KnowledgeTriple:
    """知识三元组"""

    subject: str
    predicate: str
    obj: str
    metadata: MetadataDict

    def to_tuple(self) -> tuple[str, str, str, MetadataDict]:
        return (self.subject, self.predicate, self.obj, self.metadata)


# ── 本地异常 ──────────────────────────────────────────────────


class QueryError(Exception):
    """知识查询错误"""

    def __init__(self, message: str, query: str | None = None) -> None:
        self.query = query
        super().__init__(message)


# ── 协议定义 ──────────────────────────────────────────────────


class VectorAdapter(Protocol):
    dimension: int

    async def get_embedding(self, text: str) -> NumericArray: ...
    async def get_embeddings(self, texts: list[str]) -> list[NumericArray]: ...
    def cosine_similarity(self, vec1: NumericArray, vec2: NumericArray) -> float: ...


class VectorAdapterFactory(Protocol):
    def __call__(self, provider_type: str | None = None) -> VectorAdapter: ...


class LegacyEmbeddingEngine(Protocol):
    def get_embedding(self, text: str) -> NumericArray | None: ...


class EmbeddingEngineFactory(Protocol):
    def __call__(self) -> LegacyEmbeddingEngine: ...


class _CursorProtocol(Protocol):
    def fetchall(self) -> Sequence[RowMapping]: ...


class _ConnectionProtocol(Protocol):
    def execute(self, sql: str, params: Sequence[str]) -> _CursorProtocol: ...


class _FactGraphConnectionAccessor(Protocol):
    def _get_connection(self) -> _ConnectionProtocol: ...


# ── 延迟加载 Embedding 引擎 ──────────────────────────────────

# D-Harvest embeddings (优先)
try:
    _harvest_embeddings = importlib.import_module("organs.D_Harvest.embeddings")
    HAS_HARVEST_EMBEDDINGS = True
except (ImportError, AttributeError):
    _harvest_embeddings = None  # type: ignore[assignment]
    HAS_HARVEST_EMBEDDINGS = False

# VectorSearchAdapter
try:
    from .vector_search_adapter import VectorSearchAdapter as _VectorSearchAdapter  # type: ignore[import-not-found]

    VectorSearchAdapter: VectorAdapterFactory | None = cast(
        VectorAdapterFactory,
        _VectorSearchAdapter,
    )
    HAS_VECTOR_ADAPTER = True
except (ImportError, AttributeError):
    VectorSearchAdapter = None
    HAS_VECTOR_ADAPTER = False

# 旧版 EmbeddingEngine — D_Memory 引用已移除，stub 为 None
EmbeddingEngine: EmbeddingEngineFactory | None = None
HAS_EMBEDDING = False


class KnowledgeQueryService:
    """知识查询服务实现。

    提供三种查询模式：
    - semantic: 语义搜索（基于向量相似度）
    - triple: 精确三元组查询
    - subject: 主体查询（递归查询）
    """

    def __init__(self, memory_graph: MemoryGraph) -> None:
        self._fg = memory_graph
        self._stats: dict[str, int] = {
            "total_queries": 0,
            "semantic_queries": 0,
            "triple_queries": 0,
            "subject_queries": 0,
            "errors": 0,
        }
        self._vector_adapter: VectorAdapter | None = None
        self._use_vector_adapter = False
        self._embedding_engine = self._create_embedding_engine()

    async def query_knowledge(
        self,
        query: str,
        query_type: str = "semantic",
        limit: int = 100,
        min_quality: float = 0.6,
        time_window_hours: int | None = None,
    ) -> list[KnowledgeTriple]:
        self._stats["total_queries"] += 1

        try:
            if query_type == "semantic":
                self._stats["semantic_queries"] += 1
                return await self.semantic_search(query, limit, time_window_hours)
            elif query_type == "triple":
                self._stats["triple_queries"] += 1
                return await self._triple_query(query, limit, time_window_hours)
            elif query_type == "subject":
                self._stats["subject_queries"] += 1
                return await self._subject_query(query, limit, time_window_hours)
            else:
                raise QueryError(f"Unknown query_type: {query_type}", query=query)
        except (OSError, ValueError, KeyError, RuntimeError) as e:
            self._stats["errors"] += 1
            _log.error(f"Query failed: {e}", exc_info=True)
            raise QueryError(f"Query failed: {e}", query=query) from e

    async def semantic_search(
        self, query_text: str, limit: int = 100, time_window_hours: int | None = None
    ) -> list[KnowledgeTriple]:
        _log.debug(f"Semantic search: {query_text}")

        vector_results = await self._semantic_vector_search(query_text, limit, time_window_hours)
        if vector_results is not None:
            return vector_results

        return self._semantic_keyword_search(query_text, limit, time_window_hours)

    def _create_embedding_engine(self) -> VectorAdapter | LegacyEmbeddingEngine | None:
        # 优先使用 VectorSearchAdapter
        if HAS_VECTOR_ADAPTER and VectorSearchAdapter is not None:
            try:
                provider_type = None  # auto-detect
                adapter = VectorSearchAdapter(provider_type=provider_type)
                _log.info(
                    f"KnowledgeQueryService: Using VectorSearchAdapter (provider_type=auto, dim={adapter.dimension})"
                )
                self._vector_adapter = adapter
                self._use_vector_adapter = True
                return adapter
            except (OSError, ValueError, RuntimeError) as e:
                _log.warning(f"VectorSearchAdapter initialization failed: {e}")

        # 旧版 EmbeddingEngine 已移除（原 D_Memory 依赖），直接进入关键词回退
        _log.info("KnowledgeQueryService: No embedding engine available, using keyword fallback")
        self._vector_adapter = None
        self._use_vector_adapter = False
        return None

    async def _semantic_vector_search(
        self, query_text: str, limit: int, time_window_hours: int | None
    ) -> list[KnowledgeTriple] | None:
        if self._embedding_engine is None:
            return None

        try:
            if getattr(self, "_use_vector_adapter", False) and self._vector_adapter is not None:
                return await self._vector_search_with_adapter(query_text, limit, time_window_hours)

            return await self._vector_search_with_legacy(query_text, limit, time_window_hours)

        except (OSError, ValueError, KeyError, RuntimeError) as e:
            _log.warning(f"Embedding semantic search failed; falling back to keyword search: {e}")
            return None

    async def _vector_search_with_adapter(
        self, query_text: str, limit: int, time_window_hours: int | None
    ) -> list[KnowledgeTriple]:
        adapter = self._vector_adapter
        if adapter is None:
            return []

        query_vector = await adapter.get_embedding(query_text)

        candidates = self._fg.query()
        if not candidates:
            return []

        candidate_texts = []
        candidate_rows = []
        for row in candidates:
            text = self._build_triple_text(row)
            if text:
                candidate_texts.append(text)
                candidate_rows.append((row, text))

        candidate_vectors = await adapter.get_embeddings(candidate_texts)

        scored_triples: list[tuple[float, KnowledgeTriple]] = []
        for (row, _text), vec in zip(candidate_rows, candidate_vectors, strict=False):
            similarity = adapter.cosine_similarity(query_vector, vec)
            if similarity >= SIMILARITY_THRESHOLD:
                triple = self._build_knowledge_triple(
                    row,
                    extra_metadata={"similarity": similarity, "search_method": "vector_adapter"},
                )
                if triple is not None:
                    scored_triples.append((similarity, triple))

        scored_triples.sort(key=lambda item: item[0], reverse=True)
        triples = [triple for _, triple in scored_triples[:limit]]

        if time_window_hours:
            return self._filter_by_time_window(triples, time_window_hours)
        return triples

    async def _vector_search_with_legacy(
        self, query_text: str, limit: int, time_window_hours: int | None
    ) -> list[KnowledgeTriple]:
        if self._embedding_engine is None:
            return []

        legacy_engine = cast(LegacyEmbeddingEngine, self._embedding_engine)
        query_vector = legacy_engine.get_embedding(query_text)
        if query_vector is None:
            _log.warning("EmbeddingEngine returned no query embedding; falling back to keyword search")
            return []

        candidates = self._fg.query()
        scored_triples: list[tuple[float, KnowledgeTriple]] = []
        for row in candidates or []:
            triple_text = self._build_triple_text(row)
            triple_vector = legacy_engine.get_embedding(triple_text)
            if triple_vector is None:
                continue

            similarity = self._cosine_similarity(query_vector, triple_vector)
            if similarity < SIMILARITY_THRESHOLD:
                continue

            triple = self._build_knowledge_triple(
                row,
                extra_metadata={"similarity": similarity, "search_method": "legacy_engine"},
            )
            if triple is not None:
                scored_triples.append((similarity, triple))

        scored_triples.sort(key=lambda item: item[0], reverse=True)
        triples = [triple for _, triple in scored_triples[:limit]]

        if time_window_hours:
            return self._filter_by_time_window(triples, time_window_hours)
        return triples

    def _semantic_keyword_search(
        self, query_text: str, limit: int, time_window_hours: int | None
    ) -> list[KnowledgeTriple]:
        keywords = [kw for kw in query_text.strip().split() if len(kw) >= 2]
        if not keywords:
            return []

        # 尝试使用 FTS5 全文搜索
        try:
            if hasattr(self._fg, "fts_search"):
                fts_query = " OR ".join(keywords)
                rows = self._fg.fts_search(fts_query, limit=limit * 2)
                if rows:
                    triples = []
                    for row in rows[:limit]:
                        triple = self._build_knowledge_triple(
                            row,
                            extra_metadata={
                                "search_rank": row.get("search_rank"),
                                "search_method": "fts5",
                            },
                        )
                        if triple:
                            triples.append(triple)

                    if time_window_hours:
                        triples = self._filter_by_time_window(triples, time_window_hours)
                    return triples
        except (OSError, ValueError, KeyError, RuntimeError) as e:
            _log.debug(f"FTS5 search unavailable, falling back to LIKE: {e}")

        return self._keyword_search_like(keywords, limit, time_window_hours)

    def _keyword_search_like(
        self, keywords: list[str], limit: int, time_window_hours: int | None
    ) -> list[KnowledgeTriple]:
        try:
            like_clauses: list[str] = []
            params: list[str] = []
            for kw in keywords:
                pattern = f"%{kw}%"
                like_clauses.append("(LOWER(sub) LIKE ? OR LOWER(pred) LIKE ? OR LOWER(obj) LIKE ?)")
                params.extend([pattern, pattern, pattern])

            where = " OR ".join(like_clauses)
            sql = (
                "SELECT id, sub, pred, obj, metadata, timestamp, importance, "
                "source_node_id FROM fact_triples WHERE " + where
            )

            conn = cast(_FactGraphConnectionAccessor, self._fg)._get_connection()
            cursor = conn.execute(sql, params)
            rows = [dict(row) for row in cursor.fetchall()]
        except (OSError, ValueError, KeyError, RuntimeError) as e:
            _log.warning(f"Semantic SQL search failed, returning empty: {e}")
            return []

        if not rows:
            return []

        now = datetime.now(UTC)
        scored: list[tuple[float, RowDict]] = []
        for row in rows:
            text_blob = (
                f"{self._get_row_text(row, 'sub', 'subject')} "
                f"{self._get_row_text(row, 'pred', 'predicate')} "
                f"{self._get_row_text(row, 'obj', 'object')}"
            ).lower()
            match_count = sum(1 for kw in keywords if kw.lower() in text_blob)
            score = match_count / len(keywords)

            ts_val = row.get("timestamp")
            timestamp_value = self._coerce_float(ts_val)
            if timestamp_value is not None:
                try:
                    age_hours = (now.timestamp() - timestamp_value) / 3600
                    recency_bonus = max(0.0, 0.3 * (1.0 - age_hours / 8760))
                except (ValueError, TypeError):
                    recency_bonus = 0.0
            else:
                recency_bonus = 0.0

            score += recency_bonus
            scored.append((score, row))

        scored.sort(key=lambda x: x[0], reverse=True)

        triples = self._parse_query_results(
            [row for _, row in scored[:limit]],
            time_window_hours,
        )
        return triples

    async def _triple_query(
        self, query: str, limit: int = 100, time_window_hours: int | None = None
    ) -> list[KnowledgeTriple]:
        parts = query.strip().split()
        if len(parts) < 2:
            raise QueryError("Triple query requires at least subject and predicate", query=query)

        sub = parts[0]
        pred = parts[1]
        obj = parts[2] if len(parts) > 2 else None

        try:
            results = self._fg.query(sub, pred, obj)
            return self._parse_query_results(results, time_window_hours)
        except (OSError, ValueError, KeyError, RuntimeError) as e:
            _log.error(f"Triple query failed: {e}")
            return []

    async def _subject_query(
        self, subject: str, limit: int = 100, time_window_hours: int | None = None
    ) -> list[KnowledgeTriple]:
        try:
            results = self._fg.recursive_query(subject, max_depth=2)
            triples = self._parse_query_results(results, time_window_hours)
            return triples[:limit]
        except (OSError, ValueError, KeyError, RuntimeError) as e:
            _log.error(f"Subject query failed: {e}")
            return []

    def _parse_query_results(
        self, results: Sequence[RowMapping] | None, time_window_hours: int | None = None
    ) -> list[KnowledgeTriple]:
        if not results:
            return []

        triples: list[KnowledgeTriple] = []

        for row in results:
            triple = self._build_knowledge_triple(row)
            if triple is not None:
                triples.append(triple)

        if time_window_hours:
            return self._filter_by_time_window(triples, time_window_hours)

        return triples

    def _parse_federated_results(self, results: Sequence[RowMapping] | None) -> list[KnowledgeTriple]:
        if not results:
            return []

        triples: list[KnowledgeTriple] = []
        for row in results:
            try:
                triples.append(
                    KnowledgeTriple(
                        subject=self._get_row_text(row, "sub", "subject"),
                        predicate=self._get_row_text(row, "pred", "predicate"),
                        obj=self._get_row_text(row, "obj", "object"),
                        metadata={"source": row.get("source_node_id", "federated")},
                    )
                )
            except (ValueError, KeyError, TypeError):
                continue

        return triples

    def _build_knowledge_triple(
        self, row: RowMapping, extra_metadata: MetadataDict | None = None
    ) -> KnowledgeTriple | None:
        try:
            sub = self._get_row_text(row, "sub", "subject")
            pred = self._get_row_text(row, "pred", "predicate")
            obj = self._get_row_text(row, "obj", "object")

            if not sub or not pred:
                return None

            metadata: MetadataDict = {
                "source": row.get("source_node_id", row.get("source", "unknown")),
                "timestamp": row.get("timestamp", ""),
            }
            if extra_metadata:
                metadata.update(extra_metadata)

            return KnowledgeTriple(subject=sub, predicate=pred, obj=obj, metadata=metadata)
        except (OSError, ValueError, KeyError, RuntimeError) as e:
            _log.debug(f"Failed to build knowledge triple: {e}")
            return None

    def _build_triple_text(self, row: RowMapping) -> str:
        sub = self._get_row_text(row, "sub", "subject")
        pred = self._get_row_text(row, "pred", "predicate")
        obj = self._get_row_text(row, "obj", "object")
        return f"{sub} {pred} {obj}"

    def _get_row_text(self, row: RowMapping, primary_key: str, fallback_key: str) -> str:
        value = row.get(primary_key) or row.get(fallback_key, "")
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return str(value)

    def _coerce_float(self, value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
        return None

    def _cosine_similarity(self, vec1: NumericArray, vec2: NumericArray) -> float:
        try:
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return float(np.dot(vec1, vec2) / (norm1 * norm2))
        except (ValueError, TypeError, RuntimeError):
            return 0.0

    def _filter_by_time_window(self, triples: list[KnowledgeTriple], hours: int) -> list[KnowledgeTriple]:
        now = datetime.now(UTC)
        filtered: list[KnowledgeTriple] = []

        for triple in triples:
            ts_value = triple.metadata.get("timestamp")
            if isinstance(ts_value, str) and ts_value:
                try:
                    ts = datetime.fromisoformat(ts_value.replace("Z", "+00:00"))
                    age_hours = (now - ts).total_seconds() / 3600
                    if age_hours <= hours:
                        filtered.append(triple)
                except (ValueError, TypeError):
                    filtered.append(triple)
            else:
                filtered.append(triple)

        return filtered

    def get_query_stats(self) -> QueryStats:
        return {
            "total_queries": self._stats["total_queries"],
            "by_type": {
                "semantic": self._stats["semantic_queries"],
                "triple": self._stats["triple_queries"],
                "subject": self._stats["subject_queries"],
            },
            "errors": self._stats["errors"],
            "success_rate": (
                (self._stats["total_queries"] - self._stats["errors"]) / max(self._stats["total_queries"], 1)
            ),
        }
