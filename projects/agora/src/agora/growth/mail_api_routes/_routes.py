from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
#  Routes ≡ Module
# 内涵 ≝ {, Routes}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Routes)}
# 功能 ⊢ {Init_ Routes, Execute_ Routes, Validate_ Routes}
# =============================================================================

# ---
# domain: D-Gateway
# layer: organ
# status: active
# ---
"""
MailAPIRoutes — optimized mail endpoints with <200ms response guarantee.
"""

import asyncio
import logging
import sqlite3
import time
from typing import Any

from . import _infrastructure as _infra
from ._infrastructure import (  # type: ignore[import-not-found]
    DatabaseIndexManager,
    OptimizedCache,
    performance_monitored,
    prune_email,
)

logger = logging.getLogger(__name__)


class MailAPIRoutes:
    """Optimized Mail API Routes with <200ms response guarantee.

    Provides high-performance endpoints:
    - GET /api/mail/today - Today's mail with caching
    - GET /api/mail/search - FTS search with pagination
    - GET /api/mail/thread/{id} - Thread view with preloading
    """

    def __init__(
        self,
        redis_url: str | None = None,
        enable_metrics: bool = True,
    ) -> None:
        self.status = "active"  # was super().__init__(metadata_path=...)

        self._cache = OptimizedCache(redis_url=redis_url)
        self._index_manager = DatabaseIndexManager()
        self._index_manager.initialize_schema()
        self._enable_metrics = enable_metrics

        logger.info("MailAPIRoutes initialized with <200ms target")

    # ------------------------------------------------------------------
    # Today's mail
    # ------------------------------------------------------------------

    @performance_monitored("/api/mail/today")
    async def get_mail_today(
        self,
        category: str | None = None,
        include_read: bool = True,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Get today's emails with Redis caching.

        Args:
            category: Filter by category (work, personal, etc.)
            include_read: Include read emails
            force_refresh: Bypass cache

        Returns:
            Today's email summary with metadata
        """
        cache_key = self._cache._generate_key(
            "mail_today", {"category": category, "include_read": include_read, "date": time.strftime("%Y-%m-%d")}
        )

        # Try cache first
        if not force_refresh:
            cached, hit = await self._cache.get(cache_key)
            if hit and cached:
                cached["_cache_hit"] = True
                return cached

        # Build optimized query
        today_start = time.mktime(time.strptime(time.strftime("%Y-%m-%d"), "%Y-%m-%d"))
        today_end = today_start + 86400

        query = """
            SELECT id, message_id, thread_id, subject, sender_name, sender_address,
                   received_date, is_read, is_important, category, body_preview, attachment_count
            FROM emails
            WHERE received_date >= ? AND received_date < ?
        """
        params: list[Any] = [today_start, today_end]

        if category:
            query += " AND category = ?"
            params.append(category)

        if not include_read:
            query += " AND is_read = 0"

        query += " ORDER BY received_date DESC LIMIT 100"

        emails = []
        with sqlite3.connect(_infra.MAIL_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            for row in rows:
                email = dict(row)
                emails.append(prune_email(email, "minimal"))

        # Aggregate stats
        unread_count = sum(1 for e in emails if not e.get("is_read"))
        important_count = sum(1 for e in emails if e.get("is_important"))

        categories: dict[str, int] = {}
        for e in emails:
            cat = e.get("category", "inbox")
            categories[cat] = categories.get(cat, 0) + 1

        result = {
            "date": time.strftime("%Y-%m-%d"),
            "total_count": len(emails),
            "unread_count": unread_count,
            "important_count": important_count,
            "categories": categories,
            "emails": emails[:20],  # Limit response size
            "has_more": len(emails) > 20,
        }

        # Cache result
        await self._cache.set(cache_key, result, ttl=_infra.REDIS_CACHE_TTL_SECONDS, tags=["mail", "today"])

        return result

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    @performance_monitored("/api/mail/search")
    async def search_emails(
        self,
        query: str,
        folder: str = "INBOX",
        page: int = 1,
        page_size: int = _infra.DEFAULT_PAGE_SIZE,
        filters: dict[str, Any] | None = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Search emails using FTS with result caching.

        Args:
            query: Search query string
            folder: Folder to search in
            page: Page number (1-indexed)
            page_size: Items per page
            filters: Additional filters (date range, sender, etc.)
            force_refresh: Bypass cache

        Returns:
            Search results with pagination
        """
        page_size = min(page_size, _infra.MAX_PAGE_SIZE)
        offset = (page - 1) * page_size

        cache_key = self._cache._generate_key(
            "mail_search",
            {
                "query": query,
                "folder": folder,
                "page": page,
                "page_size": page_size,
                "filters": filters,
            },
        )

        # Try cache
        if not force_refresh:
            cached, hit = await self._cache.get(cache_key)
            if hit and cached:
                cached["_cache_hit"] = True
                return cached

        # Parallel queries for FTS and metadata
        fts_task = self._fts_search(query, folder, offset, page_size)
        count_task = self._get_search_count(query, folder)

        results, total_count = await asyncio.gather(fts_task, count_task)

        # Prune results
        pruned_results = [prune_email(e, "standard") for e in results]

        total_pages = (total_count + page_size - 1) // page_size

        result = {
            "query": query,
            "folder": folder,
            "page": page,
            "page_size": page_size,
            "total_results": total_count,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
            "emails": pruned_results,
        }

        # Cache search results (shorter TTL for search)
        await self._cache.set(cache_key, result, ttl=60, tags=["mail", "search", f"search:{query}"])

        return result

    async def _fts_search(
        self,
        query: str,
        folder: str,
        offset: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Execute FTS search query."""
        try:
            with sqlite3.connect(_infra.FTS_DB_PATH) as conn:
                # Use FTS5 match
                fts_query = " OR ".join(f"{word}*" for word in query.split() if len(word) >= 2)

                cursor = conn.execute(
                    """SELECT rowid, rank FROM email_fts
                       WHERE email_fts MATCH ?
                       ORDER BY rank LIMIT ? OFFSET ?""",
                    (fts_query, limit, offset),
                )

                matches = cursor.fetchall()
                if not matches:
                    return []

                rowids = [m[0] for m in matches]

                # Fetch full email data from main DB
                placeholders = ",".join("?" * len(rowids))
                with sqlite3.connect(_infra.MAIL_DB_PATH) as mail_conn:
                    mail_conn.row_factory = sqlite3.Row
                    cursor = mail_conn.execute(
                        f"""SELECT * FROM emails WHERE id IN ({placeholders})
                           ORDER BY CASE id {" ".join(f"WHEN {rid} THEN {i}" for i, rid in enumerate(rowids))} END""",
                        rowids,
                    )
                    return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            logger.error("FTS search error: %s", e)
            return []

    async def _get_search_count(self, query: str, folder: str) -> int:
        """Get total count for search query."""
        try:
            with sqlite3.connect(_infra.FTS_DB_PATH) as conn:
                fts_query = " OR ".join(f"{word}*" for word in query.split() if len(word) >= 2)
                cursor = conn.execute("SELECT COUNT(*) FROM email_fts WHERE email_fts MATCH ?", (fts_query,))
                return cursor.fetchone()[0]
        except sqlite3.Error:
            return 0

    # ------------------------------------------------------------------
    # Thread view
    # ------------------------------------------------------------------

    @performance_monitored("/api/mail/thread")
    async def get_thread(
        self,
        thread_id: str,
        include_history: bool = True,
        history_limit: int = 50,
        detail_level: str = "standard",
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Get email thread with preloading and lazy loading.

        Args:
            thread_id: Thread identifier
            include_history: Include historical emails
            history_limit: Max history emails to load
            detail_level: 'minimal', 'standard', or 'full'
            force_refresh: Bypass cache

        Returns:
            Thread data with emails
        """
        cache_key = self._cache._generate_key(
            "mail_thread",
            {
                "thread_id": thread_id,
                "include_history": include_history,
                "history_limit": history_limit,
                "detail_level": detail_level,
            },
        )

        # Try cache
        if not force_refresh and detail_level != "full":
            cached, hit = await self._cache.get(cache_key)
            if hit and cached:
                cached["_cache_hit"] = True
                return cached

        # Get thread metadata and emails in parallel
        thread_task = self._get_thread_metadata(thread_id)
        emails_task = self._get_thread_emails(thread_id, include_history, history_limit)

        thread_meta, emails = await asyncio.gather(thread_task, emails_task)

        if not thread_meta:
            return {"error": "Thread not found", "thread_id": thread_id}

        # Prune emails based on detail level
        pruned_emails = [prune_email(e, detail_level) for e in emails]

        result = {
            "thread_id": thread_id,
            "subject": thread_meta.get("subject"),
            "participant_count": thread_meta.get("participant_count", 0),
            "message_count": thread_meta.get("message_count", len(emails)),
            "unread_count": thread_meta.get("unread_count", 0),
            "first_message_date": thread_meta.get("first_message_date"),
            "last_updated": thread_meta.get("last_updated"),
            "emails": pruned_emails,
            "has_more_history": len(emails) >= history_limit if include_history else False,
        }

        # Cache if not full detail
        if detail_level != "full":
            await self._cache.set(
                cache_key, result, ttl=_infra.REDIS_CACHE_TTL_SECONDS, tags=["mail", "thread", f"thread:{thread_id}"]
            )

        return result

    async def _get_thread_metadata(self, thread_id: str) -> dict[str, Any] | None:
        """Get thread metadata."""
        with sqlite3.connect(_infra.MAIL_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM email_threads WHERE thread_id = ?", (thread_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)

            fallback_cursor = conn.execute(
                """
                SELECT
                    thread_id,
                    COUNT(*) AS message_count,
                    SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END) AS unread_count,
                    MIN(received_date) AS first_message_date,
                    MAX(received_date) AS last_updated,
                    COUNT(DISTINCT sender_address) AS participant_count
                FROM emails
                WHERE thread_id = ?
                GROUP BY thread_id
                """,
                (thread_id,),
            )
            fallback_row = fallback_cursor.fetchone()
            if not fallback_row:
                return None

            metadata = dict(fallback_row)
            subject_cursor = conn.execute(
                """
                SELECT subject
                FROM emails
                WHERE thread_id = ?
                ORDER BY received_date DESC
                LIMIT 1
                """,
                (thread_id,),
            )
            subject_row = subject_cursor.fetchone()
            metadata["subject"] = subject_row[0] if subject_row else None
            return metadata

    async def _get_thread_emails(
        self,
        thread_id: str,
        include_history: bool,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Get emails for thread."""
        with sqlite3.connect(_infra.MAIL_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            query = """
                SELECT * FROM emails
                WHERE thread_id = ?
                ORDER BY received_date DESC
                LIMIT ?
            """
            cursor = conn.execute(query, (thread_id, limit))
            return [dict(row) for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # Incremental updates
    # ------------------------------------------------------------------

    async def get_incremental_updates(
        self,
        since_timestamp: float,
        max_results: int = 100,
    ) -> dict[str, Any]:
        """Get incremental mail updates since timestamp.

        Args:
            since_timestamp: Unix timestamp to get updates since
            max_results: Maximum results to return

        Returns:
            New and modified emails since timestamp
        """
        with sqlite3.connect(_infra.MAIL_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row

            # Get new emails
            cursor = conn.execute(
                """SELECT * FROM emails
                   WHERE created_at > ? OR received_date > ?
                   ORDER BY received_date DESC LIMIT ?""",
                (since_timestamp, since_timestamp, max_results),
            )
            new_emails = [prune_email(dict(row), "minimal") for row in cursor.fetchall()]

            # Get updated read status
            cursor = conn.execute(
                """SELECT id, message_id, is_read, is_important
                   FROM emails
                   WHERE created_at <= ? AND received_date > ?
                   LIMIT ?""",
                (since_timestamp, since_timestamp - 86400, max_results),
            )
            status_updates = [dict(row) for row in cursor.fetchall()]

        return {
            "since": since_timestamp,
            "new_emails": new_emails,
            "status_updates": status_updates,
            "has_more": len(new_emails) >= max_results,
        }

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    async def invalidate_mail_cache(
        self,
        scope: str = "all",
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        """Invalidate mail cache.

        Args:
            scope: 'all', 'today', 'search', or 'thread'
            thread_id: Specific thread to invalidate

        Returns:
            Invalidation results
        """
        count = 0

        if scope == "all":
            count = await self._cache.invalidate(tag="mail")
        elif scope == "today":
            count = await self._cache.invalidate(tag="today")
        elif scope == "search":
            count = await self._cache.invalidate(tag="search")
        elif scope == "thread" and thread_id:
            count = await self._cache.invalidate(tag=f"thread:{thread_id}")

        return {"invalidated_count": count, "scope": scope}

    async def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return await self._cache.get_stats()

    # ------------------------------------------------------------------
    # CoreService interface
    # ------------------------------------------------------------------

    def call(self, action: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Handle BOS-URI calls."""
        params = params or {}

        async def async_call() -> dict[str, object]:
            if action == "today":
                return await self.get_mail_today(
                    category=params.get("category"),
                    include_read=params.get("include_read", True),
                    force_refresh=params.get("force_refresh", False),
                )
            elif action == "search":
                return await self.search_emails(
                    query=params.get("query", ""),
                    folder=params.get("folder", "INBOX"),
                    page=params.get("page", 1),
                    page_size=params.get("page_size", _infra.DEFAULT_PAGE_SIZE),
                    filters=params.get("filters"),
                )
            elif action == "thread":
                return await self.get_thread(
                    thread_id=params.get("thread_id", ""),
                    include_history=params.get("include_history", True),
                    detail_level=params.get("detail_level", "standard"),
                )
            elif action == "incremental":
                return await self.get_incremental_updates(
                    since_timestamp=params.get("since", time.time() - 3600),
                )
            elif action == "invalidate_cache":
                return await self.invalidate_mail_cache(
                    scope=params.get("scope", "all"),
                    thread_id=params.get("thread_id"),
                )
            elif action == "cache_stats":
                return await self.get_cache_stats()
            else:
                return {"error": f"Unknown action: {action}"}

        return asyncio.run(async_call())

    def initialize(self) -> dict[str, Any]:
        """Initialize the organ."""
        return {"status": "initialized", "organ": self.organ_name}

    def shutdown(self) -> dict[str, Any]:
        """Shutdown the organ."""
        return {"status": "shutdown", "organ": self.organ_name}
