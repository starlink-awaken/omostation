"""Agent Memory System — 3-tier memory (working, project, org)."""

import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MemoryEntry:
    key: str
    value: Any
    ttl_seconds: float = 3600.0
    created_at: float = field(default_factory=time.time)
    access_count: int = 0

class WorkingMemory:
    """Volatile, TTL-based memory for active tasks."""

    def __init__(self, max_entries: int = 1000, default_ttl: float = 3600.0):
        self.max_entries = max_entries
        self.default_ttl = default_ttl
        self._store: OrderedDict[str, MemoryEntry] = OrderedDict()

    def set(self, key: str, value: Any, ttl_seconds: float | None = None):
        if len(self._store) >= self.max_entries:
            self._store.popitem(last=False)
        self._store[key] = MemoryEntry(key=key, value=value,
            ttl_seconds=ttl_seconds or self.default_ttl)

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if not entry:
            return None
        if time.time() - entry.created_at > entry.ttl_seconds:
            del self._store[key]
            return None
        entry.access_count += 1
        self._store.move_to_end(key)
        return entry.value

    def cleanup(self) -> int:
        """Remove expired entries. Returns count removed."""
        now = time.time()
        expired = [k for k, e in self._store.items() if now - e.created_at > e.ttl_seconds]
        for k in expired:
            del self._store[k]
        return len(expired)

    def clear(self):
        self._store.clear()


class ProjectMemory:
    """Persistent memory for a project using SQLite."""

    def __init__(self, db_path: str = ":memory:"):
        import sqlite3
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("CREATE TABLE IF NOT EXISTS memory (key TEXT PRIMARY KEY, value TEXT, updated_at REAL)")
        self._conn.commit()

    def set(self, key: str, value: Any):
        import json
        self._conn.execute("INSERT OR REPLACE INTO memory VALUES (?, ?, ?)",
                           (key, json.dumps(value, default=str), time.time()))
        self._conn.commit()

    def get(self, key: str) -> Any | None:
        import json
        row = self._conn.execute("SELECT value FROM memory WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def list_keys(self) -> list[str]:
        return [r[0] for r in self._conn.execute("SELECT key FROM memory").fetchall()]

    def delete(self, key: str) -> bool:
        c = self._conn.execute("DELETE FROM memory WHERE key = ?", (key,)).rowcount
        self._conn.commit()
        return c > 0

    def close(self):
        self._conn.close()


class OrgMemory:
    """Cross-project memory using SQLite."""

    def __init__(self, db_path: str = ":memory:"):
        import sqlite3
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("""CREATE TABLE IF NOT EXISTS org_memory
            (key TEXT PRIMARY KEY, value TEXT, project_id TEXT, tags TEXT, updated_at REAL)""")
        self._conn.commit()

    def set(self, key: str, value: Any, project_id: str = "", tags: list[str] | None = None):
        import json
        tags_str = ",".join(tags) if tags else ""
        self._conn.execute("INSERT OR REPLACE INTO org_memory VALUES (?, ?, ?, ?, ?)",
                           (key, json.dumps(value, default=str), project_id, tags_str, time.time()))
        self._conn.commit()

    def get(self, key: str) -> Any | None:
        import json
        row = self._conn.execute("SELECT value FROM org_memory WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def search_by_tag(self, tag: str) -> list[str]:
        rows = self._conn.execute("SELECT key FROM org_memory WHERE tags LIKE ?", (f"%{tag}%",)).fetchall()
        return [r[0] for r in rows]

    def list_by_project(self, project_id: str) -> list[str]:
        rows = self._conn.execute("SELECT key FROM org_memory WHERE project_id = ?", (project_id,)).fetchall()
        return [r[0] for r in rows]

    def close(self):
        self._conn.close()
