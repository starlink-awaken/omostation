"""KOS Self DB — SQLite persistence with version history.

Tables:
  profile — key-value store (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)
  changelog — version history (id, ts, field, old_value, new_value)

File location: ~/.kos/self/self.db
Backward compat: also writes profile.json for scripts that read it directly.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

SELF_DIR = Path.home() / ".kos" / "self"
DB_PATH = SELF_DIR / "self.db"
JSON_PATH = SELF_DIR / "profile.json"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ensure_db() -> None:
    """Auto-create tables if they don't exist."""
    SELF_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS profile (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS changelog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                field TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT
            )"""
        )
        conn.commit()
    finally:
        conn.close()


def _get_conn() -> sqlite3.Connection:
    """Get a read-write connection (auto-commits on close)."""
    _ensure_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


# ---------------------------------------------------------------------------
# Profile CRUD
# ---------------------------------------------------------------------------


def _profile_key(field: str) -> str:
    """Return the profile key for a top-level field name."""
    return f"profile:{field}"


def load_profile() -> dict[str, Any]:
    """Load full profile dict from SQLite. Returns empty dict if empty."""
    _ensure_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT key, value FROM profile").fetchall()
        if not rows:
            return {}
        data: dict[str, Any] = {}
        for row in rows:
            raw_key: str = row["key"]
            # strip "profile:" prefix
            field = raw_key[len("profile:") :] if raw_key.startswith("profile:") else raw_key
            try:
                data[field] = json.loads(row["value"])
            except (json.JSONDecodeError, TypeError):
                data[field] = row["value"]
        return data
    finally:
        conn.close()


def save_profile(data: dict[str, Any]) -> None:
    """Upsert each top-level key into SQLite profile table + write JSON for compat."""
    _ensure_db()
    now = datetime.now().isoformat()
    conn = sqlite3.connect(str(DB_PATH))
    try:
        for key, value in data.items():
            raw_key = _profile_key(key)
            serialized = json.dumps(value, ensure_ascii=False)
            conn.execute(
                """INSERT INTO profile (key, value, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
                (raw_key, serialized, now),
            )
        conn.commit()
    finally:
        conn.close()

    # Backward compat: write JSON
    _write_json_backup(data)


def _write_json_backup(data: dict[str, Any]) -> None:
    """Write full profile dict to profile.json for scripts that read it directly."""
    SELF_DIR.mkdir(parents=True, exist_ok=True)
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Changelog
# ---------------------------------------------------------------------------


def record_change(field: str, old_val: Any, new_val: Any) -> None:
    """Insert a change record into the changelog."""
    _ensure_db()
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute(
            "INSERT INTO changelog (ts, field, old_value, new_value) VALUES (?, ?, ?, ?)",
            (
                datetime.now().isoformat(),
                field,
                json.dumps(old_val, ensure_ascii=False),
                json.dumps(new_val, ensure_ascii=False),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_profile_history(limit: int = 20) -> list[dict[str, Any]]:
    """Return the most recent changelog entries, newest first."""
    _ensure_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, ts, field, old_value, new_value FROM changelog ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            entry = {
                "id": row["id"],
                "ts": row["ts"],
                "field": row["field"],
            }
            try:
                entry["old_value"] = json.loads(row["old_value"]) if row["old_value"] else None
            except (json.JSONDecodeError, TypeError):
                entry["old_value"] = row["old_value"]
            try:
                entry["new_value"] = json.loads(row["new_value"]) if row["new_value"] else None
            except (json.JSONDecodeError, TypeError):
                entry["new_value"] = row["new_value"]
            result.append(entry)
        return result
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


def migrate_from_json() -> bool:
    """If profile.json exists and SQLite is empty, import it. Returns True if migrated."""
    if not JSON_PATH.exists():
        return False

    _ensure_db()
    conn = sqlite3.connect(str(DB_PATH))
    try:
        count = conn.execute("SELECT COUNT(*) FROM profile").fetchone()[0]
        if count > 0:
            return False  # already populated
    finally:
        conn.close()

    # Read JSON and write to SQLite
    try:
        with open(JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return False

    save_profile(data)

    # Record initial migration changelog
    for key in data:
        record_change(key, None, data[key])

    return True
