#!/usr/bin/env python3
# ruff: noqa
"""KOS Weekly Report — knowledge activity summary."""

import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

from kos.config import get_artifact_path, get_workspace_manifest  # type: ignore[import-not-found]

db_path = Path(get_artifact_path("retrievalDatabase"))
if not db_path.exists():  # type: ignore[attr-defined]
    print(json.dumps({"error": "No DB"}))
    sys.exit(1)

conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row
now = datetime.now()
week_ago = (now - timedelta(days=7)).strftime("%Y%m%d")

# Recent documents (last 7 days)
recent = conn.execute(
    "SELECT title, zone FROM documents WHERE updated_at >= ? ORDER BY updated_at DESC LIMIT 10", (week_ago,)
).fetchall()

# Total by zone
zones = conn.execute("SELECT zone, COUNT(*) as cnt FROM documents GROUP BY zone").fetchall()
zone_map = {z["zone"]: z["cnt"] for z in zones}

# Entity stats
try:
    ecount = conn.execute("SELECT COUNT(*) as cnt FROM kos_entities").fetchone()["cnt"]
    rcount = conn.execute("SELECT COUNT(*) as cnt FROM kos_relations").fetchone()["cnt"]
except Exception:  # noqa: BLE001
    logger.error("Unexpected exception caught", exc_info=True)  # type: ignore[name-defined]
    ecount = rcount = 0

# Last index
last_idx = conn.execute("SELECT MAX(last_indexed) as t FROM file_fingerprints").fetchone()["t"]

conn.close()

manifest = get_workspace_manifest()
domains = manifest.get("domains", {})

report = {
    "period": f"{week_ago} ~ {now.strftime('%Y%m%d')}",
    "summary": {
        "total_documents": sum(zone_map.values()),
        "total_entities": ecount,
        "total_relations": rcount,
        "recent_activity": len(recent),
    },
    "domains": {
        info.get("description", did): zone_map.get(info.get("zoneId", did), 0) for did, info in domains.items()
    },
    "recent_documents": [{"title": r["title"], "zone": r["zone"]} for r in recent],
    "last_index": last_idx or "unknown",
    "next_health_check": "next Monday 9:00 AM",
}

print(json.dumps(report, ensure_ascii=False, indent=2))
