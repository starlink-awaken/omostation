"""Entity resolution engine — sameAs detection and merging across data sources.

Adapted from SPEC-v0.1.md §4.4 to use kos.ontology._types
instead of the (not-yet-created) starlink-types package.
"""

import json
from dataclasses import dataclass
from typing import Any

from kos.ontology._types import Entity  # type: ignore[import-not-found]


@dataclass
class ResolutionCandidate:
    source_id: str
    target_id: str
    score: float
    method: str


def find_candidates(entity: Entity, threshold: float = 0.7) -> list[ResolutionCandidate]:
    from kos.ontology.store import search_entities  # type: ignore[import-not-found]

    candidates: list[ResolutionCandidate] = []

    same_label = search_entities(entity.label, limit=10)
    for other in same_label:
        if other.entity_id != entity.entity_id:
            candidates.append(
                ResolutionCandidate(
                    source_id=entity.entity_id,
                    target_id=other.entity_id,
                    score=0.9,
                    method="label_exact",
                )
            )

    if entity.aliases:
        for alias in entity.aliases:
            for other in search_entities(alias, limit=5):
                if other.entity_id != entity.entity_id:
                    candidates.append(
                        ResolutionCandidate(
                            source_id=entity.entity_id,
                            target_id=other.entity_id,
                            score=0.8,
                            method="alias_shared",
                        )
                    )

    if entity.zone:
        for other in search_entities(entity.label[:4], zone=entity.zone, limit=5):
            if other.entity_id != entity.entity_id:
                candidates.append(
                    ResolutionCandidate(
                        source_id=entity.entity_id,
                        target_id=other.entity_id,
                        score=0.6,
                        method="zone_name_fuzzy",
                    )
                )

    seen: set[tuple[str, str]] = set()
    unique: list[ResolutionCandidate] = []
    for c in sorted(candidates, key=lambda x: -x.score):
        key = (c.source_id, c.target_id)
        if key not in seen:
            seen.add(key)
            unique.append(c)

    return [c for c in unique if c.score >= threshold]


def merge_entities(source_id: str, target_id: str) -> dict[str, Any]:
    from kos.ontology.store import _get_conn

    conn = _get_conn()

    source = conn.execute("SELECT * FROM kos_entities WHERE entity_id = ?", (source_id,)).fetchone()
    if not source:
        conn.close()
        return {"error": f"Source entity not found: {source_id}"}

    target = conn.execute("SELECT * FROM kos_entities WHERE entity_id = ?", (target_id,)).fetchone()
    if not target:
        conn.close()
        return {"error": f"Target entity not found: {target_id}"}

    src_aliases = set(json.loads(source["aliases"]) if source["aliases"] else [])
    tgt_aliases = set(json.loads(target["aliases"]) if target["aliases"] else [])
    merged = src_aliases | tgt_aliases
    merged.add(source["label"])

    conn.execute(
        "UPDATE kos_entities SET aliases = ? WHERE entity_id = ?",
        (json.dumps(list(merged), ensure_ascii=False), target_id),
    )
    conn.execute("UPDATE kos_relations SET source_id = ? WHERE source_id = ?", (target_id, source_id))
    conn.execute("UPDATE kos_relations SET target_id = ? WHERE target_id = ?", (target_id, source_id))
    conn.execute("UPDATE kos_entity_docs SET entity_id = ? WHERE entity_id = ?", (target_id, source_id))
    conn.execute("DELETE FROM kos_entities WHERE entity_id = ?", (source_id,))
    conn.commit()
    conn.close()

    return {"status": "merged", "source": source_id, "target": target_id, "aliases_merged": len(merged)}
