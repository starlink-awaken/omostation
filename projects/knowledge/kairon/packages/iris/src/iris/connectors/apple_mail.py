"""Apple Mail connector — macOS 原生 .emlx 邮件提取.

ECCP P3 收编: 从 runtime/scripts/apple-mail-ingest.py 改写成 iris connector,
统一走 BaseConnector (自动暴露 external_descriptor + is_available health).
原 ingest 脚本退化为 connector 的 fetch 实现.

收编理由 (fabric truth_owner: source_adapters=kairon.iris):
  Apple Mail 是 knowledge_source, 进 iris 连接器枢纽是架构正位.

物理提取: ~/Library/Mail/V10/**/*.emlx 真实邮件正文 (非 Envelope Index).
"""

from __future__ import annotations

import email
from pathlib import Path
from typing import Any

from iris.base import BaseConnector
from iris.models import Note

MAIL_BASE = Path.home() / "Library" / "Mail" / "V10"


def _extract_emlx_body(emlx_path: Path) -> dict[str, str]:
    """提取 .emlx 邮件正文 (收编自 apple-mail-ingest.fetch_real_apple_mail_bodies)."""
    try:
        raw = emlx_path.read_bytes()
        first_nl = raw.find(b"\n")
        if first_nl == -1:
            return {}
        eml_bytes = raw[first_nl + 1 :]
        msg = email.message_from_bytes(eml_bytes)
        subject = msg.get("Subject", "")
        sender = msg.get("From", "")
        date = msg.get("Date", "")
        body = ""
        payload = msg.get_payload(decode=True)
        if isinstance(payload, bytes):
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        part_payload = part.get_payload(decode=True)
                        if isinstance(part_payload, bytes):
                            body = part_payload.decode("utf-8", errors="replace")
                            break
            else:
                body = payload.decode("utf-8", errors="replace")
        return {"subject": subject, "sender": sender, "date": date, "body": body[:5000]}
    except Exception:
        return {}


def _eml_to_note(extracted: dict[str, str], emlx_name: str) -> Note:
    """邮件 dict → iris Note (KnowledgeArtifact)."""
    return Note(
        id=emlx_name,
        title=extracted.get("subject", "(no subject)")[:200],
        platform="apple_mail",
        created_at=extracted.get("date", ""),
        updated_at=extracted.get("date", ""),
        content=extracted.get("body", ""),
        tags=["mail", extracted.get("sender", "")[:50]],
        source_path=f"emlx://{emlx_name}",
    )


class AppleMailConnector(BaseConnector):
    """macOS Apple Mail .emlx 邮件连接器 (ECCP P3 收编)."""

    name = "apple_mail"
    display_name = "Apple Mail"
    connection_kind = "knowledge_source"
    protocol = "apple.mail.emlx/v1"
    capabilities = ("discover", "search", "read", "snapshot")
    data_classification = "private"

    def is_available(self) -> bool:
        """Check macOS Mail V10 目录存在."""
        return MAIL_BASE.exists()

    def status(self) -> dict[str, Any]:
        """Return emlx 数量 + 路径."""
        emlx_count = len(list(MAIL_BASE.glob("**/*.emlx"))) if self.is_available() else 0
        return {
            "mail_base": str(MAIL_BASE),
            "available": self.is_available(),
            "emlx_count": emlx_count,
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
        """扫 V10 下最新 .emlx 邮件 (收编自 fetch_real_apple_mail_bodies)."""
        if not self.is_available():
            return []
        emlx_files = sorted(
            MAIL_BASE.glob("**/*.emlx"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        items: list[Note] = []
        for f in emlx_files[:limit]:
            extracted = _extract_emlx_body(f)
            if not extracted:
                continue
            items.append(_eml_to_note(extracted, f.name))
        return items

    def search(self, query: str, limit: int = 10) -> list[Note]:
        """简单全文搜索 (title/content 含 query)."""
        items = self.list_items(limit=limit * 3)
        q = query.lower()
        return [it for it in items if q in it.title.lower() or q in it.content.lower()][:limit]
