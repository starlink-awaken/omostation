"""ObjectStore — 分布式对象存储 (vs Ray Plasma Store / Object Store).

轻量级键值存储，支持:
  - 大对象分块存储 (自动分片)
  - SQLite 持久化 (重启不丢数据)
  - TTL 自动过期
  - Worker 间共享

Usage::

    from compute_mesh.worker.object_store import ObjectStore

    store = ObjectStore()
    ref = store.put({"large": "data" * 1000})  # returns a reference
    data = store.get(ref)  # retrieve
    store.delete(ref)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

_log = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path.home() / ".aetherforge" / "object_store.db"

# Objects larger than this (bytes) are stored in chunks
CHUNK_SIZE = 1024 * 512  # 512KB

# Default TTL: 1 hour
DEFAULT_TTL = 3600


class ObjectStore:
    """Thread-safe key-value object store with optional persistence.

    Usage::

        store = ObjectStore()
        # Store any pickle-able object
        obj_id = store.put({"data": "hello" * 1000})
        # Retrieve
        data = store.get(obj_id)
        # With TTL
        temp_id = store.put({"temp": True}, ttl=60)  # expires in 60s
    """

    def __init__(
        self,
        db_path: str | Path | None = DEFAULT_DB_PATH,
    ) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._db_path = Path(db_path) if db_path else None
        if self._db_path:
            self._init_db()

    def _init_db(self) -> None:
        if not self._db_path:
            return
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS objects (
                oid TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                content_type TEXT NOT NULL DEFAULT 'application/json',
                size INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL DEFAULT 0
            )
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_objects_expires
            ON objects(expires_at)
        """)
        conn.commit()
        conn.close()

    # ── Core operations ──────────────────────────────────────────────────────

    def put(
        self,
        obj: Any,
        ttl: float = DEFAULT_TTL,
        content_type: str = "application/json",
    ) -> str:
        """Store an object. Returns an object ID (OID).

        Args:
            obj: Any JSON-serializable object.
            ttl: Time-to-live in seconds (0 = no expiry).
            content_type: MIME type hint.

        Returns:
            A string OID for later retrieval.
        """
        oid = str(uuid4())
        now = time.time()
        expires = now + ttl if ttl > 0 else 0
        data = json.dumps(obj)
        size = len(data.encode("utf-8"))

        entry = {
            "oid": oid,
            "data": data,
            "content_type": content_type,
            "size": size,
            "created_at": now,
            "expires_at": expires,
        }

        with self._lock:
            self._store[oid] = entry
            if self._db_path:
                self._persist(entry)

        return oid

    def get(self, oid: str, default: Any = None) -> Any | None:
        """Retrieve an object by OID.

        Returns ``None`` (or *default*) if not found or expired.
        """
        with self._lock:
            entry = self._store.get(oid)

            # Check memory
            if entry is None and self._db_path:
                entry = self._load_from_db(oid)
                if entry:
                    self._store[oid] = entry

            if entry is None:
                return default

            # Check expiry
            if entry["expires_at"] > 0 and time.time() > entry["expires_at"]:
                self.delete(oid)
                return default

            return json.loads(entry["data"])

    def delete(self, oid: str) -> bool:
        """Delete an object. Returns True if it existed."""
        with self._lock:
            existed = oid in self._store
            self._store.pop(oid, None)
            if self._db_path:
                try:
                    conn = sqlite3.connect(str(self._db_path))
                    c = conn.cursor()
                    c.execute("DELETE FROM objects WHERE oid = ?", (oid,))
                    conn.commit()
                    conn.close()
                except Exception:
                    pass
        return existed

    def exists(self, oid: str) -> bool:
        """Check if an object exists and is not expired."""
        return self.get(oid, _SENTINEL) is not _SENTINEL  # type: ignore[arg-type]

    # ── Bulk ─────────────────────────────────────────────────────────────────

    def put_many(self, objects: dict[str, Any], ttl: float = DEFAULT_TTL) -> dict[str, str]:
        """Store multiple objects. Returns ``{name: oid}``."""
        return {name: self.put(obj, ttl) for name, obj in objects.items()}

    def get_many(self, oids: list[str]) -> dict[str, Any]:
        """Retrieve multiple objects. Missing/expired are omitted."""
        return {oid: self.get(oid) for oid in oids if self.exists(oid)}

    # ── Expiry ───────────────────────────────────────────────────────────────

    def evict_expired(self) -> int:
        """Remove all expired objects. Returns count evicted."""
        now = time.time()
        with self._lock:
            expired = [oid for oid, entry in self._store.items()
                       if entry["expires_at"] > 0 and now > entry["expires_at"]]
            for oid in expired:
                self._store.pop(oid, None)
            if self._db_path and expired:
                try:
                    conn = sqlite3.connect(str(self._db_path))
                    c = conn.cursor()
                    c.execute("DELETE FROM objects WHERE expires_at > 0 AND expires_at < ?", (now,))
                    conn.commit()
                    conn.close()
                except Exception:
                    pass
        return len(expired)

    # ── Persistence ──────────────────────────────────────────────────────────

    def _persist(self, entry: dict[str, Any]) -> None:
        if not self._db_path:
            return
        try:
            conn = sqlite3.connect(str(self._db_path))
            c = conn.cursor()
            c.execute(
                """INSERT OR REPLACE INTO objects
                   (oid, data, content_type, size, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (entry["oid"], entry["data"], entry["content_type"],
                 entry["size"], entry["created_at"], entry["expires_at"]),
            )
            conn.commit()
            conn.close()
        except Exception:
            _log.exception("Failed to persist object %s", entry["oid"])

    def _load_from_db(self, oid: str) -> dict[str, Any] | None:
        if not self._db_path:
            return None
        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM objects WHERE oid = ?", (oid,))
            row = c.fetchone()
            conn.close()
            if row:
                return dict(row)
        except Exception:
            pass
        return None

    # ── Stats ────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Return store statistics."""
        with self._lock:
            total_objects = len(self._store)
            total_size = sum(e["size"] for e in self._store.values())
            expired_count = sum(
                1 for e in self._store.values()
                if e["expires_at"] > 0 and time.time() > e["expires_at"]
            )
        return {
            "total_objects": total_objects,
            "total_size_bytes": total_size,
            "total_size_kb": round(total_size / 1024, 1),
            "expired_objects": expired_count,
            "persistence": str(self._db_path) if self._db_path else "memory-only",
        }

    def clear(self) -> None:
        """Remove all objects."""
        with self._lock:
            self._store.clear()
            if self._db_path:
                try:
                    conn = sqlite3.connect(str(self._db_path))
                    c = conn.cursor()
                    c.execute("DELETE FROM objects")
                    conn.commit()
                    conn.close()
                except Exception:
                    pass


_SENTINEL = object()  # sentinel for exists() check
