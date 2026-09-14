"""KOS Common Database Utilities — shared connection helpers with optimized PRAGMA settings.

Usage:
    from kos.db import get_connection, get_ontology_connection

    conn = get_connection()  # Main retrieval database
    conn = get_ontology_connection()  # Ontology database
"""

import sqlite3
from typing import Any

from kos.config import get_artifact_path


def _set_pragmas(conn: sqlite3.Connection) -> None:
    """Set optimized PRAGMA settings for all connections."""
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA mmap_size=268435456")  # 256MB mmap


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Get a connection to the main retrieval database with optimized settings.

    Args:
        db_path: Optional path to database. If None, uses default retrieval database.

    Returns:
        sqlite3.Connection with Row factory and optimized PRAGMA settings.
    """
    if db_path is None:
        db_path = get_artifact_path("retrievalDatabase")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    _set_pragmas(conn)
    return conn


def get_ontology_connection() -> sqlite3.Connection:
    """Get a connection to the ontology database with optimized settings.

    Returns:
        sqlite3.Connection with Row factory and optimized PRAGMA settings.
    """
    from kos.ontology.engine import get_db

    conn = get_db()
    _set_pragmas(conn)
    return conn


def execute_batch(conn: sqlite3.Connection, sql: str, params_list: list[tuple[Any, ...]]) -> int:
    """Execute a batch of INSERT/UPDATE statements in a single transaction.

    Args:
        conn: Database connection.
        sql: SQL statement with placeholders.
        params_list: List of parameter tuples.

    Returns:
        Number of rows affected.
    """
    cursor = conn.cursor()
    cursor.execute("BEGIN TRANSACTION")
    try:
        for params in params_list:
            cursor.execute(sql, params)
        conn.commit()
        return cursor.rowcount
    except Exception:
        conn.rollback()
        raise
