#!/usr/bin/env python3
# ruff: noqa
"""KOS Related — smart document association discovery."""

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent

from kos.config import get_artifact_path  # type: ignore[import-not-found]


def related(query: str, limit: int = 5) -> dict:
    db_path = get_artifact_path("retrievalDatabase")
    if not db_path.exists():  # type: ignore[attr-defined]
        return {"error": "No DB"}

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Find the target document
    doc = conn.execute(
        "SELECT doc_id, title, zone, canonical_path FROM documents WHERE title LIKE ? OR doc_id = ? LIMIT 1",
        (f"%{query}%", query),
    ).fetchone()

    if not doc:
        conn.close()
        return {"error": f"Not found: {query}"}

    result: dict[str, Any] = {"document": {"title": doc["title"], "zone": doc["zone"]}, "related": []}

    # Strategy 1: Shared entities
    entities = conn.execute("SELECT entity_id FROM kos_entity_docs WHERE doc_id = ?", (doc["doc_id"],)).fetchall()
    if entities:
        eids = [e["entity_id"] for e in entities]
        placeholders = ",".join(["?"] * len(eids))
        related_docs = conn.execute(
            f"""SELECT d.title, d.zone, COUNT(*) as shared, d.doc_id
                FROM kos_entity_docs ed JOIN documents d ON ed.doc_id = d.doc_id
                WHERE ed.entity_id IN ({placeholders}) AND ed.doc_id != ?
                GROUP BY ed.doc_id ORDER BY shared DESC LIMIT ?""",
            [*eids, doc["doc_id"], limit],
        ).fetchall()
        for r in related_docs:
            result["related"].append(
                {
                    "title": r["title"],
                    "zone": r["zone"],
                    "reason": f"shared {r['shared']} entities",
                    "doc_id": r["doc_id"],
                }
            )

    # Strategy 2: FTS keyword similarity (if entity results < limit)
    if len(result["related"]) < limit:
        # Extract keywords from doc body
        body = conn.execute("SELECT body FROM documents WHERE doc_id=?", (doc["doc_id"],)).fetchone()
        keywords = []
        if body and body["body"]:
            words = body["body"].split()[:20]
            keywords = [w for w in words if len(w) > 2 and not w.startswith("[")][:3]

        for kw in keywords[:3]:
            safe_kw = kw.strip().strip('[]-,"').strip()
            if len(safe_kw) < 2:
                continue
            try:
                fts_docs = conn.execute(
                    "SELECT d.title, d.zone, d.doc_id FROM documents_fts f JOIN documents d ON f.doc_id=d.doc_id WHERE documents_fts MATCH ? AND d.doc_id!=? LIMIT 3",
                    (safe_kw, doc["doc_id"]),
                ).fetchall()
            except sqlite3.OperationalError:
                continue
            existing = {r["doc_id"] for r in result["related"]}
            for r in fts_docs:
                if r["doc_id"] not in existing and len(result["related"]) < limit:
                    result["related"].append(
                        {
                            "title": r["title"],
                            "zone": r["zone"],
                            "reason": f"keyword: {kw}",
                            "doc_id": r["doc_id"],
                        }
                    )

    conn.close()
    return result


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else ""
    print(json.dumps(related(q), ensure_ascii=False, indent=2))
