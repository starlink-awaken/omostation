"""Ontology export — JSON-LD / Turtle serialization.

Adapted from SPEC-v0.1.md §4.6. No starlink-types dependency;
builds the knowledge object directly from kos_entities/kos_relations tables.
"""

from typing import Any


def export_jsonld(zone: str | None = None) -> dict[str, Any]:
    """Export KOS entities to JSON-LD format."""
    from kos.ontology.store import _get_conn  # type: ignore[import-not-found]

    conn = _get_conn()
    if zone:
        entities = conn.execute("SELECT * FROM kos_entities WHERE zone = ?", (zone,)).fetchall()
    else:
        entities = conn.execute("SELECT * FROM kos_entities").fetchall()
    relations = conn.execute("SELECT * FROM kos_relations").fetchall()
    conn.close()

    return {
        "@context": {
            "kos": "https://kos.xiamingxing.dev/ontology#",
            "entity": "kos:entity",
            "relation": "kos:relation",
            "label": "kos:label",
            "type": "kos:type",
        },
        "@graph": [
            {
                "@id": f"kos:{r['entity_id']}",
                "@type": "kos:Entity",
                "kos:entityType": r["entity_type"],
                "kos:label": r["label"],
                "kos:zone": r["zone"] or "",
                "kos:description": r["description"] or "",
            }
            for r in entities
        ],
        "relations": [
            {
                "source": f"kos:{r['source_id']}",
                "type": r["relation_type"],
                "target": f"kos:{r['target_id']}",
            }
            for r in relations
        ],
    }


def export_turtle(zone: str | None = None) -> str:
    """Export KOS entities to Turtle (TTL) format."""
    from kos.ontology.store import _get_conn

    conn = _get_conn()
    if zone:
        entities = conn.execute("SELECT * FROM kos_entities WHERE zone = ?", (zone,)).fetchall()
    else:
        entities = conn.execute("SELECT * FROM kos_entities").fetchall()
    relations = conn.execute("SELECT * FROM kos_relations").fetchall()
    conn.close()

    lines = [
        "@prefix kos: <https://kos.xiamingxing.dev/ontology#> .",
        "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
        "",
    ]
    for r in entities:
        lines.append(f"kos:{r['entity_id']} rdf:type kos:Entity ;")
        lines.append(f'    kos:label "{r["label"]}" ;')
        lines.append(f'    kos:entityType "{r["entity_type"]}" .')
        lines.append("")

    for r in relations:
        lines.append(f"kos:{r['source_id']} kos:{r['relation_type']} kos:{r['target_id']} .")

    return "\n".join(lines)


def export_entity_summary(zone: str | None = None) -> dict[str, Any]:
    """Return a compact summary of all entities and relations."""
    from kos.ontology.store import _get_conn

    conn = _get_conn()
    if zone:
        entities = conn.execute(
            "SELECT entity_id, entity_type, label, zone FROM kos_entities WHERE zone = ?",
            (zone,),
        ).fetchall()
    else:
        entities = conn.execute("SELECT entity_id, entity_type, label, zone FROM kos_entities").fetchall()
    conn.close()

    by_type: dict[str, list[str]] = {}
    for r in entities:
        t = r["entity_type"]
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(r["label"])
    return {"total": len(entities), "by_type": {k: len(v) for k, v in by_type.items()}}
