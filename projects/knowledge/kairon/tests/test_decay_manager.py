"""Tests for decay_manager.py — BET-Y2Q1-T6-01.

Covers:
    - Recency score computation
    - Entity deprecation (idempotent)
    - Superseded entity detection
    - Conflict detection (cites vs supersedes)
    - Full decay scan report
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from kairon.graph.decay_manager import (
    DecayManager,
    DecayReport,
    compute_recency_score,
    format_report,
)
from kairon.graph.kems_v2 import (
    Edge,
    Entity,
    EntityType,
    KnowledgeGraph,
    RelationType,
)

NOW = datetime(2026, 9, 7, tzinfo=timezone.utc)


# ── Fixtures ──


def _make_entity(
    eid: str,
    title: str = "Test Entity",
    entity_type: EntityType = EntityType.POLICY,
    updated_at: str | None = None,
    created_at: str | None = None,
    status: str | None = None,
) -> Entity:
    metadata: dict = {}
    if updated_at:
        metadata["updated_at"] = updated_at
    if created_at:
        metadata["created_at"] = created_at
    if status:
        metadata["status"] = status
    return Entity(id=eid, entity_type=entity_type, title=title, metadata=metadata)


def _make_edge(
    source_id: str,
    target_id: str,
    relation: RelationType = RelationType.CITES,
    updated_at: str | None = None,
) -> Edge:
    metadata: dict = {}
    if updated_at:
        metadata["updated_at"] = updated_at
    return Edge(source_id=source_id, target_id=target_id, relation=relation, metadata=metadata)


def _empty_graph() -> KnowledgeGraph:
    return KnowledgeGraph()


# ── Tests: compute_recency_score ──


class TestRecencyScore:
    def test_recent_entity_scores_high(self):
        ts = NOW - timedelta(days=10)
        score = compute_recency_score(ts, NOW, half_life_days=180)
        assert score > 0.9

    def test_old_entity_scores_low(self):
        ts = NOW - timedelta(days=365)
        score = compute_recency_score(ts, NOW, half_life_days=180)
        assert score <= 0.1  # clamped to 0.1

    def test_half_life_at_boundary(self):
        ts = NOW - timedelta(days=180)
        score = compute_recency_score(ts, NOW, half_life_days=180)
        # At exactly half-life: 1.0 - 180/180 = 0.0, clamped to 0.1
        assert score == 0.1

    def test_none_timestamp_returns_minimum(self):
        score = compute_recency_score(None, NOW, half_life_days=180)
        assert score == 0.1


# ── Tests: DecayManager.deprecation ──


class TestDeprecation:
    def test_mark_deprecated_sets_status(self):
        entity = _make_entity("e1", updated_at="2026-01-01T00:00:00+00:00")
        dm = DecayManager(_empty_graph(), now=NOW)
        changed = dm.mark_deprecated(entity)
        assert changed is True
        assert entity.metadata["status"] == "deprecated"
        assert "deprecated_at" in entity.metadata

    def test_mark_deprecated_is_idempotent(self):
        entity = _make_entity("e1", status="deprecated", updated_at="2026-01-01T00:00:00+00:00")
        dm = DecayManager(_empty_graph(), now=NOW)
        changed = dm.mark_deprecated(entity)
        assert changed is False
        assert entity.metadata["status"] == "deprecated"


# ── Tests: find_superseded_entities ──


class TestSupersededDetection:
    def test_finds_superseded_low_score_entity(self):
        g = _empty_graph()
        old = _make_entity("old", title="旧办法", updated_at="2025-06-01T00:00:00+00:00")
        new = _make_entity("new", title="新实施细则", updated_at="2026-08-01T00:00:00+00:00")
        g.add_entity(old)
        g.add_entity(new)
        g.add_edge(Edge(source_id="new", target_id="old", relation=RelationType.SUPERSEDES))
        dm = DecayManager(g, now=NOW)
        superseded = dm.find_superseded_entities()
        assert len(superseded) == 1
        assert superseded[0].id == "old"

    def test_no_superseded_for_recent_entity(self):
        g = _empty_graph()
        recent = _make_entity("recent", title="Recent", updated_at="2026-09-01T00:00:00+00:00")
        other = _make_entity("other", title="Other", updated_at="2026-08-01T00:00:00+00:00")
        g.add_entity(recent)
        g.add_entity(other)
        g.add_edge(Edge(source_id="other", target_id="recent", relation=RelationType.SUPERSEDES))
        dm = DecayManager(g, now=NOW)
        superseded = dm.find_superseded_entities()
        # recent entity has score > 0.5, should NOT be superseded
        assert len(superseded) == 0


# ── Tests: conflict detection ──


class TestConflictDetection:
    def test_detects_cites_vs_supersedes_conflict(self):
        g = _empty_graph()
        src = _make_entity("src")
        tgt = _make_entity("tgt")
        g.add_entity(src)
        g.add_entity(tgt)
        # Two conflicting edges from src to tgt
        g.add_edge(_make_edge("src", "tgt", RelationType.CITES, updated_at="2026-01-01T00:00:00+00:00"))
        g.add_edge(_make_edge("src", "tgt", RelationType.SUPERSEDES, updated_at="2026-06-01T00:00:00+00:00"))
        dm = DecayManager(g, now=NOW)
        conflicts = dm.detect_conflicts()
        assert len(conflicts) == 1
        assert conflicts[0]["loser_edge_relation"] == "cites"

    def test_no_conflict_for_same_relation(self):
        g = _empty_graph()
        src = _make_entity("src")
        tgt = _make_entity("tgt")
        g.add_entity(src)
        g.add_entity(tgt)
        g.add_edge(_make_edge("src", "tgt", RelationType.CITES))
        g.add_edge(_make_edge("src", "tgt", RelationType.CITES))
        dm = DecayManager(g, now=NOW)
        conflicts = dm.detect_conflicts()
        # cites vs cites is NOT a conflicting pair
        assert len(conflicts) == 0

    def test_no_conflict_for_single_edge(self):
        g = _empty_graph()
        src = _make_entity("src")
        tgt = _make_entity("tgt")
        g.add_entity(src)
        g.add_entity(tgt)
        g.add_edge(_make_edge("src", "tgt", RelationType.CITES))
        dm = DecayManager(g, now=NOW)
        conflicts = dm.detect_conflicts()
        assert len(conflicts) == 0


# ── Tests: full decay scan ──


class TestDecayScan:
    def test_scan_empty_graph(self):
        dm = DecayManager(_empty_graph(), now=NOW)
        report = dm.run_decay_scan()
        assert report.total_entities == 0
        assert report.deprecated_count == 0
        assert report.conflict_count == 0

    def test_scan_with_superseded_and_conflict(self):
        g = _empty_graph()
        old = _make_entity("old", title="旧办法", updated_at="2025-01-01T00:00:00+00:00")
        new = _make_entity("new", title="新实施细则", updated_at="2026-08-01T00:00:00+00:00")
        g.add_entity(old)
        g.add_entity(new)
        g.add_edge(Edge(source_id="new", target_id="old", relation=RelationType.SUPERSEDES))
        dm = DecayManager(g, now=NOW)
        report = dm.run_decay_scan()
        assert report.deprecated_count == 1
        assert "old" in report.deprecated_entities
        # old entity should now have status=deprecated
        assert g.get_entity("old").metadata["status"] == "deprecated"

    def test_report_has_critical_conflicts(self):
        report = DecayReport(conflict_count=1)
        assert report.has_critical_conflicts() is True
        report2 = DecayReport(conflict_count=0)
        assert report2.has_critical_conflicts() is False


# ── Tests: format_report ──


class TestFormatReport:
    def test_format_empty_report(self):
        report = DecayReport(total_entities=5, total_edges=10)
        text = format_report(report)
        assert "[DECAY] Total entities: 5" in text
        assert "[DECAY] ✅ No deprecations or conflicts detected" in text

    def test_format_with_deprecations(self):
        report = DecayReport(
            total_entities=3,
            deprecated_count=1,
            deprecated_entities=["old"],
        )
        text = format_report(report)
        assert "[DECAY] Deprecated entities: 1" in text
        assert "old" in text


# ── Tests: round-trip serialization ──


class TestRoundTrip:
    def test_decay_survives_jsonl_roundtrip(self):
        g = _empty_graph()
        old = _make_entity("old", title="旧办法", updated_at="2025-01-01T00:00:00+00:00")
        new = _make_entity("new", title="新实施细则", updated_at="2026-08-01T00:00:00+00:00")
        g.add_entity(old)
        g.add_entity(new)
        g.add_edge(Edge(source_id="new", target_id="old", relation=RelationType.SUPERSEDES))

        # Run decay
        dm = DecayManager(g, now=NOW)
        dm.run_decay_scan()
        assert g.get_entity("old").metadata["status"] == "deprecated"

        # Save and reload
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            tmppath = f.name
        try:
            g.save(tmppath)
            g2 = KnowledgeGraph.load(tmppath)
            assert g2.get_entity("old").metadata["status"] == "deprecated"
        finally:
            os.unlink(tmppath)
