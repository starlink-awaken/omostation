"""KEMS-v2 Knowledge Graph — policy, regulation, ADR, and approval entity management.

Provides an in-memory graph with JSONL persistence for hybrid retrieval.
Designed for <50ms query latency with up to 5000 nodes and 20000 edges.

Entity types:
    Policy — government policy documents (卫生健康政策)
    Regulation — procedural rules and standards (公文规程)
    ADR — architecture decision records
    Approval — historical approved responses (历史批复)

Relationship types:
    cites — entity A references entity B
    supersedes — entity A replaces entity B
    implements — entity A operationalizes entity B
    references — entity A loosely relates to entity B
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Iterator


class EntityType(str, Enum):
    POLICY = "policy"
    REGULATION = "regulation"
    ADR = "adr"
    APPROVAL = "approval"


class RelationType(str, Enum):
    CITES = "cites"
    SUPERSEDES = "supersedes"
    IMPLEMENTS = "implements"
    REFERENCES = "references"


@dataclass
class Entity:
    """A knowledge graph node representing a policy, regulation, ADR, or approval."""

    id: str
    entity_type: EntityType
    title: str
    content: str = ""
    source: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def search_text(self) -> str:
        """Combined text for BM25 indexing."""
        parts = [self.title, self.content, " ".join(self.tags)]
        return " ".join(p for p in parts if p)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["entity_type"] = self.entity_type.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Entity:
        d = dict(d)
        d["entity_type"] = EntityType(d["entity_type"])
        return cls(**d)


@dataclass
class Edge:
    """A directed relationship between two entities."""

    source_id: str
    target_id: str
    relation: RelationType
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["relation"] = self.relation.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Edge:
        d = dict(d)
        d["relation"] = RelationType(d["relation"])
        return cls(**d)


def _tokenize(text: str) -> list[str]:
    """Simple CJK-aware tokenizer for BM25-style text matching.

    Splits on whitespace and punctuation, lowercases Latin chars,
    preserves CJK characters as individual tokens.
    """
    text = unicodedata.normalize("NFKC", text).lower()
    tokens: list[str] = []
    current: list[str] = []
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            if current:
                tokens.append("".join(current))
                current = []
            tokens.append(ch)
        elif ch.isalnum():
            current.append(ch)
        else:
            if current:
                tokens.append("".join(current))
                current = []
    if current:
        tokens.append("".join(current))
    return tokens


class KnowledgeGraph:
    """In-memory knowledge graph with JSONL persistence and text search.

    Supports:
    - Entity CRUD with type/tag filtering
    - Edge CRUD with relation filtering
    - BM25-style token matching for text queries
    - Graph traversal (BFS up to N hops)
    - JSONL save/load for durability
    """

    def __init__(self) -> None:
        self._entities: dict[str, Entity] = {}
        self._edges: list[Edge] = []
        self._outgoing: dict[str, list[Edge]] = defaultdict(list)
        self._incoming: dict[str, list[Edge]] = defaultdict(list)
        # Inverted index: token → set of entity IDs
        self._token_index: dict[str, set[str]] = defaultdict(set)

    # ── Entity operations ──

    def add_entity(self, entity: Entity) -> None:
        """Add or update an entity in the graph."""
        self._entities[entity.id] = entity
        # Update token index
        for token in _tokenize(entity.search_text):
            self._token_index[token].add(entity.id)

    def get_entity(self, entity_id: str) -> Entity | None:
        """Retrieve an entity by ID."""
        return self._entities.get(entity_id)

    def remove_entity(self, entity_id: str) -> bool:
        """Remove an entity and all its edges. Returns True if found."""
        if entity_id not in self._entities:
            return False
        entity = self._entities.pop(entity_id)
        # Remove from token index
        for token in _tokenize(entity.search_text):
            self._token_index.get(token, set()).discard(entity_id)
        # Remove edges
        self._edges = [
            e for e in self._edges
            if e.source_id != entity_id and e.target_id != entity_id
        ]
        self._outgoing.pop(entity_id, None)
        self._incoming.pop(entity_id, None)
        return True

    def list_entities(
        self,
        entity_type: EntityType | None = None,
        tags: list[str] | None = None,
    ) -> list[Entity]:
        """List entities, optionally filtered by type and/or tags."""
        result = list(self._entities.values())
        if entity_type is not None:
            result = [e for e in result if e.entity_type == entity_type]
        if tags:
            tag_set = set(tags)
            result = [e for e in result if tag_set.intersection(e.tags)]
        return result

    # ── Edge operations ──

    def add_edge(self, edge: Edge) -> None:
        """Add a directed edge between two entities.

        Both source and target entities must already exist.
        """
        if edge.source_id not in self._entities:
            raise ValueError(f"source entity not found: {edge.source_id}")
        if edge.target_id not in self._entities:
            raise ValueError(f"target entity not found: {edge.target_id}")
        self._edges.append(edge)
        self._outgoing[edge.source_id].append(edge)
        self._incoming[edge.target_id].append(edge)

    def remove_edge(self, source_id: str, target_id: str, relation: RelationType) -> bool:
        """Remove a specific edge. Returns True if found and removed."""
        for i, e in enumerate(self._edges):
            if e.source_id == source_id and e.target_id == target_id and e.relation == relation:
                removed = self._edges.pop(i)
                self._outgoing.get(removed.source_id, []).remove(removed)
                self._incoming.get(removed.target_id, []).remove(removed)
                return True
        return False

    def get_neighbors(
        self,
        entity_id: str,
        direction: str = "out",
        relation: RelationType | None = None,
    ) -> list[Edge]:
        """Get edges connected to an entity.

        direction: 'out' (outgoing), 'in' (incoming), 'both'
        """
        edges: list[Edge] = []
        if direction in ("out", "both"):
            edges.extend(self._outgoing.get(entity_id, []))
        if direction in ("in", "both"):
            edges.extend(self._incoming.get(entity_id, []))
        if relation is not None:
            edges = [e for e in edges if e.relation == relation]
        return edges

    # ── Text search ──

    def search(self, query: str, top_k: int = 10) -> list[tuple[Entity, float]]:
        """BM25-style text search over entity content.

        Returns (entity, score) pairs sorted by descending relevance.
        Score is the count of matching tokens (simple TF approximation).
        """
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        # Count matches per entity
        scores: dict[str, float] = defaultdict(float)
        for token in query_tokens:
            matching_ids = self._token_index.get(token, set())
            for eid in matching_ids:
                scores[eid] += 1.0

        # Sort by score descending, then by entity ID for stability
        ranked = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
        result: list[tuple[Entity, float]] = []
        for eid, score in ranked[:top_k]:
            entity = self._entities.get(eid)
            if entity is not None:
                result.append((entity, score))
        return result

    # ── Graph traversal ──

    def bfs(
        self,
        start_id: str,
        max_hops: int = 2,
        relation: RelationType | None = None,
    ) -> dict[str, int]:
        """BFS from start_id, returning {entity_id: hop_distance}.

        Useful for finding related entities within N hops.
        """
        if start_id not in self._entities:
            return {}
        visited: dict[str, int] = {start_id: 0}
        frontier = [start_id]
        for hop in range(1, max_hops + 1):
            next_frontier: list[str] = []
            for eid in frontier:
                for edge in self.get_neighbors(eid, direction="out", relation=relation):
                    if edge.target_id not in visited:
                        visited[edge.target_id] = hop
                        next_frontier.append(edge.target_id)
            frontier = next_frontier
        return visited

    def source_chain(self, entity_id: str, max_hops: int = 5) -> list[Entity]:
        """Follow 'cites' and 'supersedes' edges to build a provenance chain.

        Starting from entity_id, follow outgoing cites/supersedes edges
        to find what this entity cites or supersedes. Returns entities
        in citation order (newest → oldest).
        """
        chain: list[Entity] = []
        visited: set[str] = set()
        frontier = [entity_id]
        while frontier and len(chain) < max_hops:
            next_frontier: list[str] = []
            for eid in frontier:
                if eid in visited:
                    continue
                visited.add(eid)
                entity = self._entities.get(eid)
                if entity is not None and eid != entity_id:
                    chain.append(entity)
                for edge in self.get_neighbors(eid, direction="out"):
                    if edge.relation in (RelationType.CITES, RelationType.SUPERSEDES):
                        if edge.target_id not in visited:
                            next_frontier.append(edge.target_id)
            frontier = next_frontier
        return chain

    # ── Stats ──

    def stats(self) -> dict[str, Any]:
        """Graph statistics for health checks and criteria validation."""
        type_counts: dict[str, int] = defaultdict(int)
        for e in self._entities.values():
            type_counts[e.entity_type.value] += 1
        rel_counts: dict[str, int] = defaultdict(int)
        for edge in self._edges:
            rel_counts[edge.relation.value] += 1
        return {
            "total_entities": len(self._entities),
            "total_edges": len(self._edges),
            "entity_types": dict(type_counts),
            "relation_types": dict(rel_counts),
            "avg_out_degree": len(self._edges) / max(len(self._entities), 1),
        }

    # ── Persistence ──

    def save(self, path: str | Path) -> None:
        """Save graph to JSONL (one JSON object per line).

        Format:
        {"_t": "entity", ...entity_dict}
        {"_t": "edge", ...edge_dict}
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for entity in self._entities.values():
                record = {"_t": "entity", **entity.to_dict()}
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            for edge in self._edges:
                record = {"_t": "edge", **edge.to_dict()}
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    @classmethod
    def load(cls, path: str | Path) -> KnowledgeGraph:
        """Load graph from JSONL file."""
        graph = cls()
        path = Path(path)
        if not path.exists():
            return graph
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                t = record.pop("_t", None)
                if t == "entity":
                    graph.add_entity(Entity.from_dict(record))
                elif t == "edge":
                    graph.add_edge(Edge.from_dict(record))
        return graph

    def content_digest(self) -> str:
        """SHA-256 digest of the graph content for change detection."""
        h = hashlib.sha256()
        for entity in sorted(self._entities.values(), key=lambda e: e.id):
            h.update(entity.id.encode())
            h.update(entity.title.encode())
        for edge in sorted(self._edges, key=lambda e: (e.source_id, e.target_id, e.relation.value)):
            h.update(f"{edge.source_id}:{edge.target_id}:{edge.relation.value}".encode())
        return h.hexdigest()
