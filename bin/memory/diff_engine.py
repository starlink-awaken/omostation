#!/usr/bin/env python3
"""Memory OS 语义 Diff 提取与夏明星偏好规则学习引擎 (v2.0)"""

import difflib
import re
import sqlite3
import time
from pathlib import Path


def extract_semantic_diff(draft_text: str, modified_text: str) -> dict:
    """提取草稿与最终署名文本之间的短语级语义差异并生成偏好规则"""
    matcher = difflib.SequenceMatcher(None, draft_text, modified_text)
    changes = []
    extracted_rules = []
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "replace":
            d_part = draft_text[i1:i2].strip()
            m_part = modified_text[j1:j2].strip()
            if d_part and m_part:
                changes.append({"type": "replace", "from": d_part, "to": m_part})
                extracted_rules.append(f"遇到表述「{d_part}」时，优先使用「{m_part}」")
        elif tag == "delete":
            d_part = draft_text[i1:i2].strip()
            if d_part:
                changes.append({"type": "delete", "text": d_part})
                extracted_rules.append(f"删除冗余表述「{d_part}」")
        elif tag == "insert":
            m_part = modified_text[j1:j2].strip()
            if m_part:
                changes.append({"type": "insert", "text": m_part})
                extracted_rules.append(f"补充明确表述「{m_part}」")

    similarity = round(matcher.ratio() * 100, 1)
    return {
        "similarity_percent": similarity,
        "change_count": len(changes),
        "changes": changes,
        "extracted_rules": extracted_rules,
    }


def record_signature_diff(
    entity_id: str,
    domain: str,
    draft_text: str,
    modified_text: str,
    db_path: Path | str | None = None,
    pref_file: Path | str | None = None,
) -> dict:
    """持久化署名差异至 SQLite 及 preferences.md"""
    diff_res = extract_semantic_diff(draft_text, modified_text)
    
    target_db = Path(db_path or "/Users/xiamingxing/Workspace/.omo/state/memory/diff-ledger.db")
    target_db.parent.mkdir(parents=True, exist_ok=True)
    
    with sqlite3.connect(target_db) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS signature_diffs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id TEXT,
                domain TEXT,
                draft_text TEXT,
                modified_text TEXT,
                similarity_percent REAL,
                rules_json TEXT,
                created_at REAL
            )
        """)
        import json
        conn.execute("""
            INSERT INTO signature_diffs (entity_id, domain, draft_text, modified_text, similarity_percent, rules_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (entity_id, domain, draft_text, modified_text, diff_res["similarity_percent"], json.dumps(diff_res["extracted_rules"], ensure_ascii=False), time.time()))
        conn.commit()

    target_pref = Path(pref_file or "/Users/xiamingxing/Documents/_entities/facts/preferences.md")
    target_pref.parent.mkdir(parents=True, exist_ok=True)
    
    with open(target_pref, "a", encoding="utf-8") as f:
        f.write(f"\n<!-- Diff-Auto-Learning: {entity_id} -->\n")
        for rule in diff_res["extracted_rules"]:
            f.write(f"- [Preference] {rule}\n")

    return diff_res
