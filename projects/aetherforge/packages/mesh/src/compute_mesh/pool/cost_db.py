"""CostDB — SQLite-backed cost storage for structured queries.

Provides:
  - Persistent cost records in SQLite
  - Aggregation queries (per node, per model, per time range)
  - JSONL shadow writes (for log tailing and backwards compat)

Usage::

    from compute_mesh.pool.cost_db import CostDB

    db = CostDB()
    db.record("ollama-local", "llama3", 100, 50, 0.001)
    report = db.get_report()
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path.home() / ".aetherforge" / "cost.db"
DEFAULT_JSONL_PATH = Path.home() / ".aetherforge" / "cost.jsonl"


class CostDB:
    """SQLite-backed cost database with JSONL shadow writes.

    Dual-write strategy:
      - **SQLite**: structured storage for queries and aggregation
      - **JSONL**: append-only log for tailing and backwards compatibility
    """

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
        jsonl_path: str | Path = DEFAULT_JSONL_PATH,
    ) -> None:
        self._db_path = Path(db_path)
        self._jsonl_path = Path(jsonl_path)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the SQLite schema."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._jsonl_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self._db_path))
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS cost_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                ts_iso TEXT NOT NULL,
                node_id TEXT NOT NULL,
                model TEXT NOT NULL DEFAULT '',
                prompt_tokens INTEGER NOT NULL DEFAULT 0,
                completion_tokens INTEGER NOT NULL DEFAULT 0,
                cost_input REAL NOT NULL DEFAULT 0.0,
                cost_output REAL NOT NULL DEFAULT 0.0,
                total_cost REAL NOT NULL DEFAULT 0.0
            )
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_cost_records_ts
            ON cost_records(ts)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_cost_records_node
            ON cost_records(node_id)
        """)
        conn.commit()
        conn.close()

    # ── Record ─────────────────────────────────────────────────────────────---

    def record(
        self,
        node_id: str,
        model: str = "",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_cost: float = 0.0,
        cost_input: float = 0.0,
        cost_output: float = 0.0,
    ) -> None:
        """Record a cost entry (SQLite + JSONL dual write)."""
        now = time.time()
        ts_iso = datetime.now(UTC).isoformat()

        # SQLite
        try:
            conn = sqlite3.connect(str(self._db_path))
            c = conn.cursor()
            c.execute(
                """INSERT INTO cost_records
                   (ts, ts_iso, node_id, model, prompt_tokens,
                    completion_tokens, cost_input, cost_output, total_cost)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (now, ts_iso, node_id, model, prompt_tokens,
                 completion_tokens, cost_input, cost_output, total_cost),
            )
            conn.commit()
            conn.close()
        except Exception:
            _log.exception("Failed to write cost to SQLite")

        # JSONL shadow write
        try:
            entry = {
                "ts": ts_iso,
                "node_id": node_id,
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cost_input": round(cost_input, 6),
                "cost_output": round(cost_output, 6),
                "total_cost": round(total_cost, 6),
            }
            line = (json.dumps(entry, ensure_ascii=False) + "\n").encode("utf-8")
            fd = os.open(str(self._jsonl_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
            try:
                os.write(fd, line)
            finally:
                os.close(fd)
        except Exception:
            _log.exception("Failed to write cost JSONL")

    # ── Queries ──────────────────────────────────────────────────────────────

    def get_report(
        self,
        since: float | None = None,
        until: float | None = None,
        node_id: str | None = None,
    ) -> dict[str, Any]:
        """Get aggregated cost report with optional filters."""
        conditions = []
        params: list[Any] = []

        if since is not None:
            conditions.append("ts >= ?")
            params.append(since)
        if until is not None:
            conditions.append("ts <= ?")
            params.append(until)
        if node_id:
            conditions.append("node_id = ?")
            params.append(node_id)

        where = " AND ".join(conditions) if conditions else "1=1"

        conn = sqlite3.connect(str(self._db_path))
        c = conn.cursor()

        # Totals
        c.execute(
            f"""SELECT
                   COUNT(*) as total_requests,
                   COALESCE(SUM(prompt_tokens), 0) as total_prompt_tokens,
                   COALESCE(SUM(completion_tokens), 0) as total_completion_tokens,
                   COALESCE(SUM(total_cost), 0.0) as total_cost
               FROM cost_records WHERE {where}""",
            params,
        )
        row = c.fetchone()
        totals = {
            "total_requests": row[0],
            "total_prompt_tokens": row[1],
            "total_completion_tokens": row[2],
            "total_cost": round(row[3], 6),
        }

        # Per node breakdown
        c.execute(
            f"""SELECT
                   node_id,
                   COUNT(*) as requests,
                   COALESCE(SUM(total_cost), 0.0) as cost
               FROM cost_records WHERE {where}
               GROUP BY node_id ORDER BY cost DESC""",
            params,
        )
        per_node = {row[0]: {"requests": row[1], "cost": round(row[2], 6)} for row in c.fetchall()}

        conn.close()

        return {
            **totals,
            "per_node": per_node,
            "db_path": str(self._db_path),
            "jsonl_path": str(self._jsonl_path),
        }

    def get_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return the most recent *limit* cost records."""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(
            """SELECT * FROM cost_records
               ORDER BY id DESC LIMIT ?""",
            (limit,),
        )
        rows = [dict(row) for row in c.fetchall()]
        conn.close()
        return rows

    def get_total_cost(self) -> float:
        """Return the total cost across all records."""
        conn = sqlite3.connect(str(self._db_path))
        c = conn.cursor()
        c.execute("SELECT COALESCE(SUM(total_cost), 0.0) FROM cost_records")
        val = c.fetchone()[0]
        conn.close()
        return val

    def get_node_count(self) -> int:
        """Return the number of distinct nodes with cost records."""
        conn = sqlite3.connect(str(self._db_path))
        c = conn.cursor()
        c.execute("SELECT COUNT(DISTINCT node_id) FROM cost_records")
        val = c.fetchone()[0]
        conn.close()
        return val

    def clear(self) -> None:
        """Delete all cost records."""
        conn = sqlite3.connect(str(self._db_path))
        c = conn.cursor()
        c.execute("DELETE FROM cost_records")
        conn.commit()
        conn.close()
