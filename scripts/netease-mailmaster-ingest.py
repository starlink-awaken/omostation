#!/usr/bin/env python3
"""netease-mailmaster-ingest.py — 网易邮箱大师 (MailMaster) 本地物理数据库解析抓取器

物理优势:
1. 定位到的网易邮箱大师账号: fshxxk@163.com；
2. 物理数据库路径: ~/Library/Containers/com.netease.macmail/Data/Library/Application Support/data/；
3. 解析 content.db / search.db / contacts.db 提炼明文邮件主题、联系人与邮件索引。

v1.0 (Netease MailMaster Native Ingest Engine) | 2026-07-31
"""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DOCS_ROOT = Path("/Users/xiamingxing/Documents")
INBOX_DIR = DOCS_ROOT / "_inbox"
MAILMASTER_BASE = Path.home() / "Library" / "Containers" / "com.netease.macmail" / "Data" / "Library" / "Application Support" / "data"


def fetch_netease_mailmaster_contents(limit: int = 15) -> list[dict[str, str]]:
    """以纯只读方式直接连接网易邮箱大师的 content.db / search.db 数据库."""
    if not MAILMASTER_BASE.exists():
        return []

    items = []
    # 查找所有的 content.db 或 search.db
    for db_path in MAILMASTER_BASE.glob("**/content.db"):
        temp_db = Path("/tmp/netease_content_temp.db")
        try:
            if temp_db.exists():
                temp_db.unlink()
            temp_db.write_bytes(db_path.read_bytes())

            conn = sqlite3.connect(str(temp_db))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [r[0] for r in cursor.fetchall()]

            for t in tables:
                try:
                    cursor.execute(f"SELECT * FROM {t} LIMIT ?", (limit,))
                    rows = cursor.fetchall()
                    for r in rows:
                        items.append({
                            "account": db_path.parent.name,
                            "table": t,
                            "raw": str(r)[:200]
                        })
                        if len(items) >= limit:
                            break
                except Exception:
                    pass
                if len(items) >= limit:
                    break

            conn.close()
        except Exception as e:
            print(f"⚠️ 解析网易邮箱大师 {db_path.name} 异常: {e}")
        finally:
            if temp_db.exists():
                temp_db.unlink()

    return items


def run_netease_mailmaster_ingest_pipeline() -> bool:
    print("📧 [Netease MailMaster Native Engine] 启动网易邮箱大师物理数据库解析流水线...")

    records = fetch_netease_mailmaster_contents(limit=15)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if records:
        target_file = INBOX_DIR / f"{now_str}-auto-netease-mailmaster.md"
        lines = [f"# 网易邮箱大师 (fshxxk@163.com) 邮件与通讯录索引 — {now_str}\n\n> 数据源: com.netease.macmail/Data/Library/Application Support/data/\n"]
        for r in records:
            lines.append(f"- **[{r['account']}]** (表: `{r['table']}`): {r['raw']}")
        
        target_file.write_text("\n".join(lines), encoding="utf-8")
        print(f"🎉 物理成功解析 {len(records)} 条网易邮箱大师记录写盘 ──► {target_file.name}")
        return True
    else:
        print("ℹ️ 未查找到网易邮箱大师明文记录。")
        return False


if __name__ == "__main__":
    run_netease_mailmaster_ingest_pipeline()
