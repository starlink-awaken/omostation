"""Multi-storage backend support for Eidos.

Supported backends:
  - JSONFileBackend: per-key JSON files under ~/.eidos/store/
  - SQLiteBackend: single SQLite database (~/.kos/index.sqlite or custom path)
  - KOSLibraryBackend: wrapper that falls back to SQLiteBackend

All backends raise ``EidosError`` (ErrorCode.STORAGE_*) on failure.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Protocol, cast

from eidos.errors import EidosError, ErrorCode


class StorageBackend(Protocol):
    """Protocol for storage backends."""

    def save(self, key: str, data: dict) -> bool: ...

    def load(self, key: str) -> dict | None: ...

    def delete(self, key: str) -> bool: ...

    def list_keys(self, prefix: str = "") -> list[str]: ...


class JSONFileBackend:
    """Per-key JSON file storage under a base directory."""

    def __init__(self, base_path: str | Path | None = None) -> None:
        self.base_path = Path(base_path or Path.home() / ".eidos" / "store")
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.base_path / f"{key}.json"

    def save(self, key: str, data: dict) -> bool:
        try:
            self._path(key).write_text(json.dumps(data, indent=2, ensure_ascii=False))
            return True
        except OSError as exc:
            raise EidosError(
                ErrorCode.STORAGE_WRITE_FAILED,
                f"JSON storage write failed for key '{key}': {exc}",
                {"key": key, "path": str(self._path(key))},
            ) from exc

    def load(self, key: str) -> dict | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            return cast("dict[Any, Any] | None", json.loads(path.read_text()))
        except (json.JSONDecodeError, OSError) as exc:
            raise EidosError(
                ErrorCode.STORAGE_READ_FAILED,
                f"JSON storage read failed for key '{key}': {exc}",
                {"key": key, "path": str(path)},
            ) from exc

    def delete(self, key: str) -> bool:
        path = self._path(key)
        if not path.exists():
            return False
        try:
            path.unlink()
            return True
        except OSError as exc:
            raise EidosError(
                ErrorCode.STORAGE_WRITE_FAILED,
                f"JSON storage delete failed for key '{key}': {exc}",
                {"key": key, "path": str(path)},
            ) from exc

    def list_keys(self, prefix: str = "") -> list[str]:
        return sorted([p.stem for p in self.base_path.glob(f"{prefix}*.json")])


class SQLiteBackend:
    """SQLite storage backend.

    Stores key-value pairs in a single table (``eidos_store``) inside a
    SQLite database.  The database path defaults to
    ``~/.kos/index.sqlite`` for KOS data locality but can be overridden.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path or Path.home() / ".kos" / "index.sqlite")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _conn(self) -> sqlite3.Connection:
        """Return a connection to the SQLite database."""
        try:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            conn.execute("CREATE TABLE IF NOT EXISTS eidos_store (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)")
            return conn
        except sqlite3.Error as exc:
            raise EidosError(
                ErrorCode.STORAGE_CONNECTION_ERROR,
                f"SQLite connection failed: {exc}",
                {"db_path": str(self.db_path)},
            ) from exc

    def save(self, key: str, data: dict) -> bool:
        try:
            conn = self._conn()
            conn.execute(
                "INSERT OR REPLACE INTO eidos_store (key, value, updated_at) VALUES (?, ?, datetime('now'))",
                (key, json.dumps(data)),
            )
            conn.commit()
            conn.close()
            return True
        except (sqlite3.Error, OSError) as exc:
            raise EidosError(
                ErrorCode.STORAGE_WRITE_FAILED,
                f"SQLite storage write failed for key '{key}': {exc}",
                {"key": key, "db_path": str(self.db_path)},
            ) from exc

    def load(self, key: str) -> dict | None:
        try:
            conn = self._conn()
            row = conn.execute("SELECT value FROM eidos_store WHERE key = ?", (key,)).fetchone()
            conn.close()
            return json.loads(row[0]) if row else None
        except (sqlite3.Error, json.JSONDecodeError, OSError) as exc:
            raise EidosError(
                ErrorCode.STORAGE_READ_FAILED,
                f"SQLite storage read failed for key '{key}': {exc}",
                {"key": key, "db_path": str(self.db_path)},
            ) from exc

    def delete(self, key: str) -> bool:
        try:
            conn = self._conn()
            cur = conn.execute("DELETE FROM eidos_store WHERE key = ?", (key,))
            deleted = cur.rowcount > 0
            conn.commit()
            conn.close()
            return deleted
        except sqlite3.Error as exc:
            raise EidosError(
                ErrorCode.STORAGE_WRITE_FAILED,
                f"SQLite storage delete failed for key '{key}': {exc}",
                {"key": key, "db_path": str(self.db_path)},
            ) from exc

    def list_keys(self, prefix: str = "") -> list[str]:
        try:
            conn = self._conn()
            rows = conn.execute(
                "SELECT key FROM eidos_store WHERE key LIKE ?",
                (f"{prefix}%",),
            ).fetchall()
            conn.close()
            return [r[0] for r in rows]
        except sqlite3.Error as exc:
            raise EidosError(
                ErrorCode.STORAGE_READ_FAILED,
                f"SQLite storage list_keys failed: {exc}",
                {"prefix": prefix},
            ) from exc


class KOSLibraryBackend:
    """KOS library backend — delegates save/load/delete/list to SQLiteBackend,
    and exposes KOS search/stats when the ``kos`` package is importable.

    This backend never raises from the KOS import—if ``kos`` is unavailable
    it operates as a pure SQLite storage with no search/stats capability.
    """

    def __init__(self) -> None:
        self._fallback = SQLiteBackend()
        self._kos_available = False
        try:
            from kos import search as _kos_search  # type: ignore[import-untyped, import-not-found]
            from kos import stats as _kos_stats

            self._search = _kos_search
            self._stats = _kos_stats
            self._kos_available = True
        except ImportError:
            pass
        except Exception:
            pass  # KOS import may fail in odd edge cases — stay resilient

    def save(self, key: str, data: dict) -> bool:
        return self._fallback.save(key, data)

    def load(self, key: str) -> dict | None:
        return self._fallback.load(key)

    def delete(self, key: str) -> bool:
        return self._fallback.delete(key)

    def list_keys(self, prefix: str = "") -> list[str]:
        return self._fallback.list_keys(prefix)

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search KOS knowledge base. Returns [] if KOS unavailable."""
        if self._kos_available:
            return cast("list[dict[Any, Any]]", self._search(query=query, limit=limit))
        return []

    def stats(self) -> dict:
        """Get KOS statistics. Returns {'total': 0} if KOS unavailable."""
        if self._kos_available:
            return cast("dict[Any, Any]", self._stats())
        return {"total": 0}


def get_default_backend() -> KOSLibraryBackend:
    """Get the default storage backend (tries KOS, falls back to SQLite)."""
    return KOSLibraryBackend()
