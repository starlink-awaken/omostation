# ---
# domain: workflows
# layer: tool
# status: active
# ---
"""Inject external facts into FactGraph database.

Migrated from SharedBrain-code/workflows/perception/fact_injector.py to KOS kairon.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

# Database location: follows kairon's ~/.kos/ convention
DB_PATH = str(Path.home() / ".kos" / "perception" / "fact_graph.db")


def _serialize_metadata(value: Any) -> str:
    if value is None:
        return json.dumps({"source": "web"})
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def inject_facts(external_data: list[dict]) -> int:
    conn = sqlite3.connect(DB_PATH)
    count = 0
    try:
        for fact in external_data:
            if not _validate_fact(fact):
                continue
            fact_id = str(uuid.uuid4())[:8]
            meta = _serialize_metadata(fact.get("metadata"))
            ts = datetime.now(UTC).isoformat()
            cursor = conn.execute(
                "INSERT OR IGNORE INTO fact_triples (id, sub, pred, obj, metadata, source_node_id, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (fact_id, fact["sub"], fact["pred"], fact["obj"], meta, "perception_web", ts),
            )
            if cursor.rowcount > 0:
                count += 1
        conn.commit()
    finally:
        conn.close()
    return count


def _validate_fact(fact: dict) -> bool:
    return bool(fact.get("sub") and fact.get("pred") and fact.get("obj"))
