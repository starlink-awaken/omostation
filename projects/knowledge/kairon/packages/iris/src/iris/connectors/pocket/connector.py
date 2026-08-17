"""Pocket connector — reads bookmarks via Pocket API v3.

Uses the official Pocket API v3 (REST):
  POST https://getpocket.com/v3/get

Configuration (in order of precedence):
  1. Environment variables: POCKET_CONSUMER_KEY, POCKET_ACCESS_TOKEN
  2. Config file (~/.iris/config.json): pocket.consumer_key, pocket.access_token

API Docs: https://getpocket.com/developer/docs/v3/retrieve
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from datetime import datetime
from typing import Any, cast

from iris.base import BaseConnector, SyncResult
from iris.config import IrisConfig
from iris.models import Bookmark

logger = logging.getLogger(__name__)

POCKET_API_BASE = "https://getpocket.com/v3"
POCKET_API_TIMEOUT = 30


# ── Pocket API v3 helpers ───────────────────────────────────────────


def _pocket_post(endpoint: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """POST to the Pocket API v3 endpoint.

    Args:
        endpoint: API path (e.g., '/get')
        payload: JSON body (must include consumer_key and access_token)

    Returns:
        Parsed JSON response dict, or None on failure.
    """
    url = f"{POCKET_API_BASE}{endpoint}"
    body = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(  # noqa: S310
        url,
        data=body,
        headers={
            "Content-Type": "application/json; charset=UTF8",
            "X-Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=POCKET_API_TIMEOUT) as resp:  # noqa: S310
            data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
            if data.get("error"):
                logger.warning("Pocket API error: %s", data["error"])
                return None
            return data
    except Exception as e:
        logger.warning("Pocket API request failed [%s]: %s", endpoint, e)
        return None


def _parse_timestamp(ts: str | int | None) -> str:
    """Convert Pocket Unix timestamp (string or int) to YYYY-MM-DD string."""
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return ""


def _pocket_item_to_bookmark(item_id: str, item: dict[str, Any], platform: str) -> Bookmark:
    """Map a Pocket API item dict to a Bookmark instance.

    Pocket item fields used:
        - item_id (str)
        - given_title / resolved_title (str)
        - given_url / resolved_url (str)
        - excerpt (str)
        - time_added / time_updated (Unix timestamp string)
        - tags (dict of {tag_name: {tag: tag_name, ...}})
    """
    title = item.get("resolved_title", "") or item.get("given_title", "") or ""
    url = item.get("given_url", "") or item.get("resolved_url", "") or ""
    excerpt = item.get("excerpt", "") or ""
    tags_raw = item.get("tags", None) or {}

    # Append tags to description if present
    description = excerpt
    if tags_raw:
        tag_names = sorted(tags_raw.keys())
        if tag_names:
            tags_str = ", ".join(tag_names)
            if description:
                description = f"{description}\n\nTags: {tags_str}"
            else:
                description = f"Tags: {tags_str}"

    return Bookmark(
        id=str(item_id),
        title=title,
        url=url,
        description=description,
        platform=platform,
        created_at=_parse_timestamp(item.get("time_added")),
        updated_at=_parse_timestamp(item.get("time_updated")),
    )


def _build_params(
    consumer_key: str,
    access_token: str,
    state: str = "unread",
    sort: str = "newest",
    count: int = 20,
    offset: int | None = None,
    search: str | None = None,
    item_id: str | None = None,
) -> dict[str, Any]:
    """Build the request body for the Pocket /v3/get endpoint."""
    params: dict[str, Any] = {
        "consumer_key": consumer_key,
        "access_token": access_token,
        "state": state,
        "sort": sort,
        "count": count,
    }
    if offset is not None:
        params["offset"] = offset
    if search:
        params["search"] = search
    if item_id:
        params["item_id"] = item_id
    return params


# ── Connector ───────────────────────────────────────────────────────


class PocketConnector(BaseConnector):
    """Connector for Pocket (getpocket.com) — reads saved bookmarks.

    Uses the official Pocket API v3 with consumer_key + access_token
    authentication (both passed in the request body).

    Environment variables:
        POCKET_CONSUMER_KEY  — Pocket API consumer key
        POCKET_ACCESS_TOKEN  — Pocket access token (from OAuth flow)

    Config file keys (~/.iris/config.json):
        pocket.consumer_key
        pocket.access_token
    """

    name = "pocket"
    display_name = "Pocket"

    def __init__(self, config: IrisConfig | None = None):
        self._config = config or IrisConfig()
        self._last_sync_at: str = ""

        # Read credentials: env vars first, then config file
        self._consumer_key = self._get_credential("POCKET_CONSUMER_KEY", "pocket.consumer_key")
        self._access_token = self._get_credential("POCKET_ACCESS_TOKEN", "pocket.access_token")

    def _get_credential(self, env_var: str, config_key: str) -> str:
        """Read a credential from environment variable or config file."""
        val = os.environ.get(env_var)
        if val:
            return val
        return cast("str", self._config.get(config_key, default=""))

    # ── Availability ────────────────────────────────────────────

    def is_available(self) -> bool:
        """Check if Pocket credentials are configured."""
        return bool(self._consumer_key) and bool(self._access_token)

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
    ) -> list[Bookmark]:
        """List unread bookmarks from Pocket, newest first.

        Args:
            limit: Max items to return (default: 20).
            cursor: Pagination offset as a string-encoded integer.

        Returns:
            List of Bookmark instances.
        """
        if not self.is_available():
            logger.warning("Pocket connector not available — missing credentials")
            return []

        offset = int(cursor) if cursor else None
        params = _build_params(
            consumer_key=self._consumer_key,
            access_token=self._access_token,
            state="unread",
            sort="newest",
            count=limit,
            offset=offset,
        )

        result = _pocket_post("/get", params)
        if not result:
            return []

        items = self._parse_item_list(result)
        return items[:limit]

    def _parse_item_list(self, result: dict[str, Any]) -> list[Bookmark]:
        """Parse the Pocket /v3/get response list into Bookmark instances."""
        raw_list = result.get("list", {}) or {}
        bookmarks: list[Bookmark] = []
        for item_id, item_data in raw_list.items():
            try:
                bm = _pocket_item_to_bookmark(item_id, item_data, self.name)
                bookmarks.append(bm)
            except Exception as e:
                logger.debug("Failed to parse Pocket item %s: %s", item_id, e)
                continue
        # Sort by created_at descending (newest first)
        bookmarks.sort(key=lambda x: x.created_at, reverse=True)
        return bookmarks

    # ── Get single item ─────────────────────────────────────────

    def get_item(self, id: str) -> Bookmark | None:
        """Get a single Pocket item by its item_id.

        Args:
            id: Pocket item_id string.

        Returns:
            Bookmark instance or None if not found.
        """
        if not self.is_available():
            return None

        params = _build_params(
            consumer_key=self._consumer_key,
            access_token=self._access_token,
            state="all",
            count=1,
            item_id=id,
        )

        result = _pocket_post("/get", params)
        if not result:
            return None

        items = self._parse_item_list(result)
        return items[0] if items else None

    # ── Search ──────────────────────────────────────────────────

    def search(self, query: str, limit: int = 10) -> list[Bookmark]:
        """Search Pocket bookmarks by query string.

        Args:
            query: Search keyword (Pocket searches titles and URLs).
            limit: Max results to return (default: 10).

        Returns:
            List of matching Bookmark instances.
        """
        if not self.is_available():
            return []

        params = _build_params(
            consumer_key=self._consumer_key,
            access_token=self._access_token,
            state="all",
            sort="newest",
            count=limit,
            search=query,
        )

        result = _pocket_post("/get", params)
        if not result:
            return []

        items = self._parse_item_list(result)
        return items[:limit]

    # ── Sync ────────────────────────────────────────────────────

    def sync(self, dry_run: bool = False) -> SyncResult:
        """Pull unread bookmarks from Pocket.

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
                message="Pocket credentials not configured. Set POCKET_CONSUMER_KEY and POCKET_ACCESS_TOKEN.",
                errors=["Missing credentials"],
            )

        try:
            # Fetch unread items
            params = _build_params(
                consumer_key=self._consumer_key,
                access_token=self._access_token,
                state="unread",
                sort="newest",
                count=30,  # sync fetches a reasonable batch
            )

            result = _pocket_post("/get", params)
            if not result:
                return SyncResult(
                    connector_name=self.name,
                    success=False,
                    message="Failed to fetch Pocket items.",
                    errors=["API request failed"],
                )

            items = self._parse_item_list(result)
            count = len(items)

            if dry_run:
                return SyncResult(
                    connector_name=self.name,
                    items_found=count,
                    success=True,
                    message=f"Dry run: {count} unread Pocket items would be synced.",
                )

            # Record sync time
            self._last_sync_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            return SyncResult(
                connector_name=self.name,
                items_found=count,
                success=True,
                message=f"Synced {count} unread Pocket bookmarks.",
            )

        except Exception as e:
            logger.exception("Pocket sync failed")
            return SyncResult(
                connector_name=self.name,
                success=False,
                message=f"Pocket sync failed: {e}",
                errors=[str(e)],
            )

    # ── Status ──────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        """Return connector health and stats.

        Returns a dict with:
            - configured: whether credentials are present
            - last_sync_at: timestamp of last sync
            - total_count: approximate total bookmark count
            - unread_count: approximate unread bookmark count
            - note: any relevant info about the data

        Note: Pocket API v3 does not expose exact counts directly,
        so counts are estimated by fetching sample data.
        """
        if not self.is_available():
            return {
                "configured": False,
                "last_sync_at": self._last_sync_at,
                "total_count": 0,
                "unread_count": 0,
                "note": "Credentials not configured.",
            }

        try:
            # Fetch a small batch to estimate counts
            unread_params = _build_params(
                consumer_key=self._consumer_key,
                access_token=self._access_token,
                state="unread",
                sort="newest",
                count=1,
            )
            all_params = _build_params(
                consumer_key=self._consumer_key,
                access_token=self._access_token,
                state="all",
                sort="newest",
                count=1,
            )

            # Make both requests
            unread_result = _pocket_post("/get", unread_params)
            all_result = _pocket_post("/get", all_params)

            unread_items = self._parse_item_list(unread_result) if unread_result else []
            all_items = self._parse_item_list(all_result) if all_result else []

            # Check complete flag to determine if there might be more items
            unread_complete = bool(unread_result.get("complete", 1)) if unread_result else True
            all_complete = bool(all_result.get("complete", 1)) if all_result else True

            return {
                "configured": True,
                "last_sync_at": self._last_sync_at,
                "total_count": len(all_items),
                "unread_count": len(unread_items),
                "has_more_unread": not unread_complete,
                "has_more_total": not all_complete,
                "note": "Counts are based on latest API response; Pocket does not expose exact totals.",
            }

        except Exception as e:
            logger.warning("Failed to get Pocket status: %s", e)
            return {
                "configured": True,
                "last_sync_at": self._last_sync_at,
                "total_count": -1,
                "unread_count": -1,
                "note": f"Status check failed: {e}",
            }
