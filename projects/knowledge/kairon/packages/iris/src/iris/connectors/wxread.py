"""WeChat Read (微信读书) connector — Agent API Gateway.

Uses the official WeRead Agent API Gateway (https://i.weread.qq.com/api/agent/gateway)
with API key authentication. Replaces the old cookie-based stub.

Configuration:
  IRIS_WEREAD_API_KEY or WEREAD_API_KEY environment variable

API Docs:
  POST https://i.weread.qq.com/api/agent/gateway
  Authorization: Bearer $WEREAD_API_KEY
  Body: {"api_name": "...", "skill_version": "1.0.3", ...params}
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from typing import Any, cast

from iris.base import BaseConnector, SyncResult
from iris.config import IrisConfig
from iris.models import Highlight, KnowledgeArtifact

logger = logging.getLogger(__name__)

AGENT_GATEWAY = "https://i.weread.qq.com/api/agent/gateway"
SKILL_VERSION = "1.0.3"

# ── API request helper ─────────────────────────────────────────────


def _api_call(api_name: str, **params: Any) -> dict | None:
    """Call WeRead Agent API Gateway."""
    api_key = os.environ.get("IRIS_WEREAD_API_KEY") or os.environ.get("WEREAD_API_KEY")
    if not api_key:
        return None

    body = {"api_name": api_name, "skill_version": SKILL_VERSION, **params}
    req = urllib.request.Request(
        AGENT_GATEWAY,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data: dict = json.loads(resp.read())
        if data.get("errcode", 0) != 0:
            logger.warning("WeRead API error [%s]: %s", api_name, data.get("errmsg", ""))
            return data
        return data
    except Exception as e:
        logger.warning("WeRead API call failed [%s]: %s", api_name, e)
        return None


def _parse_timestamp(ts: int | float | None) -> str:
    """Convert Unix timestamp to YYYY-MM-DD string."""
    if not ts:
        return ""
    from datetime import datetime

    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


# ── Connector ──────────────────────────────────────────────────────


class WXReadConnector(BaseConnector):
    """Connector for WeChat Read (微信读书) via Agent API Gateway.

    Reads bookshelf, highlights, bookmarks, and personal notes.
    Uses API key authentication (no cookie scraping needed).
    """

    name = "wxread"
    display_name = "微信读书"

    def __init__(self, config: IrisConfig | None = None):
        self._config = config or IrisConfig()

    def is_available(self) -> bool:
        api_key = os.environ.get("IRIS_WEREAD_API_KEY") or os.environ.get("WEREAD_API_KEY")
        return bool(api_key)

    def list_items(
        self,
        limit: int = 20,
        cursor: str | None = None,
        tag: str | None = None,
        folder: str | None = None,
        subdir: str | None = None,
        chat_id: str | None = None,
    ) -> list[KnowledgeArtifact]:
        """List recent highlights/bookmarks from bookshelf.

        Fetches bookshelf first, then gets highlights for each book.
        """
        items: list[Highlight] = []

        # Step 1: Get bookshelf
        shelf = _api_call("/shelf/sync")
        if not shelf:
            return cast("list[KnowledgeArtifact]", items)

        books = []
        for key in ("books", "albums"):
            for b in shelf.get(key) or []:
                book = b.get("book", {})
                bid = book.get("bookId", "") or book.get("id", "")
                title = book.get("title", "Untitled")
                author = book.get("author", "")
                cover = book.get("cover", "")
                books.append({"id": bid, "title": title, "author": author, "cover": cover})

        # Step 2: Get highlights for each book (up to limit)
        for book in books[:limit]:
            bid = book["id"]
            if not bid:
                continue

            marks = _api_call("/book/bookmarklist", bookId=bid)
            if not marks or not marks.get("items"):
                continue

            for m in marks["items"][:5]:  # max 5 highlights per book
                text = m.get("text", "") or m.get("content", "") or ""
                annotation = m.get("abstract", "") or ""
                chapter = m.get("chapterUid", "")
                items.append(
                    Highlight(
                        id=f"{bid}/{m.get('chapterUid', 0)}/{m.get('range', '0-0')}",
                        title=f"📖 {book['title']}",
                        text=text,
                        chapter=str(chapter),
                        annotation=annotation,
                        source_url=f"weread://bestbookmark?bookId={bid}&chapterUid={chapter}&rangeStart={m.get('range', '0-0').split('-')[0]}&rangeEnd={m.get('range', '0-0').split('-')[1]}"
                        if m.get("range")
                        else "",
                        platform=self.name,
                        created_at=_parse_timestamp(m.get("createTime")),
                        updated_at=_parse_timestamp(m.get("updateTime")),
                    )
                )

        return cast("list[KnowledgeArtifact]", items[:limit])

    def get_item(self, id: str) -> KnowledgeArtifact | None:
        """Get a specific book's highlights."""
        items = self.list_items(limit=50)
        for item in items:
            if item.id == id:
                return item
        return None

    def search(self, query: str, limit: int = 10) -> list[KnowledgeArtifact]:
        """Search books on WeRead and return matching items."""
        results = _api_call("/store/search", keyword=query, count=limit)
        items: list[Highlight] = []
        if not results or not results.get("books"):
            return cast("list[KnowledgeArtifact]", items)

        for b in results["books"][:limit]:
            bid = b.get("bookId", "")
            title = b.get("title", "Untitled")
            author = b.get("author", "")
            intro = b.get("intro", "") or ""
            b.get("cover", "")

            items.append(
                Highlight(
                    id=f"search/{bid}",
                    title=f"📚 {title}",
                    text=f"{author} | {intro[:200]}",
                    chapter="",
                    annotation="",
                    source_url=f"weread://reading?bId={bid}",
                    platform=self.name,
                    created_at="",
                    updated_at="",
                )
            )

        return cast("list[KnowledgeArtifact]", items[:limit])

    def status(self) -> dict[str, Any]:
        configured = self.is_available()
        if not configured:
            return {
                "available": False,
                "note": "🔌 需要设置 IRIS_WEREAD_API_KEY 或 WEREAD_API_KEY",
                "setup": "export WEREAD_API_KEY=<your-api-key>",
                "help": "从微信读书开放平台获取 API Key",
            }

        # Quick connectivity check
        shelf = _api_call("/shelf/sync")
        book_count = 0
        if shelf:
            book_count = len(shelf.get("books", [])) + len(shelf.get("albums", []))

        return {
            "available": True,
            "book_count": book_count,
            "note": "✅ 已连接微信读书 API Gateway",
        }

    def sync(self, dry_run: bool = False) -> SyncResult:
        """Sync recent highlights from WeChat Read."""
        items = self.list_items(limit=50)
        return SyncResult(
            connector_name=self.name,
            items_found=len(items),
            success=True,
            message=f"Synced {len(items)} highlights from WeChat Read",
        )
