"""Implicit relation discovery — co-occurrence analysis for unrecorded relationships.

Adapted from SPEC-v0.1.md §4.5.
"""

from collections import deque
from typing import Any, cast


def discover_implicit_relations(threshold: int = 3) -> list[dict[str, Any]]:
    """Find undocumented entity pairs that co-occur in documents.

    Two entities appearing in the same document >= threshold times
    and without an explicit relation are suggested as related_to.
    """
    from kos.ontology.store import _get_conn  # type: ignore[import-not-found]

    conn = _get_conn()
    rows = conn.execute(
        """SELECT a.entity_id AS e1, b.entity_id AS e2, COUNT(*) AS shared_docs
        FROM kos_entity_docs a
        JOIN kos_entity_docs b ON a.doc_id = b.doc_id AND a.entity_id < b.entity_id
        WHERE NOT EXISTS (
            SELECT 1 FROM kos_relations r
            WHERE r.source_id = a.entity_id AND r.target_id = b.entity_id
        )
        GROUP BY a.entity_id, b.entity_id
        HAVING shared_docs >= ?
        ORDER BY shared_docs DESC
        LIMIT 50""",
        (threshold,),
    ).fetchall()
    conn.close()

    return [
        {"entity_1": r["e1"], "entity_2": r["e2"], "shared_docs": r["shared_docs"], "suggested": "related_to"}
        for r in rows
    ]


def shortest_path(from_id: str, to_id: str) -> list[dict[str, str]] | None:
    """BFS: find shortest relation path between two entities."""
    from kos.ontology.store import _get_conn

    conn = _get_conn()
    visited: set[str] = {from_id}
    queue: deque = deque([(from_id, [])])

    while queue:
        current, path = queue.popleft()
        rows = conn.execute(
            """SELECT source_id, relation_type, target_id FROM kos_relations
            WHERE source_id = ? UNION
            SELECT source_id, relation_type, target_id FROM kos_relations
            WHERE target_id = ?""",
            (current, current),
        ).fetchall()

        for row in rows:
            neighbor = row["target_id"] if row["source_id"] == current else row["source_id"]
            edge = {"source": row["source_id"], "relation": row["relation_type"], "target": row["target_id"]}
            if neighbor == to_id:
                conn.close()
                return cast("list[dict[str, str]] | None", path + [edge])
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [edge]))

    conn.close()
    return None
