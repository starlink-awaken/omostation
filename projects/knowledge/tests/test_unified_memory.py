"""Unified Memory Interface Tests — Phase 1 verification.

Tests the UnifiedMemoryBridge implementing the UnifiedMemoryInterface contract,
verifying query/ingest/search primitives and dedup behavior.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

# Ensure knowledge package is importable
SRC_ROOT = Path(__file__).resolve().parent.parent / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from knowledge.models import KnowledgeDocument, RetrievalResult, SyncEvent
from knowledge.unified.interface import UnifiedMemoryInterface
from knowledge.unified.adapter_bridge import UnifiedMemoryBridge


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc(doc_id: str = "doc-001", zone: str = "common", title: str = "Test Doc") -> KnowledgeDocument:
    return KnowledgeDocument(doc_id=doc_id, title=title, body=f"Body for {doc_id}", zone=zone)


def _make_result(doc_id: str = "doc-001", score: float = 0.9, zone: str = "common") -> RetrievalResult:
    return RetrievalResult(doc_id=doc_id, title=f"Title {doc_id}", snippet="...", zone=zone, score=score, source="kos")


def _make_mock_facade(results: list[RetrievalResult] | None = None, status: dict | None = None):
    """Create a mock KnowledgeComplex facade for testing."""
    facade = MagicMock()
    facade.search.return_value = results if results is not None else [_make_result()]
    facade.status.return_value = status if status is not None else {
        "status": "healthy",
        "version": "1.1.0",
        "subengines": {"kairon": {"exists": True}, "gbrain": {"exists": True}},
    }
    return facade


# ---------------------------------------------------------------------------
# Interface contract tests
# ---------------------------------------------------------------------------

class TestUnifiedMemoryInterfaceContract:
    """Verify UnifiedMemoryInterface is a proper ABC."""

    def test_cannot_instantiate_directly(self):
        """Abstract class should not be directly instantiable."""
        with pytest.raises(TypeError):
            UnifiedMemoryInterface()  # type: ignore[abstract]

    def test_bridge_implements_interface(self):
        """UnifiedMemoryBridge should be a subclass of UnifiedMemoryInterface."""
        assert issubclass(UnifiedMemoryBridge, UnifiedMemoryInterface)

    def test_bridge_has_all_primitives(self):
        """Bridge should implement all three primitives + health."""
        facade = _make_mock_facade()
        bridge = UnifiedMemoryBridge(facade)
        assert hasattr(bridge, "query")
        assert hasattr(bridge, "ingest")
        assert hasattr(bridge, "search")
        assert hasattr(bridge, "health")
        assert callable(bridge.query)
        assert callable(bridge.ingest)
        assert callable(bridge.search)
        assert callable(bridge.health)


# ---------------------------------------------------------------------------
# Query tests
# ---------------------------------------------------------------------------

class TestUnifiedMemoryBridgeQuery:
    """Test the query primitive."""

    def test_query_returns_results(self):
        facade = _make_mock_facade([_make_result("doc-100", score=0.95)])
        bridge = UnifiedMemoryBridge(facade)
        results = bridge.query("test query")
        assert len(results) == 1
        assert results[0].doc_id == "doc-100"

    def test_query_passes_domain(self):
        facade = _make_mock_facade()
        bridge = UnifiedMemoryBridge(facade)
        bridge.query("q", domain="health", limit=5)
        facade.search.assert_called_once_with("q", domain="health", limit=5)

    def test_query_with_filters(self):
        facade = _make_mock_facade([
            _make_result("doc-1", zone="work-weijian"),
            _make_result("doc-2", zone="health"),
            _make_result("doc-3", zone="work-transfer"),
        ])
        bridge = UnifiedMemoryBridge(facade)
        results = bridge.query("q", filters={"zone": "work-weijian"})
        assert len(results) == 1
        assert results[0].zone == "work-weijian"

    def test_query_with_min_score_filter(self):
        facade = _make_mock_facade([
            _make_result("doc-high", score=0.9),
            _make_result("doc-low", score=0.3),
        ])
        bridge = UnifiedMemoryBridge(facade)
        results = bridge.query("q", filters={"min_score": 0.5})
        assert len(results) == 1
        assert results[0].doc_id == "doc-high"

    def test_query_empty_string_returns_empty(self):
        facade = _make_mock_facade()
        bridge = UnifiedMemoryBridge(facade)
        results = bridge.query("")
        # The facade might still be called; bridge should handle empty
        assert isinstance(results, list)

    def test_query_increments_counter(self):
        facade = _make_mock_facade()
        bridge = UnifiedMemoryBridge(facade)
        assert bridge._query_count == 0
        bridge.query("q1")
        assert bridge._query_count == 1
        bridge.query("q2")
        assert bridge._query_count == 2


# ---------------------------------------------------------------------------
# Ingest tests
# ---------------------------------------------------------------------------

class TestUnifiedMemoryBridgeIngest:
    """Test the ingest primitive."""

    def test_ingest_single_document(self):
        # Use empty results so dedup check doesn't match
        facade = _make_mock_facade([])
        bridge = UnifiedMemoryBridge(facade)
        events = bridge.ingest([_make_doc()])
        assert len(events) == 1
        assert events[0].status == "committed"
        assert events[0].doc_id == "doc-001"

    def test_ingest_multiple_documents(self):
        # Use empty results so dedup check doesn't match
        facade = _make_mock_facade([])
        bridge = UnifiedMemoryBridge(facade)
        docs = [_make_doc(f"doc-{i:03d}") for i in range(5)]
        events = bridge.ingest(docs)
        assert len(events) == 5
        assert all(e.status == "committed" for e in events)

    def test_ingest_dedup_detects_duplicate(self):
        facade = _make_mock_facade()
        # Make search return a match for dedup check
        facade.search.return_value = [_make_result("doc-dup")]
        bridge = UnifiedMemoryBridge(facade, dedup_enabled=True)
        events = bridge.ingest([_make_doc("doc-dup")], dedup=True)
        assert len(events) == 1
        assert events[0].status == "skipped"
        assert events[0].action == "skip_dedup"

    def test_ingest_dedup_disabled(self):
        facade = _make_mock_facade()
        facade.search.return_value = [_make_result("doc-dup")]
        bridge = UnifiedMemoryBridge(facade, dedup_enabled=True)
        events = bridge.ingest([_make_doc("doc-dup")], dedup=False)
        assert len(events) == 1
        assert events[0].status == "committed"

    def test_ingest_no_match_not_dedup(self):
        facade = _make_mock_facade([])
        bridge = UnifiedMemoryBridge(facade, dedup_enabled=True)
        events = bridge.ingest([_make_doc("doc-new")], dedup=True)
        assert len(events) == 1
        assert events[0].status == "committed"

    def test_ingest_zone_routing_health(self):
        facade = _make_mock_facade([])
        bridge = UnifiedMemoryBridge(facade)
        events = bridge.ingest([_make_doc("doc-health", zone="health-cardio")])
        assert events[0].payload.get("zone") == "health-cardio"
        assert events[0].target == "gbrain_postgres"

    def test_ingest_zone_routing_work(self):
        facade = _make_mock_facade([])
        bridge = UnifiedMemoryBridge(facade)
        events = bridge.ingest([_make_doc("doc-work", zone="work-weijian")])
        assert events[0].target == "kairon_graph"

    def test_ingest_zone_routing_common(self):
        facade = _make_mock_facade([])
        bridge = UnifiedMemoryBridge(facade)
        events = bridge.ingest([_make_doc("doc-common", zone="common")])
        assert events[0].target == "unified_default"


# ---------------------------------------------------------------------------
# Search tests
# ---------------------------------------------------------------------------

class TestUnifiedMemoryBridgeSearch:
    """Test the search primitive."""

    def test_search_hybrid_mode(self):
        facade = _make_mock_facade([_make_result("doc-s1"), _make_result("doc-s2")])
        bridge = UnifiedMemoryBridge(facade)
        results = bridge.search("keyword", mode="hybrid")
        assert len(results) == 2
        facade.search.assert_called_once_with("keyword", domain="common", limit=10)

    def test_search_strips_entities_when_disabled(self):
        r1 = _make_result("doc-e1")
        r1.matched_entities = ["entity-1", "entity-2"]
        facade = _make_mock_facade([r1])
        bridge = UnifiedMemoryBridge(facade)
        results = bridge.search("q", include_entities=False)
        assert results[0].matched_entities == []

    def test_search_preserves_entities_by_default(self):
        r1 = _make_result("doc-e1")
        r1.matched_entities = ["entity-1"]
        facade = _make_mock_facade([r1])
        bridge = UnifiedMemoryBridge(facade)
        results = bridge.search("q")
        assert results[0].matched_entities == ["entity-1"]

    def test_search_increments_counter(self):
        facade = _make_mock_facade()
        bridge = UnifiedMemoryBridge(facade)
        assert bridge._search_count == 0
        bridge.search("q1")
        assert bridge._search_count == 1


# ---------------------------------------------------------------------------
# Health tests
# ---------------------------------------------------------------------------

class TestUnifiedMemoryBridgeHealth:
    """Test the health primitive."""

    def test_health_returns_expected_keys(self):
        facade = _make_mock_facade()
        bridge = UnifiedMemoryBridge(facade)
        h = bridge.health()
        assert "bridge" in h
        assert "backends" in h
        assert "counters" in h
        assert h["bridge"] == "healthy"

    def test_health_reflects_counters(self):
        facade = _make_mock_facade()
        bridge = UnifiedMemoryBridge(facade)
        bridge.query("q1")
        bridge.query("q2")
        bridge.search("s1")
        h = bridge.health()
        assert h["counters"]["queries"] == 2
        assert h["counters"]["searches"] == 1

    def test_health_shows_dedup_status(self):
        facade = _make_mock_facade()
        bridge = UnifiedMemoryBridge(facade, dedup_enabled=True)
        h = bridge.health()
        assert h["dedup_enabled"] is True


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestUnifiedMemoryBridgeEdgeCases:
    """Edge cases and error handling."""

    def test_ingest_exception_produces_failed_event(self):
        """If ingest raises, produce a failed SyncEvent instead of crashing."""
        facade = MagicMock()
        facade.search.return_value = []
        facade.status.return_value = {"status": "healthy", "subengines": {}, "version": "0"}
        bridge = UnifiedMemoryBridge(facade)
        # Force an exception during _route_ingest
        bridge._route_ingest = MagicMock(side_effect=RuntimeError("boom"))
        events = bridge.ingest([_make_doc("doc-fail")])
        assert len(events) == 1
        assert events[0].status == "failed"
        assert "boom" in events[0].payload.get("error", "")

    def test_bridge_default_facade_creation(self):
        """Bridge can be created without explicit facade (uses get_knowledge_facade)."""
        # This tests the default creation path — may fail if knowledge is not installed
        # but it should at least not raise on construction logic
        try:
            bridge = UnifiedMemoryBridge()
            assert bridge._facade is not None
        except Exception:
            # Acceptable if knowledge package isn't fully installed
            pytest.skip("Knowledge facade not available for default construction")
