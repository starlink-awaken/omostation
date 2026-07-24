"""ECOS 持久化工具"""

import json
import sqlite3
from typing import Any, Optional


class StatePersistence:
    """状态持久化管理器"""

    def __init__(self, db_path: str = "ecos_state.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def save(self, key: str, value: Any) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)",
                    (key, json.dumps(value)),
                )
            return True
        except Exception:  # defensive fallback
            return False

    def load(self, key: str) -> Optional[Any]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT value FROM state WHERE key = ?", (key,))
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
        except Exception:  # defensive fallback
            pass
        return None

    def delete(self, key: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM state WHERE key = ?", (key,))
            return True
        except Exception:  # defensive fallback
            return False

    def list_keys(self) -> list[str]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT key FROM state")
                return [row[0] for row in cursor.fetchall()]
        except Exception:  # defensive fallback
            return []
