#!/usr/bin/env python3
# ruff: noqa
"""KOS Ontology Infer — 关系推理 + 治理规则推导.

从 ontology/engine.py 抽出 (God Module 拆分 wave 2, engine.py 769->~640).
含 infer() (predicate::[[target]] 关系推断) + _reason_governance_rules() (L0 层级/X4 规则推理).
依赖 schema 组 (get_db/init_schema/PREDICATE_RE/KNOWN_PREDICATES).
"""

import json
import sqlite3
from datetime import datetime
from typing import Any

from kos.ontology.schema import (  # type: ignore[no-redef]
    KNOWN_PREDICATES,
    PREDICATE_RE,
    get_db,
    init_schema,
)


def infer() -> dict[str, Any]:  # type: ignore[no-untyped-def]
    conn = get_db()  # type: ignore[no-untyped-call]
    init_schema(conn)  # type: ignore[no-untyped-call]
    now = datetime.now().strftime("%Y%m%d%H%M%S")

    # Get all entity labels for matching
    entities = {
        r["entity_id"]: json.loads(r["aliases"] or "[]") + [r["label"]]
        for r in conn.execute("SELECT entity_id,label,aliases FROM kos_entities").fetchall()
    }

    if not entities:
        conn.close()
        return {"inferred": 0, "error": "No entities extracted yet. Run 'extract' first."}

    # Scan all indexed documents for predicate::[[target]] patterns
    inferred = 0
    docs = conn.execute("SELECT doc_id,canonical_path,body FROM documents WHERE body != ''").fetchall()

    for doc in docs:
        body = doc["body"] or ""
        for m in PREDICATE_RE.finditer(body):
            predicate = m.group(1)
            if predicate not in KNOWN_PREDICATES:
                continue
            target_raw = m.group(2)

            # Match target against known entities
            best_match = None
            best_conf = 0
            for eid, aliases in entities.items():
                for alias in aliases:
                    if alias in target_raw or target_raw in alias:
                        score = len(alias) / max(len(target_raw), 1)
                        if score > best_conf:
                            best_conf = score  # type: ignore[assignment]
                            best_match = eid

            if best_match and best_conf > 0.3:
                # Find source entity from doc associations
                source_ents = conn.execute(
                    "SELECT entity_id FROM kos_entity_docs WHERE doc_id=?", (doc["doc_id"],)
                ).fetchall()
                if not source_ents:
                    continue
                source_id = source_ents[0]["entity_id"]
                confidence = min(best_conf, 0.8)  # cap auto-extracted confidence

                conn.execute(
                    """INSERT OR REPLACE INTO kos_relations
                    (source_id,predicate,target_id,confidence,source_doc,source_type,updated_at)
                    VALUES (?,?,?,?,?,?,?)""",
                    (source_id, predicate, best_match, confidence, doc["canonical_path"], "auto-extract", now),
                )
                conn.execute(
                    """INSERT OR REPLACE INTO kos_entity_docs
                    (entity_id,doc_id,relevance) VALUES (?,?,?)""",
                    (best_match, doc["doc_id"], confidence),
                )
                inferred += 1

    # 5. Semantic reasoning on L0 architecture & X-axis governance checks
    inferred += _reason_governance_rules(conn, now)

    conn.commit()
    conn.close()
    return {"inferred": inferred, "timestamp": now}


def _reason_governance_rules(conn: sqlite3.Connection, now: str) -> int:
    """结合 L0 层级架构与 X 层一致性规则进行本体推理推导"""
    inferred = 0

    # 1. L0 层级依赖冲突推导
    layer_weights = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4, "I0": 5, "M0": 6, "X": 7}

    rows = conn.execute(
        """SELECT r.source_id as proj, r.target_id as layer_concept
           FROM kos_relations r
           WHERE r.predicate='member_of' AND r.source_id LIKE 'J:%' AND r.target_id LIKE 'C:Layer-%'"""
    ).fetchall()

    proj_layers = {}
    for r in rows:
        proj = r["proj"]
        layer_concept = r["layer_concept"]
        layer_name = layer_concept.replace("C:Layer-", "")
        if layer_name in layer_weights:
            proj_layers[proj] = layer_name

    dep_rows = conn.execute(
        """SELECT source_id, predicate, target_id FROM kos_relations
           WHERE source_id LIKE 'J:%' AND target_id LIKE 'J:%' AND predicate != 'violates_layer_dependency'"""
    ).fetchall()

    for dep in dep_rows:
        src = dep["source_id"]
        tgt = dep["target_id"]
        src_layer = proj_layers.get(src)
        tgt_layer = proj_layers.get(tgt)

        if src_layer and tgt_layer:
            # 如果源层级优先级值低于目标层级（即逆向引用，如 L1 引用 L3），说明发生了架构设计违规！
            if layer_weights[src_layer] < layer_weights[tgt_layer]:
                conn.execute(
                    """INSERT OR REPLACE INTO kos_relations
                    (source_id,predicate,target_id,confidence,source_doc,source_type,updated_at)
                    VALUES (?,?,?,?,?,?,?)""",
                    (src, "violates_layer_dependency", tgt, 0.95, "ontology-rules", "reasoning", now),
                )
                inferred += 1

    # 2. X4 规则链审计：找出所有未绑定 ADR 决策的 Axiom 规则
    axioms = conn.execute("SELECT entity_id, label FROM kos_entities WHERE entity_type='Axiom'").fetchall()
    for ax in axioms:
        ax_id = ax["entity_id"]
        has_adr = conn.execute(
            "SELECT 1 FROM kos_relations WHERE source_id=? AND predicate='related_to' AND target_id LIKE 'D:ADR-%'",
            (ax_id,),
        ).fetchone()

        if not has_adr:
            conn.execute(
                """INSERT OR REPLACE INTO kos_relations
                (source_id,predicate,target_id,confidence,source_doc,source_type,updated_at)
                VALUES (?,?,?,?,?,?,?)""",
                (ax_id, "lacks_adr_evidence", "A:CR-X4-HEALTH-SSOT", 0.9, "ontology-rules", "reasoning", now),
            )
            inferred += 1

    return inferred
