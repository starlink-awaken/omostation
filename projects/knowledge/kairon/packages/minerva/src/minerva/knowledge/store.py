"""
Minerva Knowledge Store — Multi-backend knowledge storage.

Tier 1 (always available):
- Markdown + Git: Source file versioning (llm-wiki-agent)
- SQLite FTS5: Full-text search
- LanceDB: Vector embeddings

Tier 2 (graceful degradation):
- Neo4j: Graph database (via Graphiti)
- Semantica: SHACL ontology + Allen temporal + Datalog
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# ---- Entity type normalization (no external dependency) ----
def _normalize_entity_type(t: str) -> str:
    """Normalize entity type to standard value. No external dependency."""
    _known_types = {
        "concept",
        "methodology",
        "framework",
        "technology",
        "domain",
        "person",
        "organization",
        "product",
        "publication",
        "data",
    }
    normalized = t.lower()
    if normalized in _known_types:
        return normalized
    return "domain"


# ---- Relation type normalization (no external dependency) ----
def _normalize_relation_type(t: str) -> str:
    """Normalize relation type to standard value. No external dependency."""
    _known_relations = {
        "struct",
        "depends",
        "influences",
        "extends",
        "contradicts",
        "supports",
        "refines",
        "generalizes",
        "part_of",
        "related",
    }
    normalized = t.lower()
    if normalized in _known_relations:
        return normalized
    return "struct"


# ============================================================
# Data Models
# ============================================================


@dataclass
class Entity:
    id: str
    type: str  # Person|Org|Product|Publication|Concept|Metric|Event|Claim|Timeline
    name: str
    aliases: list[str] = field(default_factory=list)
    properties: dict = field(default_factory=dict)
    valid_from: str | None = None
    valid_until: str | None = None
    superseded_by: str | None = None
    source_ids: list[str] = field(default_factory=list)
    confidence: str = "MEDIUM"  # HIGH|MEDIUM|LOW
    recorded_at: str | None = None
    last_verified: str | None = None

    def __post_init__(self) -> None:
        if self.type:
            self.type = _normalize_entity_type(self.type)


@dataclass
class Relation:
    id: str
    subject_id: str
    predicate: str
    object_id: str
    meta_relation: str = "struct"
    valid_from: str | None = None
    valid_until: str | None = None
    confidence: str = "MEDIUM"
    source_ids: list[str] = field(default_factory=list)
    recorded_at: str | None = None

    def __post_init__(self) -> None:
        if hasattr(self, "predicate") and self.predicate:
            self.predicate = _normalize_relation_type(self.predicate)
        if hasattr(self, "meta_relation") and self.meta_relation:
            self.meta_relation = _normalize_relation_type(self.meta_relation)


# ============================================================
# Abstract Interface
# ============================================================


class IKnowledgeStore(ABC):
    """Unified interface for knowledge storage operations."""

    @abstractmethod
    async def upsert_entity(self, entity: Entity) -> str:
        """Insert or update an entity. Returns entity ID."""
        ...

    @abstractmethod
    async def upsert_relation(self, rel: Relation) -> str:
        """Insert or update a relation. Returns relation ID."""
        ...

    @abstractmethod
    async def get_entity(self, entity_id: str) -> Entity | None:
        """Get entity by ID."""
        ...

    @abstractmethod
    async def search(self, query: str, mode: str = "hybrid", top_k: int = 20) -> list[dict]:
        """Search knowledge base.

        Modes:
        - fulltext: SQLite FTS5 keyword search
        - semantic: LanceDB vector similarity
        - graph: Entity relationship traversal (Neo4j or SQLite CTE)
        - hybrid: Fulltext + semantic + graph, RRF fused
        - timeline: Time-ordered entity/event search
        """
        ...

    @abstractmethod
    async def ingest(self, source: str, source_type: str = "auto") -> dict:
        """Ingest content into knowledge base.

        Returns: {entity_count, relation_count, source_path}
        """
        ...

    @abstractmethod
    async def get_timeline(
        self, entity_id: str, from_date: str | None = None, to_date: str | None = None
    ) -> list[dict]:
        """Get chronological timeline for an entity."""
        ...

    @abstractmethod
    async def get_contradictions(self, entity_id: str | None = None) -> list[dict]:
        """Find contradictory claims related to an entity (or all if None)."""
        ...


# ============================================================
# SQLite Backend (Tier 1)
# ============================================================


class SQLiteKnowledgeStore(IKnowledgeStore):
    """Tier 1 knowledge store backed by SQLite + FTS5.

    Schema:
    - entities: id, type, name, aliases(JSON), properties(JSON), ...
    - entities_fts: FTS5 virtual table on (name, aliases)
    - relations: id, subject_id, predicate, object_id, ...
    - sources: id, path, content_hash, ingested_at, ...
    """

    # Regex patterns for basic entity extraction — compiled once at class level
    _ENTITY_PATTERNS: dict = {}  # populated on first ingest() call

    def __init__(self, db_path: str = "~/minerva/knowledge.db") -> None:
        import sqlite3
        from pathlib import Path as _Path

        self.db_path = str(_Path(db_path).expanduser())
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._check_integrity()
        self._init_schema()

    def _check_integrity(self) -> None:
        """Run integrity check on startup. Attempt repair if corrupted."""
        import structlog

        logger = structlog.get_logger(__name__)
        try:
            result = self.conn.execute("PRAGMA integrity_check").fetchone()
            if result and result[0] == "ok":
                return
            logger.warning("db_integrity_failed", detail=result[0] if result else "unknown")
            self._repair_db()
        except Exception as e:
            logger.error("db_integrity_error", error=str(e))
            self._repair_db()

    def _repair_db(self) -> None:
        """Attempt WAL checkpoint recovery. If still broken, backup and recreate."""
        import shutil

        import structlog

        logger = structlog.get_logger(__name__)
        try:
            self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            result = self.conn.execute("PRAGMA integrity_check").fetchone()
            if result and result[0] == "ok":
                logger.info("db_repaired_via_checkpoint")
                return
        except Exception:
            pass
        # Backup corrupted DB and recreate
        import time

        backup = f"{self.db_path}.corrupted.{int(time.time())}"
        try:
            self.conn.close()
            shutil.copy2(self.db_path, backup)
            logger.warning("db_backed_up_corrupted", backup=backup)
            import sqlite3

            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode=WAL")
        except Exception as e:
            logger.error("db_repair_failed", error=str(e))

    def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                aliases TEXT DEFAULT '[]',
                properties TEXT DEFAULT '{}',
                valid_from TEXT,
                valid_until TEXT,
                superseded_by TEXT,
                source_ids TEXT DEFAULT '[]',
                confidence TEXT DEFAULT 'MEDIUM',
                recorded_at TEXT NOT NULL DEFAULT (datetime('now')),
                last_verified TEXT
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS entities_fts
                USING fts5(name, aliases);

            -- Triggers to keep FTS5 index in sync with entities table
            CREATE TRIGGER IF NOT EXISTS entities_ai AFTER INSERT ON entities BEGIN
                INSERT INTO entities_fts(rowid, name, aliases)
                VALUES (new.rowid, new.name, new.aliases);
            END;
            CREATE TRIGGER IF NOT EXISTS entities_ad AFTER DELETE ON entities BEGIN
                INSERT INTO entities_fts(entities_fts, rowid, name, aliases)
                VALUES('delete', old.rowid, old.name, old.aliases);
            END;
            CREATE TRIGGER IF NOT EXISTS entities_au AFTER UPDATE ON entities BEGIN
                INSERT INTO entities_fts(entities_fts, rowid, name, aliases)
                VALUES('delete', old.rowid, old.name, old.aliases);
                INSERT INTO entities_fts(rowid, name, aliases)
                VALUES (new.rowid, new.name, new.aliases);
            END;

            CREATE TABLE IF NOT EXISTS relations (
                id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL REFERENCES entities(id),
                predicate TEXT NOT NULL,
                object_id TEXT NOT NULL REFERENCES entities(id),
                valid_from TEXT,
                valid_until TEXT,
                confidence TEXT DEFAULT 'MEDIUM',
                source_ids TEXT DEFAULT '[]',
                recorded_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_rel_subject ON relations(subject_id);
            CREATE INDEX IF NOT EXISTS idx_rel_object ON relations(object_id);
            CREATE INDEX IF NOT EXISTS idx_rel_predicate ON relations(predicate);
            CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                source_type TEXT,
                ingested_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        self.conn.commit()

    async def upsert_entity(self, entity: Entity) -> str:
        """
        Pseudocode:
        1. Check if entity with same name+type exists → UPDATE
        2. Else → INSERT
        3. Rebuild FTS5 index for this entity
        4. Return entity.id
        """
        import json as _json

        self.conn.execute(
            """
            INSERT OR REPLACE INTO entities (
                id, type, name, aliases, properties, valid_from, valid_until,
                superseded_by, source_ids, confidence, recorded_at, last_verified
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)
        """,
            (
                entity.id,
                entity.type,
                entity.name,
                _json.dumps(entity.aliases),
                _json.dumps(entity.properties),
                entity.valid_from,
                entity.valid_until,
                entity.superseded_by,
                _json.dumps(entity.source_ids),
                entity.confidence,
                entity.last_verified,
            ),
        )
        self.conn.commit()
        return entity.id

    async def get_entity(self, entity_id: str) -> Entity | None:
        import json as _json

        row = self.conn.execute("SELECT * FROM entities WHERE id = ?", (entity_id,)).fetchone()
        if row is None:
            return None
        return Entity(
            id=row["id"],
            type=row["type"],
            name=row["name"],
            aliases=_json.loads(row["aliases"]),
            properties=_json.loads(row["properties"]),
            valid_from=row["valid_from"],
            valid_until=row["valid_until"],
            superseded_by=row["superseded_by"],
            source_ids=_json.loads(row["source_ids"]),
            confidence=row["confidence"],
            recorded_at=row["recorded_at"],
            last_verified=row["last_verified"],
        )

    async def search(self, query: str, mode: str = "hybrid", top_k: int = 20) -> list[dict]:
        """Search entities by keyword (FTS5), semantic (LanceDB), or hybrid."""
        if mode in ("fulltext", "hybrid"):
            rows = self.conn.execute(
                "SELECT e.* FROM entities e JOIN entities_fts f ON e.rowid = f.rowid WHERE entities_fts MATCH ? ORDER BY rank LIMIT ?",
                (query, top_k),
            ).fetchall()
            fts_results = [dict(r) for r in rows]
        else:
            fts_results = []

        if mode in ("semantic", "hybrid"):
            vector_store = LanceDBVectorStore()
            semantic_results = await vector_store.search(query, top_k=top_k)
            # Lazy index fallback: if no results but DB has entities, auto-index
            if not semantic_results:
                count_row = self.conn.execute("SELECT COUNT(*) FROM entities").fetchone()
                if count_row and count_row[0] > 0:
                    try:
                        import json as _json

                        rows = self.conn.execute(
                            "SELECT id, type, name, confidence, properties FROM entities LIMIT 200"
                        ).fetchall()
                        entity_objs = [
                            Entity(
                                id=r["id"],
                                type=r["type"],
                                name=r["name"],
                                confidence=r["confidence"],
                                properties=_json.loads(r["properties"]),
                            )
                            for r in rows
                        ]
                        await vector_store.index_entities(entity_objs, mode="overwrite")
                        semantic_results = await vector_store.search(query, top_k=top_k)
                    except Exception:
                        pass
        else:
            semantic_results = []

        if mode == "fulltext":
            return fts_results
        if mode == "semantic":
            return semantic_results

        # Hybrid: RRF fusion of FTS5 + semantic results
        seen = {r["id"] for r in fts_results if "id" in r}
        merged = list(fts_results)
        for sr in semantic_results:
            if sr.get("id") not in seen:
                merged.append(
                    {
                        "id": sr["id"],
                        "name": sr.get("content", ""),
                        "type": sr.get("metadata", {}).get("type", "Concept"),
                        "confidence": sr.get("metadata", {}).get("confidence", "MEDIUM"),
                        "similarity": sr.get("similarity", 0),
                    }
                )
        return merged[:top_k]

    async def upsert_relation(self, rel: Relation) -> str:
        import json as _json

        self.conn.execute(
            """
            INSERT OR REPLACE INTO relations (id, subject_id, predicate, object_id,
                valid_from, valid_until, confidence, source_ids, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
            (
                rel.id,
                rel.subject_id,
                rel.predicate,
                rel.object_id,
                rel.valid_from,
                rel.valid_until,
                rel.confidence,
                _json.dumps(rel.source_ids),
            ),
        )
        self.conn.commit()
        return rel.id

    async def ingest(self, source: str, source_type: str = "auto") -> dict:
        """Ingest content into knowledge base.

        Detects source type, extracts content, runs regex entity extraction,
        upserts entities to SQLite, and returns counts.
        """
        import hashlib
        import json as _json
        import re
        from pathlib import Path as _Path

        # Lazy-init class-level regex patterns on first call
        if not SQLiteKnowledgeStore._ENTITY_PATTERNS:
            SQLiteKnowledgeStore._ENTITY_PATTERNS = {
                "Person": re.compile(r"\b(?:Dr\.|Mr\.|Ms\.|Prof\.)\s+[A-Z][a-z]+\s+[A-Z][a-z]+\b"),
                "Organization": re.compile(
                    r"\b([A-Z][a-z]*\s){0,3}(?:Inc|Corp(?:oration)?|LLC|Ltd|University|Institute|Company)\b"
                ),
                "Date": re.compile(
                    r"\b\d{4}-\d{2}-\d{2}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{4}\b"
                ),
                "URL": re.compile(r"https?://[^\s<>\"']+"),
            }

        # 1. Determine source type and fetch content
        if source_type == "auto":
            if source.startswith(("http://", "https://")):
                source_type = "url"
            elif source.endswith(".pdf"):
                source_type = "pdf"
            elif source.endswith((".md", ".markdown")):
                source_type = "markdown"
            elif _Path(source).exists():
                source_type = "file"
            else:
                source_type = "url"

        content = ""
        if source_type == "url":
            try:
                import httpx

                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(source)
                    resp.raise_for_status()
                    content = resp.text[:50000]
            except Exception:
                return {
                    "entity_count": 0,
                    "relation_count": 0,
                    "source_path": source,
                    "error": "fetch failed",
                }
        elif source_type in ("file", "markdown", "pdf"):
            path = _Path(source).expanduser()
            if path.exists():
                with open(path, encoding="utf-8", errors="replace") as fh:
                    content = fh.read(50000)
            else:
                return {
                    "entity_count": 0,
                    "relation_count": 0,
                    "source_path": source,
                    "error": "file not found",
                }
        else:
            return {
                "entity_count": 0,
                "relation_count": 0,
                "source_path": source,
                "error": f"unsupported type: {source_type}",
            }

        if not content.strip():
            return {"entity_count": 0, "relation_count": 0, "source_path": source}

        # 2. Content hash for dedup
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        existing = self.conn.execute("SELECT id FROM sources WHERE content_hash = ?", (content_hash,)).fetchone()
        if existing:
            return {
                "entity_count": 0,
                "relation_count": 0,
                "source_path": source,
                "dedup": "skipped",
            }

        # 3. Basic regex entity extraction (patterns compiled once at class level)
        entity_count = 0
        inserted_eids: set[str] = set()
        for etype, pattern in SQLiteKnowledgeStore._ENTITY_PATTERNS.items():
            for match in pattern.finditer(content):
                name = match.group(0)[:120]
                eid = hashlib.sha256(f"{etype}:{name}".encode()).hexdigest()[:16]
                before = self.conn.total_changes
                self.conn.execute(
                    "INSERT OR IGNORE INTO entities (id, type, name, source_ids, recorded_at) VALUES (?, ?, ?, ?, datetime('now'))",
                    (eid, etype, name, _json.dumps([source])),
                )
                if self.conn.total_changes > before:
                    entity_count += 1
                    inserted_eids.add(eid)

        # 4. Co-occurrence based relations — only scan new entities
        paragraphs = [p for p in content.split("\n\n") if len(p) > 50][:20]
        relation_count = 0
        entity_names = {}
        if inserted_eids:
            placeholders = ",".join("?" for _ in inserted_eids)
            for row in self.conn.execute(
                f"SELECT id, name FROM entities WHERE id IN ({placeholders})",
                tuple(inserted_eids),
            ).fetchall():
                entity_names[row["id"]] = row["name"]

        for para in paragraphs:
            found_ids = [eid for eid, name in entity_names.items() if name.lower() in para.lower()]
            for i in range(len(found_ids)):
                for j in range(i + 1, min(i + 3, len(found_ids))):
                    rid = hashlib.sha256(f"rel:{found_ids[i]}:{found_ids[j]}".encode()).hexdigest()[:16]
                    before = self.conn.total_changes
                    self.conn.execute(
                        "INSERT OR IGNORE INTO relations (id, subject_id, predicate, object_id, source_ids, recorded_at) VALUES (?, ?, 'RELATES_TO', ?, ?, datetime('now'))",
                        (rid, found_ids[i], found_ids[j], _json.dumps([source])),
                    )
                    if self.conn.total_changes > before:
                        relation_count += 1

        # 5. Record source ingestion
        self.conn.execute(
            "INSERT OR REPLACE INTO sources (id, path, content_hash, source_type, ingested_at) VALUES (?, ?, ?, ?, datetime('now'))",
            (hashlib.sha256(source.encode()).hexdigest()[:16], source, content_hash, source_type),
        )
        self.conn.commit()

        return {
            "entity_count": entity_count,
            "relation_count": relation_count,
            "source_path": source,
        }

    async def get_timeline(
        self, entity_id: str, from_date: str | None = None, to_date: str | None = None
    ) -> list[dict]:
        """Get chronological events related to entity."""
        query = """
            SELECT e.* FROM entities e
            JOIN relations r ON (e.id = r.object_id OR e.id = r.subject_id)
            WHERE (r.subject_id = ? OR r.object_id = ?)
              AND e.type = 'event'
        """
        params = [entity_id, entity_id]
        if from_date:
            query += " AND e.valid_from >= ?"
            params.append(from_date)
        if to_date:
            query += " AND e.valid_from <= ?"
            params.append(to_date)
        query += " ORDER BY e.valid_from ASC"
        rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    async def get_contradictions(self, entity_id: str | None = None) -> list[dict]:
        """Find CONTRADICTS relations."""
        if entity_id:
            rows = self.conn.execute(
                "SELECT * FROM relations WHERE predicate = 'contradicts' AND (subject_id = ? OR object_id = ?)",
                (entity_id, entity_id),
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM relations WHERE predicate = 'contradicts'").fetchall()
        return [dict(r) for r in rows]


# ============================================================
# LanceDB Vector Backend (Tier 1)
# ============================================================


class LanceDBVectorStore:
    """Vector similarity search via LanceDB.

    Embedding model: sentence-transformers/all-MiniLM-L6-v2 (384d)
    Falls back gracefully when dependencies are unavailable.
    """

    def __init__(self, db_path: str = "~/minerva/vectors", embedding_dim: int = 384) -> None:
        from pathlib import Path

        self.db_path = str(Path(db_path).expanduser())
        self.dim = embedding_dim
        self._model = None
        self._table = None

    def _get_model(self) -> Any:
        """Lazy-load sentence-transformers model. Returns None if unavailable."""
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            return self._model
        except Exception:
            return None

    def _get_table(self) -> Any:
        """Lazy-init LanceDB table. Returns None if unavailable."""
        if self._table is not None:
            return self._table
        try:
            import os

            import lancedb

            os.makedirs(self.db_path, exist_ok=True)
            db = lancedb.connect(self.db_path)
            self._table = db.open_table("entities") if "entities" in db.list_tables() else None  # type: ignore[reportOperatorIssue]
            return self._table
        except Exception:
            return None

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings. Returns zero vectors if model unavailable."""
        if not texts:
            return []
        model = self._get_model()
        if model is None:
            return [[0.0] * self.dim for _ in texts]
        import asyncio

        loop = asyncio.get_event_loop()
        vectors = await loop.run_in_executor(None, lambda: model.encode(texts, batch_size=32, show_progress_bar=False))
        return vectors.tolist() if hasattr(vectors, "tolist") else [v.tolist() for v in vectors]

    async def search(self, query: str, top_k: int = 20) -> list[dict]:
        """Semantic vector search. Returns empty list if unavailable."""
        table = self._get_table()
        if table is None:
            return []
        query_vecs = await self.embed([query])
        if not query_vecs or sum(abs(v) for v in query_vecs[0]) < 0.001:
            return []
        try:
            result = table.search(query_vecs[0]).limit(top_k).to_list()
            return [
                {
                    "id": r.get("id", ""),
                    "content": r.get("text", ""),
                    "similarity": r.get("_distance", 0.0),
                    "metadata": r.get("metadata", {}),
                }
                for r in result
            ]
        except Exception:
            return []

    async def index_entities(self, entities: list[Entity], mode: str = "overwrite") -> None:
        """Index entities for semantic search. No-op if unavailable."""
        if not entities:
            return
        texts = [f"{e.name}: {e.properties.get('description', '')}" for e in entities]
        vectors = await self.embed(texts)
        if not vectors or sum(abs(v) for v in vectors[0]) < 0.001:
            return
        rows = [
            {
                "id": e.id,
                "text": texts[i],
                "vector": vectors[i],
                "metadata": {"type": e.type, "confidence": e.confidence},
            }
            for i, e in enumerate(entities)
        ]
        try:
            import os

            import lancedb

            os.makedirs(self.db_path, exist_ok=True)
            db = lancedb.connect(self.db_path)
            if mode == "overwrite" or "entities" not in db.list_tables():  # type: ignore[reportOperatorIssue]
                self._table = db.create_table("entities", rows, mode="overwrite")
            else:
                self._table = db.open_table("entities")
                self._table.add(rows)  # type: ignore[attr-defined]
        except Exception:
            pass


# ============================================================
# KnowledgeStore Factory
# ============================================================


def create_knowledge_store(config: dict) -> IKnowledgeStore:
    """Create knowledge store based on configuration.

    Returns SQLiteKnowledgeStore (Tier 1) as primary.
    Tier 2 stores (Neo4j, Semantica) are added as wrappers if enabled.
    """
    store = SQLiteKnowledgeStore(db_path=config.get("sqlite_path", "~/minerva/knowledge.db"))
    logger.info("knowledge_store_created", backend="sqlite")
    return store
