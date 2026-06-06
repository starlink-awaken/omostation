"""Engine Memory -- 3-tier memory with store/retrieve/search/summarize."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from runtime.executor.engine_types import OrgMemoryEntry, ProjectMemoryEntry, WorkingMemoryEntry


class WorkingMemory:
    """Volatile key-value store with optional TTL."""

    def __init__(self) -> None:
        self._store: dict[str, WorkingMemoryEntry] = {}

    def set(self, key: str, value: Any, ttl_ms: int | None = None) -> None:
        expires_at = (time.time() * 1000 + ttl_ms) if ttl_ms is not None else None
        self._store[key] = WorkingMemoryEntry(value=value, expires_at=expires_at)

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        now_ms = time.time() * 1000
        if entry.expires_at is not None and now_ms > entry.expires_at:
            del self._store[key]
            return None
        return entry.value

    def has(self, key: str) -> bool:
        return self.get(key) is not None

    def delete(self, key: str) -> bool:
        return self._store.pop(key, None) is not None

    def clear(self) -> None:
        self._store.clear()

    def prune(self) -> int:
        now_ms = time.time() * 1000
        expired = [k for k, e in self._store.items() if e.expires_at is not None and now_ms > e.expires_at]
        for k in expired:
            del self._store[k]
        return len(expired)

    def get_all(self) -> dict[str, Any]:
        self.prune()
        return {k: e.value for k, e in self._store.items()}

    @property
    def size(self) -> int:
        self.prune()
        return len(self._store)


class ProjectMemory:
    """Durable per-project knowledge store backed by SQLite."""

    def __init__(self, db_path: str = ":memory:") -> None:
        import sqlite3

        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS project_memory (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                category TEXT NOT NULL, key TEXT NOT NULL,
                value TEXT NOT NULL, metadata TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL, updated_at REAL NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_pm_unique
                ON project_memory(project_id, category, key);
        """)
        self._conn.commit()

    def store(
        self, project_id: str, category: str, key: str, value: str, metadata: dict[str, Any] | None = None
    ) -> None:
        now = time.time()
        self._conn.execute(
            """INSERT INTO project_memory VALUES (?, ?, ?, ?, ?, ?, ?, ?)
             ON CONFLICT(project_id, category, key) DO UPDATE SET value=excluded.value, metadata=excluded.metadata, updated_at=excluded.updated_at""",
            (str(uuid.uuid4()), project_id, category, key, value, json.dumps(metadata or {}), now, now),
        )
        self._conn.commit()

    def retrieve(self, project_id: str, category: str, key: str) -> ProjectMemoryEntry | None:
        row = self._conn.execute(
            "SELECT * FROM project_memory WHERE project_id=? AND category=? AND key=?", (project_id, category, key)
        ).fetchone()
        return ProjectMemory._row_to_entry(row) if row else None

    def list_by_category(self, project_id: str, category: str) -> list[ProjectMemoryEntry]:
        rows = self._conn.execute(
            "SELECT * FROM project_memory WHERE project_id=? AND category=? ORDER BY updated_at DESC",
            (project_id, category),
        ).fetchall()
        return [ProjectMemory._row_to_entry(r) for r in rows]

    def search(self, project_id: str, query: str) -> list[ProjectMemoryEntry]:
        like = f"%{query}%"
        rows = self._conn.execute(
            "SELECT * FROM project_memory WHERE project_id=? AND (key LIKE ? OR value LIKE ? OR category LIKE ?) ORDER BY updated_at DESC",
            (project_id, like, like, like),
        ).fetchall()
        return [ProjectMemory._row_to_entry(r) for r in rows]

    def summarize(self, project_id: str, category: str | None = None) -> dict[str, Any]:
        if category:
            row = self._conn.execute(
                "SELECT count(*), count(DISTINCT key) FROM project_memory WHERE project_id=? AND category=?",
                (project_id, category),
            ).fetchone()
            return {"project_id": project_id, "category": category, "entries": row[0], "unique_keys": row[1]}
        rows = self._conn.execute(
            "SELECT category, count(*) FROM project_memory WHERE project_id=? GROUP BY category", (project_id,)
        ).fetchall()
        return {"project_id": project_id, "categories": {r[0]: r[1] for r in rows}}

    def delete(self, project_id: str, category: str, key: str) -> bool:
        c = self._conn.execute(
            "DELETE FROM project_memory WHERE project_id=? AND category=? AND key=?", (project_id, category, key)
        ).rowcount
        self._conn.commit()
        return c > 0

    def delete_by_project(self, project_id: str) -> int:
        c = self._conn.execute("DELETE FROM project_memory WHERE project_id=?", (project_id,)).rowcount
        self._conn.commit()
        return c

    def close(self) -> None:
        self._conn.close()

    # fmt: off
    @staticmethod
    def _row_to_entry(row: tuple) -> ProjectMemoryEntry:
        md = {}
        try: md = json.loads(row[5])  # noqa: E701
        except (json.JSONDecodeError, IndexError): pass  # noqa: E701
        return ProjectMemoryEntry(id=row[0], project_id=row[1], category=row[2], key=row[3], value=row[4], metadata=md, created_at=row[6], updated_at=row[7])


