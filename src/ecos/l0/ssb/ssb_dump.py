#!/usr/bin/env python3
"""SSB text dump for git tracking — 完整字段输出 (Phase 4 fix)"""

import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "LADS" / "ssb" / "ecos.db"
DUMP_PATH = Path(__file__).resolve().parent.parent / "LADS" / "ssb" / "ecos.jsonl"


def dump():
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    rows = db.execute(
        "SELECT id, seq, timestamp, session_id, source_agent, source_instance, "
        "target_scope, target_hint, event_type, event_subtype, summary, detail, "
        "confidence, risk_level, priority, action_req, deadline, "
        "payload_json, semantic_json, agent_signature, created_at "
        "FROM ssb_events ORDER BY seq"
    ).fetchall()

    count = 0
    with open(DUMP_PATH, "w") as f:
        for r in rows:
            event = dict(r)
            # Parse JSON fields
            if event.get("payload_json"):
                try:
                    event["payload_json"] = json.loads(event["payload_json"])
                except Exception:  # defensive fallback
                    pass
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
            count += 1

    db.close()
    print(f"Dumped {count} events to {DUMP_PATH}")


def cli_main():
    """CLI entry point for ecos-ssb-dump"""
    print("⚠️ ECOS SSB Dump 独立 CLI 已弃用，请使用 cockpit 替代", file=sys.stderr)
    dump()


if __name__ == "__main__":
    dump()
