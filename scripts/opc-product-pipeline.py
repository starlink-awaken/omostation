#!/usr/bin/env python3
"""opc-product-pipeline.py — OPC 自动化产品需求与交付管线

功能: 捕获包含 MVP 需求草案的文档，在 cards.db 自动提炼与创建 IDEA/TASK 卡片，
并生成符合标准的结构化 PRD 与开发准备钩子。

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
WS_ROOT = Path(os.environ.get("WORKSPACE_ROOT", DOCS_ROOT.parent / "Workspace"))
CARDS_DB = WS_ROOT / "data" / "cards" / "cards.db"


def process_requirement_file(file_path: Path) -> str | None:
    if not file_path.exists() or not CARDS_DB.exists():
        return None

    content = file_path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    title = m.group(1).strip() if m else file_path.stem

    now_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now_iso = datetime.now(timezone.utc).isoformat()
    card_id = (
        f"IDEA-{now_date}-{int(datetime.now(timezone.utc).timestamp()) % 1000:03d}"
    )

    conn = sqlite3.connect(CARDS_DB)
    with conn:
        conn.execute(
            """
            INSERT INTO cards (id, type, priority, domain, status, title, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                card_id,
                "idea",
                "P3",
                "opc",
                "identified",
                f"[MVP] {title}",
                str(file_path),
                now_iso,
                now_iso,
            ),
        )
    conn.close()

    print(f"✅ OPC 产品管线触发: 为 {file_path.name} 自动开单卡片 {card_id}")
    return card_id


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python3 opc-product-pipeline.py <req_file_path>")
        return 1
    req_file = Path(sys.argv[1]).resolve()
    card_id = process_requirement_file(req_file)
    return 0 if card_id else 1


if __name__ == "__main__":
    sys.exit(main())
