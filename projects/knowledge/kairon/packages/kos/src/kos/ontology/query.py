#!/usr/bin/env python3
# ruff: noqa
"""KOS Ontology Query — 实体卡片/图谱/路径/去重/时间线/列表.

从 ontology/engine.py 抽出 (God Module 拆 wave 4, engine.py 512->~205).
含 card/_entity_graph_2hop/find_path/deduplicate_entities/entity_timeline/list_entities.
依赖 schema 组 (get_db/init_schema).
"""

import json
import sqlite3
from collections import deque
from typing import Any

from kos.ontology.schema import (  # type: ignore[no-redef]
    get_db,
    init_schema,
)


def card(entity_id: str) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    conn = get_db()  # type: ignore[no-untyped-call]
    init_schema(conn)  # type: ignore[no-untyped-call]

    entity = conn.execute("SELECT * FROM kos_entities WHERE entity_id=?", (entity_id,)).fetchone()
    if not entity:
        conn.close()
        return {"error": f"Entity not found: {entity_id}"}

    # Outgoing relations
    outgoing = conn.execute(
        "SELECT predicate,target_id,confidence,source_doc FROM kos_relations WHERE source_id=?", (entity_id,)
    ).fetchall()

    # Incoming relations
    incoming = conn.execute(
        "SELECT source_id,predicate,confidence,source_doc FROM kos_relations WHERE target_id=?", (entity_id,)
    ).fetchall()

    # Document count by zone
    doc_zones = conn.execute(
        """SELECT d.zone, COUNT(*) as cnt
           FROM kos_entity_docs ed JOIN documents d ON ed.doc_id=d.doc_id
           WHERE ed.entity_id=? GROUP BY d.zone""",
        (entity_id,),
    ).fetchall()

    # Enhanced: Document list (top 20 most relevant)
    doc_list = conn.execute(
        """SELECT d.doc_id, d.title, d.zone, d.canonical_path, d.updated_at, ed.relevance
           FROM kos_entity_docs ed JOIN documents d ON ed.doc_id=d.doc_id
           WHERE ed.entity_id=? ORDER BY ed.relevance DESC, d.updated_at DESC LIMIT 20""",
        (entity_id,),
    ).fetchall()

    # Enhanced: Entity graph (all entities within 2 hops)
    entity_graph = _entity_graph_2hop(conn, entity_id)

    # Enhanced: Related entities (co-occurring in same docs)
    related_entities = conn.execute(
        """SELECT e2.entity_id, e2.label, e2.entity_type, COUNT(*) as shared_docs
           FROM kos_entity_docs ed1
           JOIN kos_entity_docs ed2 ON ed1.doc_id = ed2.doc_id AND ed1.entity_id != ed2.entity_id
           JOIN kos_entities e2 ON ed2.entity_id = e2.entity_id
           WHERE ed1.entity_id = ?
           GROUP BY e2.entity_id ORDER BY shared_docs DESC LIMIT 10""",
        (entity_id,),
    ).fetchall()

    conn.close()

    return {
        "entity_id": entity["entity_id"],
        "entity_type": entity["entity_type"],
        "label": entity["label"],
        "aliases": json.loads(entity["aliases"] or "[]"),
        "description": entity["description"],
        "primary_zone": entity["primary_zone"],
        "outgoing_relations": [
            {"predicate": r["predicate"], "target": r["target_id"], "confidence": r["confidence"]} for r in outgoing
        ],
        "incoming_relations": [
            {"source": r["source_id"], "predicate": r["predicate"], "confidence": r["confidence"]} for r in incoming
        ],
        "document_zones": {r["zone"]: r["cnt"] for r in doc_zones},
        "total_docs": sum(r["cnt"] for r in doc_zones),
        "documents": [
            {
                "doc_id": d["doc_id"],
                "title": d["title"],
                "zone": d["zone"],
                "canonical_path": d["canonical_path"],
                "updated_at": d["updated_at"],
                "relevance": d["relevance"],
            }
            for d in doc_list
        ],
        "entity_graph": entity_graph,
        "related_entities": [
            {
                "entity_id": r["entity_id"],
                "label": r["label"],
                "type": r["entity_type"],
                "shared_docs": r["shared_docs"],
            }
            for r in related_entities
        ],
    }


def _entity_graph_2hop(conn: sqlite3.Connection, entity_id: str) -> dict[str, Any]:
    """Get the entity graph within 2 hops of the given entity."""
    neighbors_1 = conn.execute(
        """SELECT DISTINCT target_id as entity_id FROM kos_relations WHERE source_id = ?
           UNION
           SELECT DISTINCT source_id as entity_id FROM kos_relations WHERE target_id = ?""",
        (entity_id, entity_id),
    ).fetchall()

    neighbor_ids = {r["entity_id"] for r in neighbors_1}
    neighbor_ids.add(entity_id)

    if neighbor_ids:
        placeholders = ",".join(["?"] * len(neighbor_ids))
        neighbors_2 = conn.execute(
            f"""SELECT DISTINCT target_id as entity_id FROM kos_relations
                WHERE source_id IN ({placeholders}) AND target_id NOT IN ({placeholders})
                UNION
                SELECT DISTINCT source_id as entity_id FROM kos_relations
                WHERE target_id IN ({placeholders}) AND source_id NOT IN ({placeholders})""",
            list(neighbor_ids) * 4,
        ).fetchall()
        for r in neighbors_2:
            neighbor_ids.add(r["entity_id"])

    if not neighbor_ids:
        return {"nodes": [], "edges": []}

    placeholders = ",".join(["?"] * len(neighbor_ids))
    nodes = conn.execute(
        f"SELECT entity_id, entity_type, label FROM kos_entities WHERE entity_id IN ({placeholders})",
        list(neighbor_ids),
    ).fetchall()

    edges = conn.execute(
        f"""SELECT source_id, predicate, target_id FROM kos_relations
            WHERE source_id IN ({placeholders}) AND target_id IN ({placeholders})""",
        list(neighbor_ids) * 2,
    ).fetchall()

    return {
        "nodes": [{"id": n["entity_id"], "type": n["entity_type"], "label": n["label"]} for n in nodes],
        "edges": [{"source": e["source_id"], "predicate": e["predicate"], "target": e["target_id"]} for e in edges],
    }


