"""decay_manager.py — 跨生命周期记忆衰减与冲突消除引擎 (BET-Y2Q1-T6-01)

建立 MOS 记忆全生命周期管理：基于时间戳与权威更新动态衰减旧版规章制度，
自动消除记忆图谱中的语义冲突与陈旧过时事实。

Core capabilities:
    1. Time-decay scoring — recency factor based on entity updated_at / created_at
    2. Authority override — when superseded edges exist, mark old entity deprecated
    3. Conflict detection — find A→B vs A→¬B type semantic conflicts
    4. Idempotent re-runs — safe to call multiple times, no side effects beyond metadata mutation

Half-life default: 180 days (6 months).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from kairon.graph.kems_v2 import (
    Edge,
    Entity,
    KnowledgeGraph,
    RelationType,
)

HALF_LIFE_DAYS = 180
DEPRECATED_STATUS = "deprecated"
CONFLICT_MARKER = "conflict_with"

# Conflicting relation pairs: if source→target has both in outgoing edges,
# the one with the earlier timestamp (or lower authority) is the conflict loser.
_CONFLICT_PAIRS: frozenset[tuple[str, str]] = frozenset(
    {
        ("cites", "supersedes"),
    }
)


@dataclass
class DecayReport:
    """Result of a full decay scan."""

    total_entities: int = 0
    total_edges: int = 0
    deprecated_count: int = 0
    conflict_count: int = 0
    deprecated_entities: list[str] = field(default_factory=list)
    conflict_details: list[dict[str, Any]] = field(default_factory=list)
    low_score_entities: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_entities": self.total_entities,
            "total_edges": self.total_edges,
            "deprecated_count": self.deprecated_count,
            "conflict_count": self.conflict_count,
            "deprecated_entities": self.deprecated_entities,
            "conflict_details": self.conflict_details,
            "low_score_entities": self.low_score_entities,
        }

    def has_critical_conflicts(self) -> bool:
        """True if there are un-resolved conflicts (幻觉事实风险)."""
        return self.conflict_count > 0


def _parse_timestamp(value: Any) -> datetime | None:
    """Parse a timestamp from metadata, supporting ISO 8601 and epoch seconds."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    return None


def _entity_timestamp(entity: Entity) -> datetime | None:
    """Extract the most relevant timestamp from an entity's metadata.

    Priority: updated_at > created_at.
    """
    ts = _parse_timestamp(entity.metadata.get("updated_at"))
    if ts is not None:
        return ts
    return _parse_timestamp(entity.metadata.get("created_at"))


def _edge_timestamp(edge: Edge) -> datetime | None:
    """Extract the most relevant timestamp from an edge's metadata."""
    ts = _parse_timestamp(edge.metadata.get("updated_at"))
    if ts is not None:
        return ts
    return _parse_timestamp(edge.metadata.get("created_at"))


def compute_recency_score(
    timestamp: datetime | None,
    now: datetime | None = None,
    half_life_days: float = HALF_LIFE_DAYS,
) -> float:
    """Compute a recency score between 0.1 and 1.0.

    Formula: max(0.1, 1.0 - (days_since_update / half_life_days))
    """
    if now is None:
        now = datetime.now(tz=timezone.utc)
    if timestamp is None:
        return 0.1  # No timestamp = lowest score
    days_elapsed = max(0.0, (now - timestamp).total_seconds() / 86400.0)
    return max(0.1, 1.0 - days_elapsed / half_life_days)


