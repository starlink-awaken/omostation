#!/usr/bin/env python3
# ruff: noqa

"""
KOS Cross-Domain Knowledge Graph Discovery v2.0

Scans indexed documents and entity files to discover:
  - Named predicates (works_at::, reports_to::, described_in::)
  - Cross-domain entity co-occurrence
  - Implicit concept mappings

Usage:
    python3 cross-domain-discovery.py              # full scan
    python3 cross-domain-discovery.py --predicates # named predicate scan
"""

import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
# sys.path.insert(0, str(SCRIPT_DIR))  # removed
from kos.config import get_vault_ops_dir  # type: ignore[unused-ignore, import-not-found]

VAULT_OPS_DIR = get_vault_ops_dir()
# sys.path.insert(0, str(VAULT_OPS_DIR))  # removed

from kos.config import get_artifact_path

# Named predicate patterns
PREDICATE_RE = re.compile(r"(\w+)::\[\[([^\]]+)\]\]")
ENTITY_RE = re.compile(r"\b(P|O|J|R|D|C):(\w[\w-]+)\b")

# Known predicates
KNOWN_PREDICATES = [
    "works_at",
    "seconded_to",
    "reports_to",
    "works_on",
    "described_in",
    "derived_from",
    "related_to",
    "conforms_to",
    "depends_on",
    "triggers",
    "member_of",
    "manages",
    "belongs_to",
    "applied_in",
]


def scan_predicates(db_path: str) -> dict:  # type: ignore[type-arg]
    """Scan indexed documents for named predicate occurrences."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    predicates_found = defaultdict(list)

    # Search for predicate patterns in document bodies
    for pred in KNOWN_PREDICATES:
        rows = conn.execute(
            """SELECT d.title, d.zone, d.canonical_path, d.body
               FROM documents d
               WHERE d.body LIKE ?
               LIMIT 30""",
            (f"%{pred}::%",),
        ).fetchall()

        for row in rows:
            body = row["body"] or ""
            matches = PREDICATE_RE.findall(body)
            for p, target in matches:
                if p == pred:
                    predicates_found[pred].append(
                        {
                            "source": {"title": row["title"], "zone": row["zone"]},
                            "target": target,
                        }
                    )

    conn.close()

    return {
        "predicates_found": {p: len(v) for p, v in predicates_found.items()},
        "total_relations": sum(len(v) for v in predicates_found.values()),
        "details": {p: v[:5] for p, v in predicates_found.items() if v},
    }


def scan_entities(db_path: str) -> dict:  # type: ignore[type-arg]
    """Find documents referencing known entity IDs."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    entity_refs = defaultdict(list)  # type: ignore[var-annotated]

    # Common entity IDs from the knowledge graph
    known_entities = [
        "P:夏同学",
        "P:柴组长",
        "P:周副主任",
        "P:沐宇组长",
        "J:数字化平台",
        "J:知识库运维",
        "J:电子病历数据质量",
        "O:房卫健委",
        "O:国转中心",
        "O:Obsidian域",
        "C:Metacog",
        "C:ALE框架",
        "R:公文/3.制度规范",
        "R:国转中心/40-政策法规",
    ]

    for entity in known_entities:
        parts = entity.split(":", 1)
        if len(parts) < 2:
            continue
        name = parts[1]

        rows = conn.execute(
            """SELECT d.title, d.zone, d.canonical_path
               FROM documents d
               WHERE d.body LIKE ? OR d.title LIKE ?
               LIMIT 10""",
            (f"%{name}%", f"%{name}%"),
        ).fetchall()

        if rows:
            entity_refs[entity] = {  # type: ignore[reportArgumentType]
                "count": len(rows),
                "documents": [{"title": r["title"], "zone": r["zone"]} for r in rows[:3]],
            }

    conn.close()

    return {"entity_references": dict(entity_refs), "entities_found": len(entity_refs)}


def discover_all() -> dict:
    try:
        db_path = get_artifact_path("retrievalDatabase")
    except Exception:  # noqa: BLE001
        return {"error": "Retrieval database not found"}

    if not db_path.exists():  # type: ignore[attr-defined]
        return {"error": "Retrieval database not found"}

    return {
        "predicates": scan_predicates(str(db_path)),
        "entities": scan_entities(str(db_path)),
    }


if __name__ == "__main__":
    result = discover_all()  # type: ignore[no-untyped-call]
    print(json.dumps(result, ensure_ascii=False, indent=2))
