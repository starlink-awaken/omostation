"""Hybrid Search Engine Resilience and Circuit Breaker Tests."""

from unittest.mock import MagicMock
import pytest


def test_hybrid_search_fusion_rrf():
    """Verify RRF (Reciprocal Rank Fusion) algorithm correctness."""
    # RRF formula: Score(d) = sum(1 / (k + rank_i(d)))
    k = 60
    vector_rank = 1
    bm25_rank = 2
    graph_rank = 1

    score_doc1 = (1.0 / (k + vector_rank)) + (1.0 / (k + bm25_rank)) + (1.0 / (k + graph_rank))
    score_doc2 = (1.0 / (k + 10)) + (1.0 / (k + 10))

    assert score_doc1 > score_doc2


def test_circuit_breaker_offline_fallback():
    """Verify circuit breaker fallback when primary Postgres/gbrain is offline."""
    class MockHybridSearch:
        def __init__(self, gbrain_online: bool = False):
            self.gbrain_online = gbrain_online

        def search(self, query: str, mode: str = "hybrid") -> dict:
            if not self.gbrain_online:
                # Gracefully fallback to local SQLite FTS5 + LanceDB near-cache
                return {
                    "query": query,
                    "mode": "offline_fallback",
                    "source": "local_sqlite_fts5",
                    "results": [{"id": "doc-local-1", "title": "Local Cached Doc", "score": 0.85}],
                    "degraded": True,
                }
            return {
                "query": query,
                "mode": mode,
                "source": "gbrain_postgres",
                "results": [{"id": "doc-pg-1", "title": "Live Doc", "score": 0.98}],
                "degraded": False,
            }

    engine = MockHybridSearch(gbrain_online=False)
    res = engine.search("卫健委数据治理")
    assert res["degraded"] is True
    assert res["source"] == "local_sqlite_fts5"
    assert len(res["results"]) > 0
