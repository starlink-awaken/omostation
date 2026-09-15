"""RSS/Feeds connector — wraps blogwatcher-cli for RSS feed management."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import time
from typing import Any

from iris.base import BaseConnector, SyncResult
from iris.models import Article, KnowledgeArtifact

logger = logging.getLogger(__name__)


def _run_blogwatcher(args: list[str]) -> str:
    """Run blogwatcher-cli with given args and return stdout.

    Raises FileNotFoundError if blogwatcher-cli is not installed.
    Raises subprocess.CalledProcessError on non-zero exit.
    """
    cli = shutil.which("blogwatcher-cli")
    if not cli:
        raise FileNotFoundError("blogwatcher-cli not found on PATH")
    result = subprocess.run(
        [cli, *args],
        capture_output=True,
        text=True,
        timeout=30,
    )
    result.check_returncode()
    return result.stdout


def _parse_articles(output: str) -> list[dict[str, str]]:
    """Parse blogwatcher-cli articles text output into structured dicts.

    Expected output format::

        [1] [new] Article Title
            Blog: xkcd
            URL: https://example.com
            Published: 2026-04-02

        [2] [read] Another Article
            Blog: some blog
            URL: https://...
            Published: 2026-03-15

    Returns list of dicts with keys: id, status, title, blog, url, published.
    """
    articles: list[dict[str, str]] = []
    # Each article starts with a line like "[N] [status] Title"
    # followed by indented key: value lines.
    pattern = re.compile(
        r"^\[(\d+)\]\s+\[([^\]]+)\]\s+(.+?)$",
        re.MULTILINE,
    )

    lines = output.splitlines()
    current: dict[str, str] | None = None

    for line in lines:
        # Check if this is a new article header
        match = pattern.match(line.strip())
        if match:
            # Save previous article if exists
            if current is not None:
                articles.append(current)
            current = {
                "id": match.group(1),
                "status": match.group(2),
                "title": match.group(3).strip(),
                "blog": "",
                "url": "",
                "published": "",
            }
            continue

        # Parse indented fields like "    Blog: xkcd"
        if current is not None and line.startswith("    "):
            stripped = line.strip()
            if stripped.startswith("Blog:"):
                current["blog"] = stripped[5:].strip()
            elif stripped.startswith("URL:"):
                current["url"] = stripped[4:].strip()
            elif stripped.startswith("Published:"):
                current["published"] = stripped[10:].strip()

    # Don't forget the last article
    if current is not None:
        articles.append(current)

    return articles


class RssConnector(BaseConnector):
    """Connector for RSS feeds via blogwatcher-cli.

    Wraps the blogwatcher-cli command-line tool to list, search,
    and sync articles from configured RSS/Atom feeds.
    """

    name = "rss"
    display_name = "RSS Feeds"

    def __init__(self) -> None:
        self._available: bool | None = None
        self._last_sync: str | None = None

    # ── Availability ─────────────────────────────────────────────────

    def is_available(self) -> bool:
        """Check if blogwatcher-cli is installed on PATH."""
        if self._available is not None:
            return self._available
        self._available = shutil.which("blogwatcher-cli") is not None
        if not self._available:
            logger.info("RSS connector unavailable: blogwatcher-cli not found")
        return self._available

    # ── List / Read ──────────────────────────────────────────────────

    def list_items(
        self,
        limit: int = 20,
        cursor: str | None = None,
        tag: str | None = None,
        folder: str | None = None,
        subdir: str | None = None,
        chat_id: str | None = None,
    ) -> list[KnowledgeArtifact]:
        """List articles from blogwatcher.

        Args:
            limit: Maximum number of articles to return.
            cursor: Pagination cursor — if provided, skip articles with
                    id <= cursor (cursor is an article id string).

        Returns:
            List of Article objects.
        """
        if not self.is_available():
            return []

        try:
            output = _run_blogwatcher(["articles"])
        except (FileNotFoundError, subprocess.CalledProcessError, TimeoutError) as exc:
            logger.warning("Failed to list RSS articles: %s", exc)
            return []

        raw_articles = _parse_articles(output)

        # Apply cursor-based pagination
        if cursor:
            try:
                cursor_int = int(cursor)
                raw_articles = [a for a in raw_articles if int(a["id"]) > cursor_int]
            except ValueError:
                pass  # Invalid cursor — ignore

        # Apply limit
        raw_articles = raw_articles[:limit]

        return [self._to_article(a) for a in raw_articles]

    def get_item(self, id: str) -> Article | None:
        """Get a single article by its ID.

        Args:
            id: Article ID (the numeric id from blogwatcher, with or
                without the 'rss/' prefix).

        Returns:
            Article if found, None otherwise.
        """
        # Strip the 'rss/' prefix if present
        article_id = id.removeprefix("rss/").removeprefix("rss:")

        if not self.is_available():
            return None

        try:
            output = _run_blogwatcher(["articles"])
        except (FileNotFoundError, subprocess.CalledProcessError, TimeoutError) as exc:
            logger.warning("Failed to get RSS article %s: %s", id, exc)
            return None

        raw_articles = _parse_articles(output)
        for a in raw_articles:
            if a["id"] == article_id:
                return self._to_article(a)

        return None

    def search(self, query: str, limit: int = 10) -> list[KnowledgeArtifact]:
        """Search articles by keyword.

        Calls ``blogwatcher-cli articles`` and greps the output
        for the query string (case-insensitive match on title, blog,
        and URL fields).

        Args:
            query: Keyword to search for.
            limit: Maximum results to return.

        Returns:
            List of matching Article objects.
        """
        if not self.is_available():
            return []

        try:
            output = _run_blogwatcher(["articles"])
        except (FileNotFoundError, subprocess.CalledProcessError, TimeoutError) as exc:
            logger.warning("Failed to search RSS articles: %s", exc)
            return []

        raw_articles = _parse_articles(output)

        query_lower = query.lower()
        matched = [
            a
            for a in raw_articles
            if query_lower in a.get("title", "").lower()
            or query_lower in a.get("blog", "").lower()
            or query_lower in a.get("url", "").lower()
        ]

        return [self._to_article(a) for a in matched[:limit]]

    # ── Sync ─────────────────────────────────────────────────────────

    def sync(self, dry_run: bool = False) -> SyncResult:
        """Scan for new articles from all configured feeds.

        Args:
            dry_run: If True, report what would be done without executing.

        Returns:
            SyncResult with count of new articles found.
        """
        if not self.is_available():
            return SyncResult(
                connector_name=self.name,
                success=False,
                errors=["blogwatcher-cli not installed"],
                message="Cannot sync: blogwatcher-cli not found on PATH",
            )

        if dry_run:
            # In dry-run mode, count current articles without scanning
            try:
                output = _run_blogwatcher(["articles"])
                raw = _parse_articles(output)
                return SyncResult(
                    connector_name=self.name,
                    items_found=len(raw),
                    success=True,
                    message=f"Dry-run: {len(raw)} article(s) available to sync",
                )
            except (FileNotFoundError, subprocess.CalledProcessError, TimeoutError) as exc:
                return SyncResult(
                    connector_name=self.name,
                    success=False,
                    errors=[str(exc)],
                    message=f"Dry-run failed: {exc}",
                )

        try:
            _run_blogwatcher(["scan"])
            self._last_sync = time.strftime("%Y-%m-%dT%H:%M:%SZ")
            return SyncResult(
                connector_name=self.name,
                success=True,
                message="RSS feeds scanned successfully",
            )
        except subprocess.CalledProcessError as exc:
            return SyncResult(
                connector_name=self.name,
                success=False,
                errors=[f"blogwatcher-cli scan exit code {exc.returncode}: {exc.stderr}"],
                message=f"Scan failed: {exc.stderr}",
            )
        except (FileNotFoundError, TimeoutError) as exc:
            return SyncResult(
                connector_name=self.name,
                success=False,
                errors=[str(exc)],
                message=f"Scan failed: {exc}",
            )

    # ── Status ───────────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        """Return connector health and feed/article statistics.

        Calls ``blogwatcher-cli blogs`` and ``blogwatcher-cli articles``
        for counts.

        Returns:
            Dict with keys: available, blog_count, article_count,
            last_sync, blog_names.
        """
        if not self.is_available():
            return {
                "available": False,
                "blog_count": 0,
                "article_count": 0,
                "last_sync": self._last_sync,
                "blog_names": [],
                "note": "blogwatcher-cli not installed",
            }

        blog_count = 0
        blog_names: list[str] = []
        article_count = 0

        try:
            blogs_output = _run_blogwatcher(["blogs"])
            # Parse blog list — each line is a blog name or "[N] Blog Name"
            for line in blogs_output.splitlines():
                line = line.strip()
                if line:
                    # Lines like "[1] xkcd" or just blog name
                    blog_match = re.match(r"^\[\d+\]\s+(.+)$", line)
                    if blog_match:
                        blog_names.append(blog_match.group(1).strip())
                    else:
                        blog_names.append(line)
            blog_count = len(blog_names)
        except (FileNotFoundError, subprocess.CalledProcessError, TimeoutError) as exc:
            logger.debug("Could not get blogs list: %s", exc)

        try:
            articles_output = _run_blogwatcher(["articles"])
            raw_articles = _parse_articles(articles_output)
            article_count = len(raw_articles)
        except (FileNotFoundError, subprocess.CalledProcessError, TimeoutError) as exc:
            logger.debug("Could not get articles list: %s", exc)

        return {
            "available": True,
            "blog_count": blog_count,
            "article_count": article_count,
            "last_sync": self._last_sync,
            "blog_names": blog_names[:20],  # Cap names for readability
        }

    # ── RSS-specific operations ──────────────────────────────────────

    def list_blogs(self) -> list[dict[str, str]]:
        """List configured blogs/feeds.

        Calls ``blogwatcher-cli blogs`` and returns parsed results.

        Returns:
            List of dicts with keys: id, name (blog name/URL).
        """
        if not self.is_available():
            return []

        try:
            output = _run_blogwatcher(["blogs"])
        except (FileNotFoundError, subprocess.CalledProcessError, TimeoutError) as exc:
            logger.warning("Failed to list RSS blogs: %s", exc)
            return []

        blogs: list[dict[str, str]] = []
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            match = re.match(r"^\[(\d+)\]\s+(.+)$", line)
            if match:
                blogs.append(
                    {
                        "id": match.group(1),
                        "name": match.group(2).strip(),
                    }
                )
            else:
                blogs.append(
                    {
                        "id": "",
                        "name": line,
                    }
                )

        return blogs

    # ── Internal helpers ─────────────────────────────────────────────

    @staticmethod
    def _to_article(raw: dict[str, str]) -> Article:
        """Convert a parsed article dict to an Article model."""
        article_id = raw.get("id", "0")
        title = raw.get("title", "")
        url = raw.get("url", "")
        blog = raw.get("blog", "")
        published = raw.get("published", "")
        summary = raw.get("summary", "")

        # Content = URL + summary
        content_parts = []
        if url:
            content_parts.append(url)
        if summary:
            content_parts.append("")
            content_parts.append(summary)
        content = "\n".join(content_parts) if content_parts else ""

        return Article(
            id=f"rss/{article_id}",
            title=title,
            platform="rss",
            content=content,
            url=url,
            author=blog,
            created_at=published,
            updated_at=published,
        )
