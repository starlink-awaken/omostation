# ---
# domain: D-Memory
# layer: organ
# status: active
# ---
from __future__ import annotations

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Sisyphus'
Layer: L3
Summary: 'ClosureTableIndex — SQLite Closure Table for O(1) ancestor/descendant queries'
Tags:
- memory
- performance
- graph
- closure-table
Authority: organs/D-Memory/AGENTS.md
---
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# ClosureTableIndex ≡ Module
# 内涵 ≝ {nodes, edges, closure}
# 外延 ≝ {e | e ∈ D-Memory ∧ implements(e, ClosureTableIndex)}
# 功能 ⊢ {O1_Ancestor_Lookup, O1_Descendant_Lookup, BFS_Path, Rebuild}
# =============================================================================

import logging
from collections import deque

from organs.D_Memory.organs.storage_dal import SQLiteRelationalProvider  # type: ignore[reportMissingImports]

_log = logging.getLogger(__name__)


class ClosureTableIndex:
    """SQLite Closure Table for O(1) ancestor/descendant graph queries.

    Schema
    ------
    nodes(id TEXT PRIMARY KEY)
    edges(parent TEXT, child TEXT, PRIMARY KEY(parent, child))
    closure(ancestor TEXT, descendant TEXT, depth INTEGER,
            PRIMARY KEY(ancestor, descendant))

    The closure table pre-computes every reachable (ancestor, descendant) pair
    so ancestor/descendant membership checks become single-row index seeks.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._db = SQLiteRelationalProvider(db_path)
        self._init_schema()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.execute("PRAGMA foreign_keys=OFF")
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY
            )
            """
        )
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS edges (
                parent TEXT NOT NULL,
                child  TEXT NOT NULL,
                PRIMARY KEY (parent, child)
            )
            """
        )
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS closure (
                ancestor   TEXT NOT NULL,
                descendant TEXT NOT NULL,
                depth      INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (ancestor, descendant)
            )
            """
        )
        self._db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_closure_ancestor
                ON closure (ancestor, depth)
            """
        )
        self._db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_closure_descendant
                ON closure (descendant, depth)
            """
        )

    def _ensure_node(self, node_id: str) -> None:
        """Insert node and its self-reference closure row if not already present."""
        self._db.execute("INSERT OR IGNORE INTO nodes (id) VALUES (?)", (node_id,))
        self._db.execute(
            "INSERT OR IGNORE INTO closure (ancestor, descendant, depth) VALUES (?, ?, 0)",
            (node_id, node_id),
        )

    def _propagate_edge(self, parent_id: str, child_id: str) -> None:
        """Propagate closure rows for a new parent→child edge."""
        self._db.execute(
            """
            INSERT OR IGNORE INTO closure (ancestor, descendant, depth)
            SELECT p.ancestor, c.descendant, p.depth + c.depth + 1
            FROM   closure p,
                   closure c
            WHERE  p.descendant = ?
              AND  c.ancestor   = ?
            """,
            (parent_id, child_id),
        )

    # ------------------------------------------------------------------
    # Mutation API
    # ------------------------------------------------------------------

    def add_node(self, node_id: str, parent_id: str | None = None) -> None:
        """Add *node_id* to the graph, optionally linking it under *parent_id*."""
        self._ensure_node(node_id)
        if parent_id is not None:
            self._ensure_node(parent_id)
            self._db.execute(
                "INSERT OR IGNORE INTO edges (parent, child) VALUES (?, ?)",
                (parent_id, node_id),
            )
            self._propagate_edge(parent_id, node_id)

    def add_edge(self, parent_id: str, child_id: str) -> None:
        """Add a directed parent→child edge (nodes are created if absent)."""
        self._ensure_node(parent_id)
        self._ensure_node(child_id)
        self._db.execute(
            "INSERT OR IGNORE INTO edges (parent, child) VALUES (?, ?)",
            (parent_id, child_id),
        )
        self._propagate_edge(parent_id, child_id)

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def get_ancestors(self, node_id: str) -> list[str]:
        """Return all ancestors of *node_id* (excluding self), sorted by depth."""
        rows = self._db.fetch_all(
            """
            SELECT ancestor FROM closure
            WHERE  descendant = ? AND depth > 0
            ORDER  BY depth ASC
            """,
            (node_id,),
        )
        return [r["ancestor"] for r in rows]

    def get_descendants(self, node_id: str) -> list[str]:
        """Return all descendants of *node_id* (excluding self), sorted by depth."""
        rows = self._db.fetch_all(
            """
            SELECT descendant FROM closure
            WHERE  ancestor = ? AND depth > 0
            ORDER  BY depth ASC
            """,
            (node_id,),
        )
        return [r["descendant"] for r in rows]

    def is_ancestor(self, ancestor_id: str, descendant_id: str) -> bool:
        """O(1) check — True iff *ancestor_id* is a (transitive) ancestor of *descendant_id*."""
        row = self._db.fetch_one(
            """
            SELECT 1 FROM closure
            WHERE  ancestor = ? AND descendant = ? AND depth > 0
            LIMIT  1
            """,
            (ancestor_id, descendant_id),
        )
        return row is not None

    def get_path(self, from_id: str, to_id: str) -> list[str] | None:
        """BFS shortest path from *from_id* to *to_id*; returns None if unreachable."""
        if from_id == to_id:
            return [from_id]
        # Build in-memory adjacency list from edges table for BFS
        edge_rows = self._db.fetch_all("SELECT parent, child FROM edges")
        adj: dict[str, list[str]] = {}
        for row in edge_rows:
            adj.setdefault(row["parent"], []).append(row["child"])

        visited: set[str] = {from_id}
        queue: deque[list[str]] = deque([[from_id]])
        while queue:
            path = queue.popleft()
            current = path[-1]
            for neighbour in adj.get(current, []):
                if neighbour == to_id:
                    return path + [neighbour]
                if neighbour not in visited:
                    visited.add(neighbour)
                    queue.append(path + [neighbour])
        return None

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def node_count(self) -> int:
        row = self._db.fetch_one("SELECT COUNT(*) FROM nodes")
        return row["COUNT(*)"] if row else 0

    def edge_count(self) -> int:
        row = self._db.fetch_one("SELECT COUNT(*) FROM edges")
        return row["COUNT(*)"] if row else 0

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def rebuild_index(self) -> None:
        """Rebuild the closure table from scratch using the raw edges table."""
        # Clear existing closure rows
        self._db.execute("DELETE FROM closure")
        # Re-seed self-references for all nodes
        self._db.execute("INSERT OR IGNORE INTO closure (ancestor, descendant, depth) SELECT id, id, 0 FROM nodes")
        # Re-propagate all edges in insertion order
        edge_rows = self._db.fetch_all("SELECT parent, child FROM edges")
        for row in edge_rows:
            self._propagate_edge(row["parent"], row["child"])

    def close(self) -> None:
        """Close the SQLite connection."""
        self._db.disconnect()
