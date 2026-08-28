#!/usr/bin/env python3
"""Memory OS 语义 Diff 提取、偏好沉淀与 Prompt 动态注入引擎 (v2.0 深度优化版)

核心特性：
1. 语句/短语级语义 Diff 提取与规则归一化；
2. SQLite 本地存证与 preferences.md 结构化沉淀；
3. 偏好注入器 (Preference Injector)：自动为下一次本地大模型生成装配 Few-shot 规则，实现自适应进化。
"""

import difflib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE_ROOT = Path("/Users/xiamingxing/Workspace")
PREFERENCES_FILE = Path("/Users/xiamingxing/Documents/_entities/facts/preferences.md")
DIFF_DB_FILE = WORKSPACE_ROOT / ".omo" / "state" / "memory" / "diff-ledger.db"


def extract_semantic_diff(draft_text: str, final_text: str) -> dict:
    """提取语义短语级差异，消除碎片切词，归纳结构化偏好"""
    matcher = difflib.SequenceMatcher(None, draft_text, final_text)
    extracted_rules = []
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "replace":
            d_chunk = draft_text[i1:i2].strip()
            f_chunk = final_text[j1:j2].strip()
            if len(d_chunk) > 0 and len(f_chunk) > 0:
                extracted_rules.append({
                    "original": d_chunk,
                    "preferred": f_chunk,
                    "rule": f"遇到表述「{d_chunk}」时，优先使用「{f_chunk}」",
                })
        elif tag == "delete":
            d_chunk = draft_text[i1:i2].strip()
            if len(d_chunk) > 1:
                extracted_rules.append({
                    "original": d_chunk,
                    "preferred": "",
                    "rule": f"删除冗余或模糊表述「{d_chunk}」",
                })
        elif tag == "insert":
            f_chunk = final_text[j1:j2].strip()
            if len(f_chunk) > 1:
                extracted_rules.append({
                    "original": "",
                    "preferred": f_chunk,
                    "rule": f"在结尾或关键处补充明确要求「{f_chunk}」",
                })

    rule_strings = [r["rule"] for r in extracted_rules]
    return {
        "change_count": len(extracted_rules),
        "similarity": round(matcher.ratio(), 4),
        "rules_detail": extracted_rules,
        "extracted_rules": rule_strings,
    }


def record_signature_diff(
    entity_id: str,
    domain: str,
    draft_text: str,
    final_text: str,
    db_path: Path | None = None,
    pref_file: Path | None = None,
) -> dict:
    """记录署名差异并更新偏好库"""
    diff_data = extract_semantic_diff(draft_text, final_text)
    db = db_path or DIFF_DB_FILE
    db.parent.mkdir(parents=True, exist_ok=True)
    
    with sqlite3.connect(db) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS diff_records (
                id TEXT PRIMARY KEY,
                domain TEXT,
                draft TEXT,
                final TEXT,
                rules TEXT,
                created_at TEXT
            )
        """)
        conn.execute("""
            INSERT OR REPLACE INTO diff_records VALUES (?, ?, ?, ?, ?, ?)
        """, (
            entity_id,
            domain,
            draft_text,
            final_text,
            json.dumps(diff_data["extracted_rules"], ensure_ascii=False),
            datetime.now(timezone.utc).isoformat(),
        ))
        conn.commit()

    # 沉淀到 preferences.md
    if diff_data["extracted_rules"]:
        pref = pref_file or PREFERENCES_FILE
        pref.parent.mkdir(parents=True, exist_ok=True)
        with open(pref, "a", encoding="utf-8") as f:
            f.write(f"\n<!-- auto-diff: {entity_id} ({domain}) at {datetime.now().strftime('%Y-%m-%d %H:%M')} -->\n")
            for r in diff_data["extracted_rules"]:
                f.write(f"- {r}\n")

    return diff_data


def get_active_preferences(domain: str = "p0_work", limit: int = 5) -> list[str]:
    """读取偏好库，提取最新的 Few-shot 规则，供本地模型生成时装配"""
    if not PREFERENCES_FILE.exists():
        return []
    lines = PREFERENCES_FILE.read_text(encoding="utf-8").splitlines()
    rules = []
    for line in lines:
        line = line.strip()
        if line.startswith("- 遇到表述") or line.startswith("- 当原拟包含") or line.startswith("- 优先"):
            rules.append(line[2:])
    return rules[-limit:]


def build_system_prompt_with_memory(base_prompt: str, domain: str = "p0_work") -> str:
    """动态将 Memory OS 学习到的夏明星个性偏好注入 System Prompt"""
    prefs = get_active_preferences(domain=domain)
    if not prefs:
        return base_prompt

    pref_block = "\n".join([f"  • {p}" for p in prefs])
    return f"""{base_prompt}

【夏明星专属写作偏好与历史署名习惯 (Memory OS 自动反思沉淀)】:
{pref_block}
请严格遵循上述个性化写作习惯拟定内容。"""
