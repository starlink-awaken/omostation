import logging
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CodeGraphAdapter:
    """Adapter for 'codegraph' - a tree-sitter based relational codebase indexer."""

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root)
        self.db_path = self.workspace_root / ".codegraph" / "index.sqlite"

    def is_indexed(self) -> bool:
        return self.db_path.exists()

    def build_index(self) -> bool:
        """Trigger codegraph to build the SQLite index using tree-sitter."""
        # Assuming the CLI tool is 'codegraph'
        try:
            logger.info("Building CodeGraph index...")
            subprocess.run(["codegraph", "index", "--dir", str(self.workspace_root)], check=True, capture_output=True)
            return True
        except FileNotFoundError:
            logger.warning(
                "codegraph CLI not found. Please install it globally (e.g. `npm i -g codegraph` or via cargo)."
            )
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to build index: {e.stderr.decode()}")
            return False

    def _query_db(self, query: str, params: tuple = ()) -> list[dict[str, Any]]:
        """Execute a query against the codegraph SQLite database."""
        if not self.is_indexed():
            if not self.build_index():
                raise RuntimeError("CodeGraph index is not available and could not be built.")

        results = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            for row in cursor.fetchall():
                results.append(dict(row))
        return results

    def get_symbol_graph(self, symbol_name: str) -> dict[str, Any]:
        """Returns a JSON tree of callers and callees for a specific symbol."""
        # Mocking the schema based on common relational graph mappers
        # In a real codegraph DB, tables might be `symbols`, `references`, `edges`
        try:
            # Placeholder query to demonstrate FTS5 / graph traversal
            rows = self._query_db(
                "SELECT * FROM edges WHERE source_symbol = ? OR target_symbol = ? LIMIT 100", (symbol_name, symbol_name)
            )
            return {
                "symbol": symbol_name,
                "edges": rows,
                "note": "This is a placeholder schema. Actual query depends on codegraph SQLite layout.",
            }
        except sqlite3.OperationalError:
            return {"error": "Schema mismatch or DB not initialized.", "symbol": symbol_name}

    def get_impact_radius(self, file_path: str) -> list[str]:
        """Returns all files that depend on the target file."""
        try:
            rows = self._query_db("SELECT DISTINCT source_file FROM imports WHERE target_file = ?", (file_path,))
            return [row["source_file"] for row in rows]
        except sqlite3.OperationalError:
            return []
