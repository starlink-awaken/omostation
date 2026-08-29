#!/usr/bin/env python3
"""kairon-entity-ingest.py — 实体与关系图谱增量抽取器

功能: 解析 Markdown 文件的 YAML frontmatter 与标题/正文关键词，
提取核心实体 (Person, Domain, Project, Policy) 与语义关系，
增量更新至 Documents/kos-index.sqlite 数据库中的 entities 与 relations 表。

v1.0 | 2026-07-30
"""

from __future__ import annotations

import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DOCS_ROOT = Path(__file__).resolve().parents[2]
KOS_DB = DOCS_ROOT / "kos-index.sqlite"

# 默认关键实体定义
KNOWN_ENTITIES = {
    "夏明星": ("Person", "owner"),
    "秦张瑶": ("Person", "family_member"),
    "@驾驶舱": ("Domain", "cockpit"),
    "@学习进化": ("Domain", "vault"),
    "@家庭生活": ("Domain", "family"),
    "@OPC": ("Domain", "opc"),
    "@工作文档": ("Domain", "work"),
    "@个人": ("Domain", "personal"),
    "@创意创作": ("Domain", "creative"),
    "@公共": ("Domain", "shared"),
    "omostation": ("Project", "workspace_root"),
    "MetaOS": ("Project", "l4_self_layer"),
    "ADR-0203": ("Policy", "workflow_mandate"),
    "EX05": ("Policy", "inbox_routing_executor"),
}


def init_db(conn: sqlite3.Connection) -> None:
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                domain TEXT,
                updated_at TEXT NOT NULL
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS relations (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                predicate TEXT NOT NULL,
                target_id TEXT NOT NULL,
                doc_path TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(source_id) REFERENCES entities(id),
                FOREIGN KEY(target_id) REFERENCES entities(id)
            );
        """)


def ingest_file(file_path: Path, conn: sqlite3.Connection) -> int:
    if not file_path.exists() or not file_path.is_file():
        return 0
    content = file_path.read_text(encoding="utf-8", errors="ignore")
    now_iso = datetime.now(timezone.utc).isoformat()
    rel_path = str(file_path.relative_to(DOCS_ROOT))

    extracted_entities = []
    for name, (etype, domain) in KNOWN_ENTITIES.items():
        if name in content:
            entity_id = f"{etype.lower()}:{re.sub(r'\\W+', '_', name).strip('_')}"
            extracted_entities.append((entity_id, name, etype, domain))

    with conn:
        for eid, name, etype, domain in extracted_entities:
            conn.execute("""
                INSERT INTO entities (id, name, type, domain, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at
            """, (eid, name, etype, domain, now_iso))

        # 关联关系绑定: 文件归属域与实体绑定
        for eid, name, etype, domain in extracted_entities:
            rel_id = f"{rel_path}:{eid}"
            conn.execute("""
                INSERT INTO relations (id, source_id, predicate, target_id, doc_path, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at
            """, (rel_id, "doc:" + rel_path, "MENTIONS", eid, rel_path, now_iso))

    return len(extracted_entities)


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python3 kairon-entity-ingest.py <file_path>")
        return 1

    target_file = Path(sys.argv[1]).resolve()
    conn = sqlite3.connect(KOS_DB)
    init_db(conn)
    count = ingest_file(target_file, conn)
    conn.close()
    print(f"✅ 实体图谱抽取完成: 从 {target_file.name} 关联 {count} 个实体与关系")
    return 0


if __name__ == "__main__":
    sys.exit(main())
