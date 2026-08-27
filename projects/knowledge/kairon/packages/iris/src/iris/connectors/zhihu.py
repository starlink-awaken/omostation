"""Zhihu connector — reads public articles and content via kronos.

Uses kronos fetch_router for L0 HTTP fetching of public Zhihu content.
For authenticated content (saved articles, likes), requires cookie setup.

Configuration:
  IRIS_ZHIHU_COOKIE — optional cookie for authenticated Zhihu access
  Falls back to public scraping via kronos for open articles/columns

Setup:
  1. Public content: works out of the box via kronos
  2. Authenticated: export cookie from Chrome DevTools → ~/.iris/zhihu_cookie.txt
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, cast

from iris.base import BaseConnector, SyncResult
from iris.config import IrisConfig
from iris.models import Article

logger = logging.getLogger(__name__)

ZHIHU_HOST = "https://www.zhihu.com"


class ZhihuConnector(BaseConnector):
    """Connector for Zhihu (知乎).

    Reads public articles and column posts via kronos fetch_router.
    Authenticated content requires cookie setup.
    """

    name = "zhihu"
    display_name = "知乎"

    def __init__(self, config: IrisConfig | None = None):
        self._config = config or IrisConfig()
        self._cookie = os.environ.get("IRIS_ZHIHU_COOKIE", "")

    def _fetch_url(self, url: str) -> str | None:
        """Fetch a URL using kronos fetch_router or direct HTTP."""
        try:
            from kronos.fetch_router import execute_fetch

            result = execute_fetch(url, cookie=self._cookie)  # type: ignore[reportCallIssue]
            if result and result.get("content"):
                return cast("str | None", result["content"])
        except ImportError:
            pass
        except Exception as e:
            logger.debug("kronos fetch failed: %s", e)

        # Fallback: direct HTTP with optional cookie
        try:
            import urllib.request

            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "Accept": "text/html,application/xhtml+xml",
            }
            if self._cookie:
                headers["Cookie"] = self._cookie
            req = urllib.request.Request(url, headers=headers)
            resp = urllib.request.urlopen(req, timeout=15)
            return cast("str", resp.read().decode("utf-8", errors="replace"))
        except Exception as e:
            logger.debug("Direct HTTP fetch failed: %s", e)
            return None

    def _extract_articles(self, html: str) -> list[dict]:
        """Extract article info from Zhihu HTML."""
        articles = []

        # Try JSON-LD structured data
        for match in re.finditer(
            r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
            html,
            re.DOTALL,
        ):
            try:
                data = json.loads(match.group(1))
                if isinstance(data, dict) and data.get("@type") == "Article":
                    articles.append(
                        {
                            "title": data.get("headline", ""),
                            "url": data.get("url", ""),
                            "description": data.get("description", ""),
                            "author": data.get("author", {}).get("name", "")
                            if isinstance(data.get("author"), dict)
                            else "",
                        }
                    )
            except (json.JSONDecodeError, AttributeError):
                pass

        # Fallback: regex-based extraction from HTML
        if not articles:
            for title_match in re.finditer(
                r'<h1[^>]*class="[^"]*ContentHeader[^"]*"[^>]*>(.*?)</h1>',
                html,
                re.DOTALL,
            ):
                title = re.sub(r"<[^>]+>", "", title_match.group(1)).strip()
                if title:
                    articles.append({"title": title, "url": "", "description": "", "author": ""})

            if not articles:
                for title_match in re.finditer(r"<title>(.*?)</title>", html):
                    title = title_match.group(1).replace(" - 知乎", "").strip()
                    if title:
                        articles.append({"title": title, "url": "", "description": "", "author": ""})

        return articles

    def is_available(self) -> bool:
        """Check if we can reach Zhihu."""
        try:
            import urllib.request

            resp = urllib.request.urlopen(f"{ZHIHU_HOST}/robots.txt", timeout=5)
            return cast("bool", resp.status == 200)
        except Exception:
            return False

    def list_items(
        self,
        limit: int = 20,
        cursor: str | None = None,
        tag: str | None = None,
        folder: str | None = None,
        subdir: str | None = None,
        chat_id: str | None = None,
        **kwargs: Any,
    ) -> list[Article]:
        """Not available without auth — Zhihu doesn't have a public feed API."""
        return []

    def get_item(self, id: str) -> Article | None:
        """Get a specific Zhihu article by URL or ID."""
        url = id
        if not url.startswith("http"):
            url = f"{ZHIHU_HOST}/question/{id}" if id.isdigit() else f"{ZHIHU_HOST}/p/{id}"

        html = self._fetch_url(url)
        if not html:
            return None

        articles = self._extract_articles(html)
        if articles:
            a = articles[0]
            return Article(
                id=id,
                title=a.get("title", f"Zhihu Article {id}"),
                url=url,
                author=a.get("author", ""),
                summary=a.get("description", "")[:300],
                content=html[:5000],
                platform=self.name,
            )
        return None

    def search(self, query: str, limit: int = 10) -> list[Article]:
        """Search public Zhihu content."""
        url = f"{ZHIHU_HOST}/search?type=content&q={query.replace(' ', '+')}"
        html = self._fetch_url(url)
        if not html:
            return []

        articles = self._extract_articles(html)
        return [
            Article(
                id=a.get("url", "").split("/")[-1] or str(i),
                title=a.get("title", f"Result {i}"),
                url=a.get("url", ""),
                author=a.get("author", ""),
                summary=a.get("description", "")[:300],
                platform=self.name,
            )
            for i, a in enumerate(articles[:limit])
        ]

    def status(self) -> dict[str, Any]:
        available = self.is_available()
        auth = bool(self._cookie)
        return {
            "available": available,
            "authenticated": auth,
            "note": "🔌 知乎连接器" if available else "🔌 知乎不可达（网络/代理）",
            "setup": "export IRIS_ZHIHU_COOKIE='<cookie>' for authenticated access",
        }

    def sync(self, dry_run: bool = False) -> SyncResult:
        return SyncResult(
            connector_name=self.name,
            items_found=0,
            success=True,
            message="Zhihu sync: manual URL fetch only (no feed API)",
        )
