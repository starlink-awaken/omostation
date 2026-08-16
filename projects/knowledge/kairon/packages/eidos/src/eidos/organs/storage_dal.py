"""SQLite relational storage provider — lightweight SQLite-backed key-value store.

Provides SQLite relational provider with basic migration and connection management.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any, cast

_log = logging.getLogger(__name__)


class SQLiteError(Exception):
    """Base exception for SQLite storage operations."""

    pass


class SQLiteOperationalError(SQLiteError):
    """Operational error during SQLite storage operations."""

    pass


class SQLiteRelationalProvider:
    """Lightweight SQLite-backed relational storage provider.

    Provides basic CRUD operations for knowledge graph entities and relations.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database connection and create tables if needed."""
        try:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._create_tables()
        except sqlite3.Error as e:
            _log.error("Failed to initialize SQLite at %s: %s", self.db_path, e)
            raise SQLiteOperationalError(str(e)) from e

    def _create_tables(self) -> None:
        """Create default tables if they don't exist."""
        if self._conn is None:
            return
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS kv_store (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                entity_type TEXT DEFAULT '',
                properties TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS relations (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                properties TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)
        self._conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> Any:
        """Execute a raw SQL query."""
        if self._conn is None:
            raise SQLiteOperationalError("Database not initialized")
        try:
            return self._conn.execute(sql, params)
        except sqlite3.Error as e:
            raise SQLiteOperationalError(str(e)) from e

    def execute_many(self, sql: str, params_list: list[tuple]) -> None:
        """Execute a SQL statement with multiple parameter sets."""
        if self._conn is None:
            raise SQLiteOperationalError("Database not initialized")
        try:
            self._conn.executemany(sql, params_list)
            self._conn.commit()
        except sqlite3.Error as e:
            raise SQLiteOperationalError(str(e)) from e

    def fetch_one(self, sql: str, params: tuple = ()) -> Any:
        """Fetch a single row."""
        cur = self.execute(sql, params)
        return cur.fetchone()

    def fetch_all(self, sql: str, params: tuple = ()) -> list[Any]:
        """Fetch all rows."""
        cur = self.execute(sql, params)
        return cast("list[Any]", cur.fetchall())

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> SQLiteRelationalProvider:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def connect(self) -> None:
        """Connect (stub, no-op — __init__ already connects)."""

    def execute_write(self, sql: str, params: tuple = ()) -> Any:
        """Execute a write statement (stub, delegates to execute)."""
        return self.execute(sql, params)

    def disconnect(self) -> None:
        """Disconnect (stub, delegates to close)."""
        self.close()


__all__ = [
    "SQLiteError",
    "SQLiteOperationalError",
    "SQLiteRelationalProvider",
]
