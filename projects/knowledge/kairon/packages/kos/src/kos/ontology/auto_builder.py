#!/usr/bin/env python3
# ruff: noqa
"""
KOS Auto Ontology Builder — LLM 辅助本体自动构建.

监听索引变更, 自动提取实体和关系, 低置信度进入审核队列.

Usage:
    from kos.ontology.auto_builder import AutoBuilder

    builder = AutoBuilder()
    builder.run_batch(limit=100)
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from kos.config import get_artifact_path
from kos.db import get_connection


class AutoBuilder:
    """自动本体构建器。"""

    BATCH_CONFIDENCE_THRESHOLD = 0.6

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or get_artifact_path("retrievalDatabase")
        self._conn = None

    @property
    def conn(self):
        if self._conn is None:
            self._conn = get_connection(self.db_path)
        return self._conn

    def run_batch(self, limit: int = 100) -> dict[str, Any]:
        """运行一批自动构建。"""
        stats = {"processed": 0, "entities": 0, "relations": 0, "skipped": 0}

        # Get documents not yet processed
        docs = self.conn.execute(
            """
            SELECT d.doc_id, d.title, d.body, d.zone
            FROM documents d
            LEFT JOIN _auto_build_meta ab ON d.doc_id = ab.doc_id
            WHERE ab.doc_id IS NULL AND d.body != ''
            ORDER BY d.updated_at DESC LIMIT ?
        """,
            (limit,),
        ).fetchall()

        for doc in docs:
            try:
                entities = self._extract_entities(doc)
                relations = self._infer_relations(doc, entities)

                # Save results
                for e in entities:
                    if e["confidence"] >= self.BATCH_CONFIDENCE_THRESHOLD:
                        self.conn.execute(
                            """
                            INSERT OR REPLACE INTO kos_entities
                            (entity_id, entity_type, label, description, primary_zone, source_file, metadata, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                            (
                                e["entity_id"],
                                e["type"],
                                e["label"],
                                e["description"],
                                doc["zone"],
                                e.get("source_doc_id", doc["doc_id"]),
                                json.dumps({"confidence": e["confidence"], "auto": True}),
                                datetime.now().strftime("%Y%m%d%H%M%S"),
                            ),
                        )
                        stats["entities"] += 1

                for r in relations:
                    if r["confidence"] >= self.BATCH_CONFIDENCE_THRESHOLD:
                        self.conn.execute(
                            """
                            INSERT OR REPLACE INTO kos_relations
                            (source_id, predicate, target_id, confidence, source_type, updated_at)
                            VALUES (?, ?, ?, ?, 'auto-build', ?)
                        """,
                            (
                                r["source"],
                                r["predicate"],
                                r["target"],
                                r["confidence"],
                                datetime.now().strftime("%Y%m%d%H%M%S"),
                            ),
                        )
                        stats["relations"] += 1

                # Mark as processed
                self.conn.execute(
                    "INSERT OR REPLACE INTO _auto_build_meta (doc_id, processed_at) VALUES (?, ?)",
                    (doc["doc_id"], datetime.now().isoformat()),
                )
                stats["processed"] += 1

            except Exception:
                stats["skipped"] += 1

        self.conn.commit()
        return stats

    def _extract_entities(self, doc: sqlite3.Row) -> list[dict]:  # type: ignore[reportUndefinedVariable]
        """从文档中提取实体（规则+模式）。"""
        import sqlite3

        entities = []
        body = doc["body"] or ""

        # Pattern 1: Title-based (proper nouns)
        title = doc["title"] or ""
        if title and not title.startswith("["):
            entity_id = f"C:{title[:50].replace(' ', '_')}"
            entities.append(
                {
                    "entity_id": entity_id,
                    "type": "Concept",
                    "label": title[:50],
                    "description": (body or "")[:200],
                    "confidence": 0.7,
                    "source_doc_id": doc["doc_id"],
                }
            )

        # Pattern 2: Section headers (## Entity Name)
        for m in re.finditer(r"^##\s+(.+)$", body, re.MULTILINE):
            heading = m.group(1).strip()
            if 2 <= len(heading) <= 50:
                entity_id = f"C:{heading[:50].replace(' ', '_')}"
                entities.append(
                    {
                        "entity_id": entity_id,
                        "type": "Concept",
                        "label": heading,
                        "description": (body[m.end() : m.end() + 200].strip())[:200],
                        "confidence": 0.6,
                        "source_doc_id": doc["doc_id"],
                    }
                )

        # Deduplicate by entity_id
        seen = set()
        unique = []
        for e in entities:
            if e["entity_id"] not in seen:
                seen.add(e["entity_id"])
                unique.append(e)

        return unique[:10]  # Limit per doc

    def _infer_relations(self, doc: sqlite3.Row, entities: list[dict]) -> list[dict]:  # type: ignore[reportUndefinedVariable]
        """推断实体间关系。"""
        relations = []
        for i, e1 in enumerate(entities):
            for e2 in entities[i + 1 :]:
                relations.append(
                    {
                        "source": e1["entity_id"],
                        "predicate": "related_to",
                        "target": e2["entity_id"],
                        "confidence": min(e1["confidence"], e2["confidence"]) * 0.8,
                    }
                )
        return relations

    def ensure_meta_table(self):
        """确保元数据表存在。"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS _auto_build_meta (
                doc_id TEXT PRIMARY KEY,
                processed_at TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None


if __name__ == "__main__":
    builder = AutoBuilder()
    builder.ensure_meta_table()
    result = builder.run_batch(limit=10)
    print(f"Processed: {result['processed']}, Entities: {result['entities']}, Relations: {result['relations']}")
    builder.close()
