"""SQLite-backed tool catalog for MCP tool registry."""

import json
import sqlite3
from datetime import UTC, datetime

import structlog

from agora.mcp.mcp_bootstrap import get_data_dir  # type: ignore[import-not-found]

logger = structlog.get_logger(__name__)

_DB_PATH = get_data_dir() / "repository.db"


def _now():
    return datetime.now(UTC).isoformat()


class ToolCatalog:
    """SQLite-backed catalog for MCP tools with status tracking."""

    _TOOL_STATUSES = {"discovered", "installed", "loaded", "idle"}

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or str(_DB_PATH)
        self._conn: sqlite3.Connection | None = None
        self._ensure_schema()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._ensure_schema()
        return self._conn

    def _ensure_schema(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tools (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                repo_url TEXT DEFAULT '',
                tool_type TEXT DEFAULT '',
                entry TEXT DEFAULT '',
                install_path TEXT DEFAULT '',
                version TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                source TEXT DEFAULT '',
                status TEXT DEFAULT 'discovered' CHECK(status IN ('discovered','installed','loaded','idle')),
                quality_score REAL DEFAULT 0.0,
                stars INTEGER DEFAULT 0,
                first_discovered TEXT DEFAULT (datetime('now')),
                last_used TEXT DEFAULT '',
                usage_count INTEGER DEFAULT 0,
                install_error TEXT DEFAULT '',
                metadata TEXT DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_tools_status ON tools(status);
            CREATE INDEX IF NOT EXISTS idx_tools_name ON tools(name);
            CREATE INDEX IF NOT EXISTS idx_tools_quality ON tools(quality_score DESC);
        """)
        conn.commit()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        # Parse JSON fields
        if isinstance(d.get("tags"), str):
            try:
                d["tags"] = json.loads(d["tags"])
            except (json.JSONDecodeError, TypeError):
                d["tags"] = []
        if isinstance(d.get("metadata"), str):
            try:
                d["metadata"] = json.loads(d["metadata"])
            except (json.JSONDecodeError, TypeError):
                d["metadata"] = {}
        return d

    def add_tool(self, tool_info: dict) -> str:
        """Insert or update a tool in the catalog. Returns the tool ID."""
        tool_id = tool_info.get("id") or tool_info.get("name")
        if not tool_id:
            raise ValueError("tool_info must contain 'id' or 'name'")

        name = tool_info.get("name", tool_id)
        description = tool_info.get("description", "")
        repo_url = tool_info.get("repo_url", "")
        tool_type = tool_info.get("tool_type", "")
        entry = tool_info.get("entry", "")
        version = tool_info.get("version", "")
        tags = json.dumps(tool_info.get("tags", []), ensure_ascii=False)
        source = tool_info.get("source", "")
        quality_score = float(tool_info.get("quality_score", 0.0))
        stars = int(tool_info.get("stars", 0))
        metadata = json.dumps(tool_info.get("metadata", {}), ensure_ascii=False)
        now = _now()

        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO tools (
                id, name, description, repo_url, tool_type, entry,
                version, tags, source, quality_score, stars,
                first_discovered, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                repo_url = excluded.repo_url,
                tool_type = excluded.tool_type,
                entry = excluded.entry,
                version = excluded.version,
                tags = excluded.tags,
                source = excluded.source,
                quality_score = excluded.quality_score,
                stars = excluded.stars,
                first_discovered = COALESCE(tools.first_discovered, excluded.first_discovered),
                metadata = excluded.metadata
            """,
            (
                tool_id,
                name,
                description,
                repo_url,
                tool_type,
                entry,
                version,
                tags,
                source,
                quality_score,
                stars,
                now,
                metadata,
            ),
        )
        conn.commit()
        logger.info("tool_added", tool_id=tool_id, name=name)
        return tool_id

    def get_tool(self, tool_id: str) -> dict | None:
        """Fetch a single tool by ID."""
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM tools WHERE id = ?", (tool_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def list_tools(self, status: str | None = None) -> list[dict]:
        """List all tools, optionally filtered by status."""
        conn = self._get_conn()
        if status:
            rows = conn.execute(
                "SELECT * FROM tools WHERE status = ? ORDER BY quality_score DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tools ORDER BY quality_score DESC"
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def search_tools(
        self, query: str = "", status: str | None = None, limit: int = 20
    ) -> list[dict]:
        """Search tools by name/description/tags."""
        conn = self._get_conn()
        if not query:
            return self.list_tools(status)[:limit]

        like = f"%{query}%"
        if status:
            rows = conn.execute(
                "SELECT * FROM tools WHERE (name LIKE ? OR description LIKE ? OR tags LIKE ?) AND status = ? ORDER BY quality_score DESC LIMIT ?",
                (like, like, like, status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tools WHERE (name LIKE ? OR description LIKE ? OR tags LIKE ?) ORDER BY quality_score DESC LIMIT ?",
                (like, like, like, limit),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def count_by_status(self) -> dict[str, int]:
        """Return counts of tools grouped by status."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM tools GROUP BY status"
        ).fetchall()
        return {r["status"]: r["cnt"] for r in rows}

    def update_status(self, tool_id: str, status: str) -> bool:
        """Update tool status. Returns True if updated."""
        if status not in self._TOOL_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. Must be one of {self._TOOL_STATUSES}"
            )
        conn = self._get_conn()
        cur = conn.execute(
            "UPDATE tools SET status = ? WHERE id = ?", (status, tool_id)
        )
        conn.commit()
        return cur.rowcount > 0

    def record_usage(self, tool_id: str) -> bool:
        """Increment usage count and update last_used timestamp."""
        conn = self._get_conn()
        now = _now()
        cur = conn.execute(
            "UPDATE tools SET usage_count = usage_count + 1, last_used = ? WHERE id = ?",
            (now, tool_id),
        )
        conn.commit()
        return cur.rowcount > 0

    def update_quality(self, tool_id: str, score: float) -> bool:
        """Update the quality score for a tool."""
        conn = self._get_conn()
        cur = conn.execute(
            "UPDATE tools SET quality_score = ? WHERE id = ?", (score, tool_id)
        )
        conn.commit()
        return cur.rowcount > 0

    def update_entry(
        self,
        tool_id: str,
        entry: str = "",
        install_path: str = "",
        metadata: dict | None = None,
    ) -> bool:
        """Update a tool's entry point and related config after installation.

        Args:
            tool_id: Tool ID to update.
            entry: New entry point string (e.g. ``"kos.mcp.server"``).
            install_path: New install path string (e.g. ``"/usr/local/bin/tool"``).
            metadata: New metadata dict to merge (e.g. ``{"command": "my-mcp", "args": []}``).

        Returns:
            True if the tool was updated, False if the tool was not found.
        """
        conn = self._get_conn()
        if metadata:
            existing = self.get_tool(tool_id)
            if existing is None:
                return False
            current_meta = existing.get("metadata", {}) or {}
            current_meta.update(metadata)
            meta_json = json.dumps(current_meta, ensure_ascii=False)
            cur = conn.execute(
                "UPDATE tools SET entry = ?, install_path = ?, metadata = ? WHERE id = ?",
                (entry, install_path, meta_json, tool_id),
            )
        else:
            cur = conn.execute(
                "UPDATE tools SET entry = ?, install_path = ? WHERE id = ?",
                (entry, install_path, tool_id),
            )
        conn.commit()
        return cur.rowcount > 0

    def update_install(
        self, tool_id: str, install_path: str, install_error: str = ""
    ) -> bool:
        """Record installation result and set status to installed."""
        conn = self._get_conn()
        cur = conn.execute(
            "UPDATE tools SET status = 'installed', install_path = ?, install_error = ? WHERE id = ?",
            (install_path, install_error, tool_id),
        )
        conn.commit()
        return cur.rowcount > 0

    def remove_tool(self, tool_id: str) -> bool:
        """Remove a tool from the catalog."""
        conn = self._get_conn()
        cur = conn.execute("DELETE FROM tools WHERE id = ?", (tool_id,))
        conn.commit()
        return cur.rowcount > 0

    def close(self):
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
