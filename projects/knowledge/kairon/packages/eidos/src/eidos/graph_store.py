"""Graph store — entity and relation data models for NKS pipeline.

Provides graph storage backend with basic CRUD operations.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from eidos.organs.storage_dal import SQLiteRelationalProvider


@dataclass
class CandidateEntity:
    """A candidate entity extracted during NKS pipeline processing."""

    entity_id: str
    name: str
    properties: dict = field(default_factory=dict)
    source_file: str = ""
    embedding: list[float] | None = None


@dataclass
class CandidateRelation:
    """A candidate relation extracted during NKS pipeline processing."""

    source_id: str
    target_id: str
    relation_type: str
    properties: dict = field(default_factory=dict)
    source_file: str = ""
    weight: float = 1.0
    confidence: float = 1.0


@dataclass
class Entity:
    """A knowledge graph entity."""

    id: str
    name: str = ""
    entity_type: str = ""
    properties: dict[str, Any] = field(default_factory=dict)
    source_files: list[str] = field(default_factory=list)
    merged_from: list[str] = field(default_factory=list)
    created_at: str = ""
    confidence: float = 1.0
    timestamp: str = ""
    entity_id: str = ""
    is_canonical: bool = True

    def __post_init__(self) -> None:
        if self.entity_id and not self.id:
            self.id = self.entity_id
        elif self.id and not self.entity_id:
            self.entity_id = self.id


@dataclass
class Relation:
    """A knowledge graph relation."""

    id: str
    source_id: str = ""
    target_id: str = ""
    relation_type: str = ""
    properties: dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0
    source_files: list[str] = field(default_factory=list)
    confidence: float = 1.0
    relation_id: str = ""
    merged_from: list[str] = field(default_factory=list)
    created_at: str = ""
    is_canonical: bool = True

    def __post_init__(self) -> None:
        if self.relation_id and not self.id:
            self.id = self.relation_id
        elif self.id and not self.relation_id:
            self.relation_id = self.id


class GraphStore:
    """Graph store — SQLite-backed entity/relation storage (真实现 MVP).

    复用 SQLiteRelationalProvider (organs/storage_dal) 的 entities/relations 表.
    Entity/Relation 的扩展字段 (source_files/merged_from/confidence/entity_id/
    is_canonical/timestamp) 序列化到 properties JSON 列.
    """

    def __init__(self, db_path: str = "") -> None:
        self.db_path = db_path or ":memory:"
        self._db = SQLiteRelationalProvider(self.db_path)

    # --- Entity CRUD ---

    def add_entity(self, entity: Entity) -> None:
        """Insert or replace an entity (by id)."""
        self._db.execute(
            "INSERT OR REPLACE INTO entities (id, name, entity_type, properties, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                entity.id,
                entity.name,
                entity.entity_type,
                json.dumps(
                    {
                        "properties": entity.properties,
                        "source_files": entity.source_files,
                        "merged_from": entity.merged_from,
                        "confidence": entity.confidence,
                        "timestamp": entity.timestamp,
                        "entity_id": entity.entity_id,
                        "is_canonical": entity.is_canonical,
                    }
                ),
                entity.created_at,
            ),
        )

    def get_entity(self, entity_id: str) -> Entity | None:
        """Get an entity by ID."""
        row = self._db.fetch_one(
            "SELECT id, name, entity_type, properties, created_at FROM entities WHERE id = ?", (entity_id,)
        )
        return self._row_to_entity(row) if row else None

    def search_entities(self, limit: int = 100, name_pattern: str | None = None) -> list[Entity]:
        """Search entities by name pattern (LIKE), or list all."""
        if name_pattern:
            rows = self._db.fetch_all(
                "SELECT id, name, entity_type, properties, created_at FROM entities WHERE name LIKE ? LIMIT ?",
                (f"%{name_pattern}%", limit),
            )
        else:
            rows = self._db.fetch_all(
                "SELECT id, name, entity_type, properties, created_at FROM entities LIMIT ?", (limit,)
            )
        return [self._row_to_entity(r) for r in rows]

    @staticmethod
    def _row_to_entity(row: Any) -> Entity:
        props = json.loads(row[3]) if row[3] else {}
        return Entity(
            id=row[0],
            name=row[1],
            entity_type=row[2],
            created_at=row[4] or "",
            properties=props.get("properties", {}),
            source_files=props.get("source_files", []),
            merged_from=props.get("merged_from", []),
            confidence=props.get("confidence", 1.0),
            timestamp=props.get("timestamp", ""),
            entity_id=props.get("entity_id", ""),
            is_canonical=props.get("is_canonical", True),
        )

    # --- Relation CRUD ---

    def add_relation(self, relation: Relation) -> None:
        """Insert or replace a relation (by id)."""
        self._db.execute(
            "INSERT OR REPLACE INTO relations (id, source_id, target_id, relation_type, weight, properties, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                relation.id,
                relation.source_id,
                relation.target_id,
                relation.relation_type,
                relation.weight,
                json.dumps(
                    {
                        "properties": relation.properties,
                        "source_files": relation.source_files,
                        "confidence": relation.confidence,
                        "relation_id": relation.relation_id,
                        "merged_from": relation.merged_from,
                        "is_canonical": relation.is_canonical,
                    }
                ),
                relation.created_at,
            ),
        )

    def get_relation(self, relation_id: str) -> Relation | None:
        """Get a relation by ID."""
        row = self._db.fetch_one(
            "SELECT id, source_id, target_id, relation_type, weight, properties, created_at FROM relations WHERE id = ?",
            (relation_id,),
        )
        return self._row_to_relation(row) if row else None

    def get_relations_for_entity(self, entity_id: str, direction: str | None = None) -> list[Relation]:
        """Get relations where entity is source and/or target."""
        if direction == "out":
            rows = self._db.fetch_all(
                "SELECT id, source_id, target_id, relation_type, weight, properties, created_at FROM relations WHERE source_id = ?",
                (entity_id,),
            )
        elif direction == "in":
            rows = self._db.fetch_all(
                "SELECT id, source_id, target_id, relation_type, weight, properties, created_at FROM relations WHERE target_id = ?",
                (entity_id,),
            )
        else:
            rows = self._db.fetch_all(
                "SELECT id, source_id, target_id, relation_type, weight, properties, created_at FROM relations WHERE source_id = ? OR target_id = ?",
                (entity_id, entity_id),
            )
        return [self._row_to_relation(r) for r in rows]

    @staticmethod
    def _row_to_relation(row: Any) -> Relation:
        props = json.loads(row[5]) if row[5] else {}
        return Relation(
            id=row[0],
            source_id=row[1],
            target_id=row[2],
            relation_type=row[3],
            weight=row[4],
            created_at=row[6] or "",
            properties=props.get("properties", {}),
            source_files=props.get("source_files", []),
            confidence=props.get("confidence", 1.0),
            relation_id=props.get("relation_id", ""),
            merged_from=props.get("merged_from", []),
            is_canonical=props.get("is_canonical", True),
        )

    # --- Generic query / health ---

    def query(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        """Generic query — return entities as dicts."""
        rows = self._db.fetch_all("SELECT id, name, entity_type, properties, created_at FROM entities")
        return [
            {
                "id": r[0],
                "name": r[1],
                "entity_type": r[2],
                "properties": json.loads(r[3]) if r[3] else {},
                "created_at": r[4],
            }
            for r in rows
        ]

    def ping(self) -> bool:
        """Check if the graph store is reachable."""
        try:
            self._db.fetch_one("SELECT 1")
            return True
        except Exception:
            return False

    def clear_candidates(self, source_file: str = "") -> None:
        """Clear candidate entities/relations (stub)."""

    def add_candidate_entity(self, entity: Any) -> None:
        """Add a candidate entity (stub)."""

    def add_candidate_relation(self, relation: Any) -> None:
        """Add a candidate relation (stub)."""

    def get_candidate_entities(self, *args: Any, **kwargs: Any) -> list[Any]:
        """Get candidate entities (stub)."""
        return []

    def get_candidate_relations(self, *args: Any, **kwargs: Any) -> list[Any]:
        """Get candidate relations (stub)."""
        return []

    def _get_connection(self) -> None:
        """Get DB connection (stub)."""
        return None


__all__ = [
    "CandidateEntity",
    "CandidateRelation",
    "Entity",
    "Relation",
    "GraphStore",
]
