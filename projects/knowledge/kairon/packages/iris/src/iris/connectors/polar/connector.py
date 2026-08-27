"""Polar.sh connector — reads articles via Polar.sh REST API.

Uses the official Polar.sh API v1:
  GET https://api.polar.sh/v1/articles/

Configuration (in order of precedence):
  1. Environment variable: POLAR_API_KEY
  2. Config file (~/.iris/config.json): polar.api_key

API Docs: https://docs.polar.sh/api-reference
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, cast

import httpx

from iris.base import BaseConnector, SyncResult
from iris.config import IrisConfig
from iris.models import Article

logger = logging.getLogger(__name__)

POLAR_API_BASE = "https://api.polar.sh"
POLAR_API_TIMEOUT = 30


# ── Polar.sh API helpers ──────────────────────────────────────────


def _polar_get(endpoint: str, api_key: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """GET from the Polar.sh API.

    Args:
        endpoint: API path (e.g., '/v1/articles/')
        api_key: Bearer token for authentication.
        params: Optional query parameters.

    Returns:
        Parsed JSON response dict, or None on failure.
    """
    url = f"{POLAR_API_BASE}{endpoint}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }

    try:
        response = httpx.get(url, headers=headers, params=params, timeout=POLAR_API_TIMEOUT)
        response.raise_for_status()
        return cast("dict[str, Any] | None", response.json())
    except httpx.HTTPStatusError as e:
        logger.warning("Polar.sh API HTTP error [%s]: %s %s", endpoint, e.response.status_code, e.response.text)
        return None
    except Exception as e:
        logger.warning("Polar.sh API request failed [%s]: %s", endpoint, e)
        return None


def _polar_item_to_article(item: dict[str, Any], platform: str) -> Article:
    """Map a Polar.sh API article dict to an Article instance.

    Polar.sh article fields (typical):
        - id (str)
        - title (str)
        - slug (str)
        - body (str, markdown content)
        - byline (str, author/creator)
        - published_at (ISO 8601 datetime string)
        - url (str, external URL if any)
        - tags (list[str])
    """
    item_id = item.get("id", "")
    title = item.get("title", "") or ""
    body = item.get("body", "") or ""
    url = item.get("url", "") or ""
    author = item.get("byline", "") or ""
    published_at = item.get("published_at", "")
    updated_at = item.get("updated_at", "")
    tags = item.get("tags", None) or []

    # Add tags to body as a footer for discoverability
    content = body
    if tags:
        tag_str = ", ".join(tags)
        if content:
            content = f"{content}\n\n---\nTags: {tag_str}"
        else:
            content = f"Tags: {tag_str}"

    # Format dates: ISO 8601 → YYYY-MM-DD
    created = ""
    if published_at:
        try:
            created = published_at[:10]
        except Exception:
            created = published_at

    updated = ""
    if updated_at:
        try:
            updated = updated_at[:10]
        except Exception:
            updated = updated_at

    return Article(
        id=f"polar/{item_id}",
        title=title,
        content=content,
        url=url,
        author=author,
        platform=platform,
        created_at=created,
        updated_at=updated,
    )


# ── Connector ─────────────────────────────────────────────────────


class PolarConnector(BaseConnector):
    """Connector for Polar.sh — reads articles via the Polar.sh REST API.

    Uses Bearer token authentication via the POLAR_API_KEY environment
    variable or polar.api_key config file entry.

    Environment variables:
        POLAR_API_KEY  — Polar.sh API key (recommended)

    Config file keys (~/.iris/config.json):
        polar.api_key
    """

    name = "polar"
    display_name = "Polar.sh"

    def __init__(self, config: IrisConfig | None = None):
        self._config = config or IrisConfig()
        self._last_sync_at: str = ""

        # Read API key: env var first, then config file
        self._api_key = self._get_credential("POLAR_API_KEY", "polar.api_key")

    def _get_credential(self, env_var: str, config_key: str) -> str:
        """Read a credential from environment variable or config file."""
        val = os.environ.get(env_var)
        if val:
            return val
        return cast("str", self._config.get(config_key, default=""))

    # ── Availability ────────────────────────────────────────────

    def is_available(self) -> bool:
        """Check if Polar.sh API key is configured."""
        return bool(self._api_key)

    # ── List items ──────────────────────────────────────────────

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
        """List articles from Polar.sh, with optional pagination.

        Args:
            limit: Max items to return (default: 20).
            cursor: Pagination cursor string (Polar uses opaque cursors).

        Returns:
            List of Article instances.
        """
        if not self.is_available():
            logger.warning("Polar connector not available — missing POLAR_API_KEY")
            return []

        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor

        result = _polar_get("/v1/articles/", self._api_key, params=params)
        if not result:
            return []

        return self._parse_article_list(result)

    def _parse_article_list(self, result: dict[str, Any]) -> list[Article]:
        """Parse the Polar.sh API response into Article instances."""
        items = result.get("items", []) or []
        articles: list[Article] = []
        for item in items:
            try:
                article = _polar_item_to_article(item, self.name)
                articles.append(article)
            except Exception as e:
                logger.debug("Failed to parse Polar.sh article %s: %s", item.get("id", "?"), e)
                continue
        return articles

    # ── Get single item ─────────────────────────────────────────

    def get_item(self, id: str) -> Article | None:
        """Get a single Polar.sh article by its platform ID.

        Args:
            id: Polar.sh article ID (with or without 'polar/' prefix).

        Returns:
            Article instance or None if not found.
        """
        if not self.is_available():
            return None

        # Strip the 'polar/' prefix if present
        raw_id = id.removeprefix("polar/")

        result = _polar_get(f"/v1/articles/{raw_id}", self._api_key)
        if not result:
            return None

        try:
            return _polar_item_to_article(result, self.name)
        except Exception as e:
            logger.warning("Failed to parse Polar.sh article %s: %s", raw_id, e)
            return None

    # ── Search ──────────────────────────────────────────────────

    def search(self, query: str, limit: int = 10) -> list[Article]:
        """Search Polar.sh articles by query string.

        Args:
            query: Search keyword.
            limit: Max results to return (default: 10).

        Returns:
            List of matching Article instances.
        """
        if not self.is_available():
            return []

        params: dict[str, Any] = {"q": query, "limit": limit}

        result = _polar_get("/v1/articles/search", self._api_key, params=params)
        if not result:
            return []

        items = self._parse_article_list(result)
        return items[:limit]

    # ── Sync ────────────────────────────────────────────────────

    def sync(self, dry_run: bool = False) -> SyncResult:
        """Pull latest articles from Polar.sh.

        In dry_run mode, returns the count of items that would
        be synced without actually processing them.

        Args:
            dry_run: If True, only count available items.

        Returns:
            SyncResult with items_found count.
        """
        if not self.is_available():
            return SyncResult(
                connector_name=self.name,
                success=False,
                message="Polar.sh API key not configured. Set POLAR_API_KEY environment variable.",
                errors=["Missing credentials"],
            )

        try:
            # Fetch articles sorted by newest first
            params: dict[str, Any] = {"limit": 30, "sort": "-published_at"}
            result = _polar_get("/v1/articles/", self._api_key, params=params)
            if not result:
                return SyncResult(
                    connector_name=self.name,
                    success=False,
                    message="Failed to fetch Polar.sh articles.",
                    errors=["API request failed"],
                )

            items = self._parse_article_list(result)
            count = len(items)

            if dry_run:
                return SyncResult(
                    connector_name=self.name,
                    items_found=count,
                    success=True,
                    message=f"Dry run: {count} Polar.sh articles would be synced.",
                )

            # Record sync time
            self._last_sync_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            return SyncResult(
                connector_name=self.name,
                items_found=count,
                success=True,
                message=f"Synced {count} Polar.sh articles.",
            )

        except Exception as e:
            logger.exception("Polar.sh sync failed")
            return SyncResult(
                connector_name=self.name,
                success=False,
                message=f"Polar.sh sync failed: {e}",
                errors=[str(e)],
            )

    # ── Status ──────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        """Return connector health and stats.

        Returns a dict with:
            - configured: whether API key is present
            - last_sync_at: timestamp of last sync
            - total_count: total article count
            - note: any relevant info about the data
        """
        if not self.is_available():
            return {
                "configured": False,
                "last_sync_at": self._last_sync_at,
                "total_count": 0,
                "note": "API key not configured. Set POLAR_API_KEY.",
            }

        try:
            # Fetch 1 item to get pagination total
            params: dict[str, Any] = {"limit": 1}
            result = _polar_get("/v1/articles/", self._api_key, params=params)
            if not result:
                return {
                    "configured": True,
                    "last_sync_at": self._last_sync_at,
                    "total_count": -1,
                    "note": "Failed to fetch article count.",
                }

            pagination = result.get("pagination", {}) or {}
            total_count = pagination.get("total_count", -1)

            return {
                "configured": True,
                "last_sync_at": self._last_sync_at,
                "total_count": total_count,
                "note": "Article count from Polar.sh API pagination metadata.",
            }

        except Exception as e:
            logger.warning("Failed to get Polar.sh status: %s", e)
            return {
                "configured": True,
                "last_sync_at": self._last_sync_at,
                "total_count": -1,
                "note": f"Status check failed: {e}",
            }
