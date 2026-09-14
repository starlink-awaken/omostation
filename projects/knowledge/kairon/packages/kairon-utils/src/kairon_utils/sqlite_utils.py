"""Minimal sqlite_utils replacement for kairon_lib (standalone operation)."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager


@contextmanager
def managed_connection(conn: sqlite3.Connection) -> Generator[sqlite3.Connection]:
    """Context manager that yields a sqlite3 connection and closes it on exit."""
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
