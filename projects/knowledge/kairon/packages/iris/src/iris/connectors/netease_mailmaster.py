"""Netease Mailmaster connector — 网易邮箱大师 (ECCP P3 收编, N5 list 能力).

收编自 runtime/scripts/netease-mailmaster-ingest.py.
原脚本: 真实解压 OrigBody zlib Blob, 3 账号 (卫健委/163) 真实邮件公文.
N5: 迁移 zlib 解压逻辑到 list_items, 统一走 BaseConnector list/search 契约.

收编理由 (fabric truth_owner: source_adapters=kairon.iris):
  网易邮箱大师是 knowledge_source, 进 iris 连接器枢纽是架构正位.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import zlib
from pathlib import Path
from typing import Any

from iris.base import BaseConnector
from iris.models import Note

MAILMASTER_BASE = Path.home() / "Library/Containers/com.netease.macmail/Data/Library/Application Support/data"

logger = logging.getLogger(__name__)


def _clean_html_text(raw_html: str) -> str:
    """去除邮件 HTML 标签, 提炼可读文本 (收编自原 ingest 脚本 clean_html_text)."""
    text = re.sub(r"<style.*?>.*?</style>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script.*?>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<.*?>", " ", text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " ".join(lines)


def _decompress_mail_bodies(db_path: Path, limit: int) -> list[dict[str, str]]:
    """复制 content.db 到 /tmp (避免锁原库), zlib 解压 OrigBody 真实正文.

    收编自原 ingest 脚本 fetch_netease_mailmaster_real_bodies, 逻辑等价:
    text_factory=bytes + zlib.decompress + utf-8 decode + clean_html_text.
    """
    temp_db = Path("/tmp/iris_netease_content.db")
    try:
        if temp_db.exists():
            temp_db.unlink()
        temp_db.write_bytes(db_path.read_bytes())
        conn = sqlite3.connect(str(temp_db))
        conn.text_factory = bytes
        cursor = conn.cursor()
        cursor.execute(
            "SELECT LocalId, MailId, OrigBody FROM MailContent WHERE OrigBody IS NOT NULL LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()
    finally:
        if temp_db.exists():
            temp_db.unlink()

    account = db_path.parent.name
    items: list[dict[str, str]] = []
    for _lid, mid, raw_blob in rows:
        if not raw_blob:
            continue
        try:
            html = zlib.decompress(raw_blob).decode("utf-8", errors="ignore")
            plain = _clean_html_text(html)
            if len(plain) > 10:
                mail_id = mid.decode() if isinstance(mid, bytes) else str(mid)
                items.append(
                    {
                        "account": account,
                        "mail_id": mail_id,
                        "content": plain[:5000],
                    }
                )
        except Exception as e:
            logger.debug("netease OrigBody 解压跳过 (单封损坏不影响批量): %s", e)
            continue
    return items


class NeteaseMailmasterConnector(BaseConnector):
    """网易邮箱大师 (ECCP P3 收编, N5 list 能力: zlib 真实邮件正文)."""

    name = "netease_mailmaster"
    display_name = "网易邮箱大师"
    connection_kind = "knowledge_source"
    protocol = "netease.mailmaster/v1"
    capabilities = ("discover", "search", "read", "snapshot")
    data_classification = "private"

    def is_available(self) -> bool:
        return MAILMASTER_BASE.exists()

    def status(self) -> dict[str, Any]:
        db_count = len(list(MAILMASTER_BASE.glob("**/*.sqlite"))) if self.is_available() else 0
        return {
            "base": str(MAILMASTER_BASE),
            "available": self.is_available(),
            "sqlite_count": db_count,
        }

    def list_items(
        self,
        limit: int = 20,
        cursor: str | None = None,
        tag: str | None = None,
        folder: str | None = None,
        subdir: str | None = None,
        chat_id: str | None = None,
    ) -> list[Note]:
        """扫 content.db + zlib 解压 OrigBody 真实邮件正文 (收编自原 ingest 脚本)."""
        if not self.is_available():
            return []
        items: list[Note] = []
        for db_path in MAILMASTER_BASE.glob("**/content.db"):
            for r in _decompress_mail_bodies(db_path, limit):
                items.append(
                    Note(
                        id=r["mail_id"],
                        title=f"[{r['account']}] {r['content'][:50]}",
                        platform="netease_mailmaster",
                        created_at="",
                        updated_at="",
                        content=r["content"],
                        tags=["mail", r["account"]],
                        source_path=f"netease://{r['account']}/{r['mail_id']}",
                    )
                )
            if len(items) >= limit:
                break
        return items[:limit]

    def search(self, query: str, limit: int = 10) -> list[Note]:
        """简单全文搜索 (title/content 含 query)."""
        items = self.list_items(limit=limit * 3)
        q = query.lower()
        return [it for it in items if q in it.content.lower() or q in it.title.lower()][:limit]
