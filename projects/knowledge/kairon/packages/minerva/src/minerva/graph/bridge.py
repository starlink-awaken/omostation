"""Graphiti + Neo4j bridge — knowledge graph operations for Minerva pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphConfig:
    """Configuration for Neo4j/Graphiti connection."""

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""  # Set via MINERVA_NEO4J_PASSWORD env var or config
    enabled: bool = True


@dataclass
class GraphEntity:
    """An entity in the knowledge graph.

    Can be constructed from minerva.knowledge.store.Entity via from_entity().
    """

    id: str
    name: str
    entity_type: str
    properties: dict = field(default_factory=dict)
    confidence: str = "MEDIUM"

    @classmethod
    def from_kb_entity(cls, entity: Any) -> GraphEntity:
        """Create GraphEntity from minerva.knowledge.store.Entity."""
        return cls(
            id=entity.id,
            name=entity.name,
            entity_type=getattr(entity, "type", "Concept"),
            properties=getattr(entity, "properties", {}),
            confidence=getattr(entity, "confidence", "MEDIUM"),
        )


@dataclass
class GraphRelation:
    """A relation between two entities in the knowledge graph.

    Can be constructed from minerva.knowledge.store.Relation via from_relation().
    """

    source_id: str
    target_id: str
    relation_type: str
    properties: dict = field(default_factory=dict)
    confidence: str = "MEDIUM"

    @classmethod
    def from_relation(cls, relation: Any) -> GraphRelation:
        """Create GraphRelation from minerva.knowledge.store.Relation."""
        return cls(
            source_id=getattr(relation, "subject_id", ""),
            target_id=getattr(relation, "object_id", ""),
            relation_type=getattr(relation, "predicate", "RELATES"),
            properties=getattr(relation, "properties", {}),
            confidence=getattr(relation, "confidence", "MEDIUM"),
        )


class GraphBridge:
    """Bridge between Minerva and Neo4j knowledge graph.

    Provides a simplified interface over Graphiti or direct Neo4j driver
    for knowledge graph operations during research.

    Tier-2 dependency: degrades gracefully when Neo4j is unavailable.
    """

    def __init__(self, config: GraphConfig | None = None) -> None:
        self.config = config or GraphConfig()
        self._driver = None
        self._connected = False

    async def connect(self) -> bool:
        """Connect to Neo4j. Returns True if connected."""
        if not self.config.enabled:
            return False
        try:
            from neo4j import AsyncGraphDatabase  # type: ignore[reportMissingImports]

            self._driver = AsyncGraphDatabase.driver(
                self.config.neo4j_uri,
                auth=(self.config.neo4j_user, self.config.neo4j_password),
            )
            assert self._driver is not None
            await self._driver.verify_connectivity()
            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Close the Neo4j connection."""
        if self._driver:
            await self._driver.close()
            self._connected = False

    async def upsert_entity(self, entity: GraphEntity) -> bool:
        """Upsert an entity into the knowledge graph."""
        if not self._connected or not self._driver:
            return False
        try:
            async with self._driver.session() as session:
                await session.run(
                    """
                    MERGE (e:Entity {id: $id})
                    SET e.name = $name,
                        e.type = $type,
                        e.confidence = $confidence
                    SET e += $properties
                    SET e.updated_at = datetime()
                    """,
                    id=entity.id,
                    name=entity.name,
                    type=entity.entity_type,
                    confidence=entity.confidence,
                    properties=entity.properties,
                )
            return True
        except Exception:
            return False

    async def upsert_relation(self, rel: GraphRelation) -> bool:
        """Upsert a relation between two entities."""
        if not self._connected or not self._driver:
            return False
        try:
            async with self._driver.session() as session:
                await session.run(
                    """
                    MATCH (a:Entity {id: $source_id})
                    MATCH (b:Entity {id: $target_id})
                    MERGE (a)-[r:RELATES {type: $rel_type}]->(b)
                    SET r.confidence = $confidence
                    SET r += $properties
                    SET r.updated_at = datetime()
                    """,
                    source_id=rel.source_id,
                    target_id=rel.target_id,
                    rel_type=rel.relation_type,
                    confidence=rel.confidence,
                    properties=rel.properties,
                )
            return True
        except Exception:
            return False

    async def search_entities(self, query: str, limit: int = 10) -> list[dict]:
        """Search entities by name or type."""
        if not self._connected or not self._driver:
            return []
        try:
            async with self._driver.session() as session:
                result = await session.run(
                    """
                    MATCH (e:Entity)
                    WHERE e.name CONTAINS $query OR e.type CONTAINS $query
                    RETURN e.id, e.name, e.type, e.confidence
                    LIMIT $limit
                    """,
                    query=query,
                    limit=limit,
                )
                records = await result.data()
                return [
                    {
                        "id": r["e.id"],
                        "name": r["e.name"],
                        "type": r["e.type"],
                        "confidence": r["e.confidence"],
                    }
                    for r in records
                ]
        except Exception:
            return []

    async def find_relations(self, entity_id: str, depth: int = 1) -> list[dict]:
        """Find relations connected to an entity."""
        if not self._connected or not self._driver:
            return []
        try:
            async with self._driver.session() as session:
                result = await session.run(
                    """
                    MATCH (a:Entity {id: $id})-[r]-(b:Entity)
                    RETURN a.name, type(r) as rel_type, r.confidence, b.name, b.id
                    LIMIT 50
                    """,
                    id=entity_id,
                )
                records = await result.data()
                return [
                    {
                        "source": r["a.name"],
                        "relation": r["rel_type"],
                        "confidence": r["r.confidence"],
                        "target": r["b.name"],
                        "target_id": r["b.id"],
                    }
                    for r in records
                ]
        except Exception:
            return []

    async def sync_from_research(self, entities: list[dict], relations: list[dict]) -> dict:
        """Sync research pipeline output into the knowledge graph.

        Returns counts of entities and relations synced.
        """
        entity_count = 0
        relation_count = 0

        for e in entities:
            ge = GraphEntity(
                id=e.get("id", e.get("name", "")),
                name=e.get("name", ""),
                entity_type=e.get("type", "Concept"),
                confidence=e.get("confidence", "MEDIUM"),
            )
            if await self.upsert_entity(ge):
                entity_count += 1

        for r in relations:
            gr = GraphRelation(
                source_id=r.get("source_id", ""),
                target_id=r.get("target_id", ""),
                relation_type=r.get("relation_type", "RELATES"),
                confidence=r.get("confidence", "MEDIUM"),
            )
            if await self.upsert_relation(gr):
                relation_count += 1

        return {"entities_synced": entity_count, "relations_synced": relation_count}

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def sync_code_graph(self, repo_path: str = ".") -> dict:
        """Build code knowledge graph via graphify and sync to Neo4j/SQLite.

        Uses graphify Python API to analyze a code repository, then upserts
        extracted entities and relations into the knowledge graph.
        Falls back gracefully if graphify is not installed.
        """
        try:
            from minerva.graph.graphify_adapter import build_code_graph

            graph = build_code_graph(repo_path)
        except Exception:
            return {"entities_synced": 0, "relations_synced": 0, "error": "graphify unavailable"}

        entities = graph.get("entities", [])
        relations = graph.get("relations", [])
        if not entities:
            return {"entities_synced": 0, "relations_synced": 0}

        entity_count = 0
        for e in entities:
            ge = GraphEntity(
                id=e.get("id", e.get("name", "")),
                name=e.get("name", ""),
                entity_type=e.get("type", "Module"),
                properties=e.get("properties", {}),
            )
            if await self.upsert_entity(ge):
                entity_count += 1

        relation_count = 0
        for r in relations:
            gr = GraphRelation(
                source_id=r.get("source_id", ""),
                target_id=r.get("target_id", ""),
                relation_type=r.get("relation_type", "IMPORTS"),
            )
            if await self.upsert_relation(gr):
                relation_count += 1

        return {"entities_synced": entity_count, "relations_synced": relation_count}