class OrgMemory:
    """Cross-project institutional knowledge store backed by SQLite."""

    def __init__(self, db_path: str = ":memory:") -> None:
        import sqlite3

        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS org_memory (
                id TEXT PRIMARY KEY, category TEXT NOT NULL, key TEXT NOT NULL,
                value TEXT NOT NULL, source_project TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 0.5,
                tags TEXT NOT NULL DEFAULT '[]',
                created_at REAL NOT NULL, updated_at REAL NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_om_unique
                ON org_memory(category, key);
            CREATE INDEX IF NOT EXISTS idx_om_confidence
                ON org_memory(confidence DESC);
        """)
        self._conn.commit()

    def store(
        self,
        category: str,
        key: str,
        value: str,
        source_project: str = "",
        confidence: float = 0.5,
        tags: list[str] | None = None,
    ) -> None:
        now = time.time()
        confidence = max(0.0, min(1.0, confidence))
        self._conn.execute(
            """INSERT INTO org_memory VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
             ON CONFLICT(category, key) DO UPDATE SET value=excluded.value, source_project=excluded.source_project, confidence=excluded.confidence, tags=excluded.tags, updated_at=excluded.updated_at""",
            (str(uuid.uuid4()), category, key, value, source_project, confidence, json.dumps(tags or []), now, now),
        )
        self._conn.commit()

    def retrieve(self, category: str, key: str) -> OrgMemoryEntry | None:
        row = self._conn.execute("SELECT * FROM org_memory WHERE category=? AND key=?", (category, key)).fetchone()
        return OrgMemory._row_to_entry(row) if row else None

    def list_by_category(self, category: str) -> list[OrgMemoryEntry]:
        rows = self._conn.execute(
            "SELECT * FROM org_memory WHERE category=? ORDER BY confidence DESC, updated_at DESC", (category,)
        ).fetchall()
        return [OrgMemory._row_to_entry(r) for r in rows]

    def search_by_tags(self, tags: list[str]) -> list[OrgMemoryEntry]:
        if not tags:
            return []
        conditions = " OR ".join(["tags LIKE ?" for _ in tags])
        rows = self._conn.execute(
            f"SELECT * FROM org_memory WHERE {conditions} ORDER BY confidence DESC, updated_at DESC",
            [f"%{t}%" for t in tags],
        ).fetchall()
        return [OrgMemory._row_to_entry(r) for r in rows]

    def get_high_confidence(self, min_confidence: float = 0.7, limit: int = 50) -> list[OrgMemoryEntry]:
        rows = self._conn.execute(
            "SELECT * FROM org_memory WHERE confidence >= ? ORDER BY confidence DESC LIMIT ?", (min_confidence, limit)
        ).fetchall()
        return [OrgMemory._row_to_entry(r) for r in rows]

    def update_confidence(self, category: str, key: str, new_confidence: float) -> bool:
        new_confidence = max(0.0, min(1.0, new_confidence))
        c = self._conn.execute(
            "UPDATE org_memory SET confidence=?, updated_at=? WHERE category=? AND key=?",
            (new_confidence, time.time(), category, key),
        ).rowcount
        self._conn.commit()
        return c > 0

    def delete(self, category: str, key: str) -> bool:
        c = self._conn.execute("DELETE FROM org_memory WHERE category=? AND key=?", (category, key)).rowcount
        self._conn.commit()
        return c > 0

    def summarize(self) -> dict[str, Any]:
        rows = self._conn.execute(
            "SELECT category, count(*), avg(confidence) FROM org_memory GROUP BY category ORDER BY count(*) DESC"
        ).fetchall()
        return {
            "categories": {r[0]: {"count": r[1], "avg_confidence": round(r[2], 3)} for r in rows},
            "total": sum(r[1] for r in rows),
        }

    def close(self) -> None:
        self._conn.close()

    # fmt: off
    @staticmethod
    def _row_to_entry(row: tuple) -> OrgMemoryEntry:
        tags = []
        try: tags = json.loads(row[6])  # noqa: E701
        except (json.JSONDecodeError, IndexError): pass  # noqa: E701
        return OrgMemoryEntry(id=row[0], category=row[1], key=row[2], value=row[3], source_project=row[4], confidence=row[5], tags=tags, created_at=row[7], updated_at=row[8])
    # fmt: on
