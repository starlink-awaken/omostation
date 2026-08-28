#!/usr/bin/env python3
"""Memory OS 语义 Diff 提取与自适应偏好更新引擎"""
import difflib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

def extract_semantic_diff(draft_text: str, final_text: str) -> dict:
    matcher = difflib.SequenceMatcher(None, draft_text, final_text)
    extracted_rules = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "replace":
            extracted_rules.append(f"当原拟包含「{draft_text[i1:i2]}」时，优先替换为「{final_text[j1:j2]}」")
    return {
        "change_count": len(extracted_rules),
        "similarity": round(matcher.ratio(), 4),
        "extracted_rules": extracted_rules,
    }

def record_signature_diff(entity_id: str, domain: str, draft_text: str, final_text: str,
                          db_path: Path | None = None, pref_file: Path | None = None) -> dict:
    diff_data = extract_semantic_diff(draft_text, final_text)
    db = db_path or (Path("/Users/xiamingxing/Workspace/.omo/state/memory") / "diff-ledger.db")
    db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS diff_records (
                id TEXT PRIMARY KEY, domain TEXT, draft TEXT, final TEXT, rules TEXT, created_at TEXT
            )
        """)
        conn.execute("""
            INSERT OR REPLACE INTO diff_records VALUES (?, ?, ?, ?, ?, ?)
        """, (entity_id, domain, draft_text, final_text, json.dumps(diff_data["extracted_rules"], ensure_ascii=False), datetime.now(timezone.utc).isoformat()))
        conn.commit()

    if diff_data["extracted_rules"]:
        pref = pref_file or Path("/Users/xiamingxing/Documents/_entities/facts/preferences.md")
        pref.parent.mkdir(parents=True, exist_ok=True)
        with open(pref, "a", encoding="utf-8") as f:
            f.write(f"\n<!-- auto-diff: {entity_id} ({domain}) at {datetime.now().strftime('%Y-%m-%d %H:%M')} -->\n")
            for r in diff_data["extracted_rules"]:
                f.write(f"- {r}\n")
    return diff_data