def find_path(from_id: str, to_id: str) -> dict[str, Any] | None:  # type: ignore[no-untyped-def]
    conn = get_db()  # type: ignore[no-untyped-call]
    edges = conn.execute("SELECT source_id,predicate,target_id FROM kos_relations").fetchall()
    conn.close()

    adj: dict[str, list[tuple[str, str]]] = {}
    for s, p, t in edges:
        adj.setdefault(s, []).append((t, p))

    queue = deque([(from_id, [])])  # type: ignore[var-annotated]
    visited = {from_id}

    while queue:
        node, path = queue.popleft()
        if node == to_id:
            return {"path": path, "hops": len(path)}
        for neighbor, predicate in adj.get(node, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [{"from": node, "predicate": predicate, "to": neighbor}]))

    return {"error": f"No path found between {from_id} and {to_id}"}


def deduplicate_entities() -> dict[str, Any]:
    """Merge duplicate entities based on label similarity."""
    conn = get_db()  # type: ignore[no-untyped-call]
    init_schema(conn)  # type: ignore[no-untyped-call]

    duplicates = conn.execute("""
        SELECT LOWER(label) as low_label, COUNT(*) as cnt,
               GROUP_CONCAT(entity_id, '|||') as ids,
               GROUP_CONCAT(entity_type, '|||') as types
        FROM kos_entities
        GROUP BY LOWER(label)
        HAVING cnt > 1
    """).fetchall()

    merged = 0
    for dup in duplicates:
        ids = dup["ids"].split("|||")
        # Keep the first entity, merge others into it
        canonical_id = ids[0]
        for other_id in ids[1:]:
            conn.execute("UPDATE OR IGNORE kos_relations SET target_id=? WHERE target_id=?", (canonical_id, other_id))
            conn.execute("UPDATE OR IGNORE kos_relations SET source_id=? WHERE source_id=?", (canonical_id, other_id))
            conn.execute("UPDATE OR IGNORE kos_entity_docs SET entity_id=? WHERE entity_id=?", (canonical_id, other_id))
            conn.execute("DELETE FROM kos_entities WHERE entity_id=?", (other_id,))
            merged += 1

    conn.commit()
    conn.close()

    return {
        "duplicate_groups": len(duplicates),
        "entities_merged": merged,
    }


def entity_timeline(entity_id: str) -> dict[str, Any]:
    """Get the timeline of an entity based on document creation dates."""
    conn = get_db()  # type: ignore[no-untyped-call]
    init_schema(conn)  # type: ignore[no-untyped-call]

    entity = conn.execute("SELECT * FROM kos_entities WHERE entity_id=?", (entity_id,)).fetchone()
    if not entity:
        conn.close()
        return {"error": f"Entity not found: {entity_id}"}

    timeline = conn.execute(
        """SELECT d.title, d.zone, d.canonical_path, d.created_at, d.updated_at, ed.relevance,
                  SUBSTR(d.body, 1, 200) as snippet
           FROM kos_entity_docs ed
           JOIN documents d ON ed.doc_id = d.doc_id
           WHERE ed.entity_id = ?
           ORDER BY d.created_at DESC""",
        (entity_id,),
    ).fetchall()

    conn.close()

    return {
        "entity_id": entity_id,
        "label": entity["label"],
        "entity_type": entity["entity_type"],
        "total_docs": len(timeline),
        "timeline": [
            {
                "title": t["title"],
                "zone": t["zone"],
                "canonical_path": t["canonical_path"],
                "created_at": t["created_at"],
                "updated_at": t["updated_at"],
                "relevance": t["relevance"],
                "snippet": t["snippet"],
            }
            for t in timeline
        ],
    }


def list_entities(entity_type: str | None = None) -> dict:
    conn = get_db()  # type: ignore[no-untyped-call]
    init_schema(conn)  # type: ignore[no-untyped-call]
    if entity_type:
        rows = conn.execute(
            "SELECT entity_id,entity_type,label,primary_zone FROM kos_entities WHERE entity_type=? ORDER BY entity_type,label",
            (entity_type.capitalize(),),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT entity_id,entity_type,label,primary_zone FROM kos_entities ORDER BY entity_type,label"
        ).fetchall()
    conn.close()
    return {"entities": [dict(r) for r in rows], "count": len(rows)}