class DecayManager:
    """Memory decay and conflict elimination engine.

    Operates on a KnowledgeGraph instance. All methods are idempotent.
    """

    def __init__(
        self,
        graph: KnowledgeGraph,
        half_life_days: float = HALF_LIFE_DAYS,
        now: datetime | None = None,
    ) -> None:
        self._graph = graph
        self._half_life_days = half_life_days
        self._now = now or datetime.now(tz=timezone.utc)

    # ── Score ──

    def score_entity(self, entity: Entity) -> float:
        """Compute the recency score for a single entity."""
        ts = _entity_timestamp(entity)
        return compute_recency_score(ts, self._now, self._half_life_days)

    # ── Deprecation ──

    def mark_deprecated(self, entity: Entity) -> bool:
        """Mark an entity as deprecated. Returns True if state changed."""
        current = entity.metadata.get("status")
        if current == DEPRECATED_STATUS:
            return False  # Already deprecated — idempotent
        entity.metadata["status"] = DEPRECATED_STATUS
        entity.metadata["deprecated_at"] = self._now.isoformat()
        return True

    def find_superseded_entities(self) -> list[Entity]:
        """Find entities that have been superseded by newer ones via supersedes edges.

        When edge A→B with relation SUPERSEDES means "A supersedes B",
        entity B (the target) is the one that's been superseded and should be deprecated.
        """
        superseded: list[Entity] = []
        seen: set[str] = set()
        # Access internal edge list (KnowledgeGraph has no public edges iterator)
        for edge in self._graph._edges:
            if edge.relation == RelationType.SUPERSEDES:
                # The TARGET is the superseded entity (the one being replaced)
                superseded_entity = self._graph.get_entity(edge.target_id)
                if superseded_entity is not None and superseded_entity.id not in seen:
                    score = self.score_entity(superseded_entity)
                    if score < 0.5:
                        superseded.append(superseded_entity)
                        seen.add(superseded_entity.id)
        return superseded

    # ── Conflict Detection ──

    def detect_conflicts(self) -> list[dict[str, Any]]:
        """Detect semantic conflicts in the knowledge graph.

        Conflict: same source entity has edges to the same target with
        conflicting relations (e.g., cites + supersedes to the same target).
        """
        conflicts: list[dict[str, Any]] = []
        # Build edge index: (source_id, target_id) → list[Edge]
        edge_pairs: dict[tuple[str, str], list[Edge]] = {}
        # Access internal edge list (KnowledgeGraph has no public edges iterator)
        for edge in self._graph._edges:
            key = (edge.source_id, edge.target_id)
            edge_pairs.setdefault(key, []).append(edge)

        for (src_id, tgt_id), edges in edge_pairs.items():
            if len(edges) < 2:
                continue
            relations = {e.relation.value for e in edges}
            for pair in _CONFLICT_PAIRS:
                if pair[0] in relations and pair[1] in relations:
                    # Find the older edge (conflict loser)
                    timestamps = [
                        (_edge_timestamp(e), e) for e in edges if e.relation.value in pair
                    ]
                    timestamps.sort(key=lambda x: x[0] or self._now)
                    loser_edge = timestamps[0][1]
                    conflicts.append(
                        {
                            "source_id": src_id,
                            "target_id": tgt_id,
                            "conflicting_relations": list(pair),
                            "loser_edge_relation": loser_edge.relation.value,
                            "detail": (
                                f"Entity {src_id} → {tgt_id}: "
                                f"{pair[0]} vs {pair[1]} conflict"
                            ),
                        }
                    )
        return conflicts

    # ── Full Scan ──

    def run_decay_scan(self) -> DecayReport:
        """Run a complete decay scan: score, deprecate, detect conflicts.

        Returns a DecayReport with full diagnostics.
        """
        report = DecayReport()
        # Access internal data (KnowledgeGraph has no public entities/edges iterator)
        entities = list(self._graph._entities.values())
        report.total_entities = len(entities)
        report.total_edges = len(self._graph._edges)

        # 1. Score all entities
        for entity in entities:
            score = self.score_entity(entity)
            if score < 0.5:
                report.low_score_entities.append(
                    {
                        "id": entity.id,
                        "title": entity.title,
                        "score": round(score, 4),
                        "updated_at": entity.metadata.get("updated_at"),
                    }
                )

        # 2. Deprecate superseded entities
        superseded = self.find_superseded_entities()
        for entity in superseded:
            changed = self.mark_deprecated(entity)
            if changed:
                report.deprecated_count += 1
                report.deprecated_entities.append(entity.id)

        # 3. Detect conflicts
        conflicts = self.detect_conflicts()
        report.conflict_count = len(conflicts)
        report.conflict_details = conflicts

        return report


def run_check_decay(
    graph: KnowledgeGraph | None = None,
    graph_path: str | None = None,
    half_life_days: float = HALF_LIFE_DAYS,
) -> DecayReport:
    """CLI-friendly entry point: load graph, run decay scan, return report.

    If graph is None, attempts to load from graph_path (JSONL).
    """
    if graph is None:
        if graph_path is None:
            raise ValueError("Either graph or graph_path must be provided")
        graph = KnowledgeGraph.load(graph_path)
    manager = DecayManager(graph, half_life_days=half_life_days)
    return manager.run_decay_scan()


def format_report(report: DecayReport) -> str:
    """Format a DecayReport as human-readable output."""
    lines: list[str] = []
    lines.append(f"[DECAY] Total entities: {report.total_entities}")
    lines.append(f"[DECAY] Total edges: {report.total_edges}")
    lines.append(f"[DECAY] Low-score entities (<0.5): {len(report.low_score_entities)}")
    for item in report.low_score_entities:
        lines.append(f"  - {item['id']} ({item['title']}): score={item['score']}")
    lines.append(f"[DECAY] Deprecated entities: {report.deprecated_count}")
    for eid in report.deprecated_entities:
        lines.append(f"  - {eid}")
    lines.append(f"[DECAY] Conflicts: {report.conflict_count}")
    for c in report.conflict_details:
        lines.append(f"  - {c['detail']}")
    if not report.deprecated_entities and not report.conflict_details:
        lines.append("[DECAY] ✅ No deprecations or conflicts detected")
    return "\n".join(lines)
