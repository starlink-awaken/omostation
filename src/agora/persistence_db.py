"""SQLite-based persistence — drop-in replacement for JSON file persistence.

Provides the same json_load/json_save interface backed by SQLite for:
- Concurrent safety (WAL mode)
- Atomic writes (single transaction)
- Indexed queries
- Auto-migration from existing JSON files
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import structlog

from agora.mcp.mcp_bootstrap import get_data_dir  # type: ignore[import-not-found]

logger = structlog.get_logger(__name__)

_DB_PATH = get_data_dir() / "agora.db"


def _get_db(db_path: str | None = None) -> sqlite3.Connection:
    """Get or create the SQLite database connection."""
    path = db_path or str(_DB_PATH)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS kv_store (  key TEXT PRIMARY KEY,  value TEXT NOT NULL,  updated_at TEXT DEFAULT (datetime('now')))"
    )
    return conn


def json_load(file_path: str | Path, default=None) -> dict | list:
    """Load JSON data from SQLite keyed by file path.

    Auto-migrates from existing JSON file on first access.
    """
    key = str(Path(file_path).name)
    conn = _get_db(str(Path(file_path).parent / "agora.db"))
    try:
        row = conn.execute(
            "SELECT value FROM kv_store WHERE key = ?", (key,)
        ).fetchone()
        if row:
            return json.loads(row[0])
    except Exception as e:
        logger.warning("persistence_db_load_failed", key=key, error=str(e))

    # Auto-migrate from JSON file (copy, don't rename — preserve original)
    json_path = Path(file_path)
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text())
            json_save(file_path, data)
            # Keep original JSON intact; do NOT rename to .bak
            return data
        except Exception:
            pass
    return default if default is not None else {}


def json_save(file_path: str | Path, data: dict | list) -> bool:
    """Save data to SQLite keyed by file path. Returns True on success."""
    key = str(Path(file_path).name)
    conn = _get_db(str(Path(file_path).parent / "agora.db"))
    try:
        conn.execute(
            "INSERT OR REPLACE INTO kv_store (key, value, updated_at) VALUES (?, ?, datetime('now'))",
            (key, json.dumps(data, ensure_ascii=False, default=str)),
        )
        conn.commit()
        return True
    except Exception as e:
        logger.warning("persistence_db_save_failed", key=key, error=str(e))
        return False
