"""Search backend implementations — SearXNG, Semantic Scholar, DuckDuckGo, Jina, BS4."""

from __future__ import annotations

import atexit
import contextlib
import os
from typing import Any, cast

import httpx

# Shared httpx helpers — reduce boilerplate across 7 backends
# Connection pooling: one AsyncClient per domain for reuse
import structlog as _structlog
from bs4 import BeautifulSoup

from minerva.search.engine import SearchResult

_log = _structlog.get_logger(__name__)

_client_cache: dict[str, httpx.AsyncClient] = {}
_domain_last_call: dict[str, float] = {}  # Rate limiting: domain → last call timestamp
_MIN_CALL_INTERVAL = 2.0  # Minimum seconds between calls to same domain
_MAX_DOMAIN_CACHE_SIZE = 50  # Prevent unbounded growth of _domain_last_call


@atexit.register
def _cleanup_clients() -> None:
    """Close all pooled HTTP clients on process exit."""
    import asyncio

    for client in _client_cache.values():
        with contextlib.suppress(Exception):
            asyncio.get_event_loop().run_until_complete(client.aclose())
    _client_cache.clear()


def _get_client(domain: str, timeout: int = 30) -> httpx.AsyncClient:
    """Get or create a pooled httpx client for a domain."""
    if domain not in _client_cache:
        _client_cache[domain] = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )
    return _client_cache[domain]


async def _api_get(url: str, params: dict | None = None, headers: dict | None = None, timeout: int = 15) -> dict | None:
    """GET JSON from an API. Exponential backoff on 429. Returns None on persistent error."""
    import asyncio
    import time
    from urllib.parse import urlparse

    domain = urlparse(url).netloc or url

    # Rate limit: enforce minimum interval between calls to same domain
    now = time.monotonic()
    last = _domain_last_call.get(domain, 0)
    gap = _MIN_CALL_INTERVAL - (now - last)
    if gap > 0:
        await asyncio.sleep(gap)
    # Prune cache if too large (LRU: drop oldest entries)
    if len(_domain_last_call) > _MAX_DOMAIN_CACHE_SIZE:
        oldest = sorted(_domain_last_call.items(), key=lambda x: x[1])[: _MAX_DOMAIN_CACHE_SIZE // 2]
        _domain_last_call.clear()
        _domain_last_call.update(oldest)

    for attempt in range(3):
        try:
            client = _get_client(domain, timeout)
            resp = await client.get(url, params=params, headers=headers)
            if resp.status_code == 429:
                if attempt < 2:
                    # Respect Retry-After header, fall back to exponential backoff
                    retry_after = resp.headers.get("Retry-After", "")
                    try:
                        wait = int(retry_after)
                    except ValueError:
                        wait = 2 ** (attempt + 3)  # 8s → 16s → 32s
                    _log.debug("rate_limited", url=url[:60], attempt=attempt, wait_s=wait)
                    await asyncio.sleep(wait)
                    continue
                # Last attempt also failed — log and return
                _log.warning("rate_limited_persistent", url=url[:60])
                return None
            resp.raise_for_status()
            _domain_last_call[domain] = time.monotonic()
            return cast("dict[Any, Any] | None", resp.json())
        except (httpx.HTTPError, ConnectionError, TimeoutError) as e:
            _log.debug("api_get_failed", url=url[:80], error=str(e)[:100])
            _domain_last_call[domain] = time.monotonic()
            return None
    _domain_last_call[domain] = time.monotonic()
    return None


async def _api_post(url: str, json_data: dict, headers: dict | None = None, timeout: int = 20) -> dict | None:
    """POST JSON to an API. Returns None on any error."""
    from urllib.parse import urlparse

    domain = urlparse(url).netloc or url
    try:
        client = _get_client(domain, timeout)
        resp = await client.post(url, json=json_data, headers=headers)
        resp.raise_for_status()
        return cast("dict[Any, Any] | None", resp.json())
    except (httpx.HTTPError, ConnectionError, TimeoutError) as e:
        _log.debug("api_post_failed", url=url[:80], error=str(e)[:100])
        return None


# ============================================================
# SearXNG Backend
# ============================================================


async def search_searxng(
    query: str,
    base_url: str = f"http://localhost:{os.environ.get('ONTODERIVE_WEB_PORT', '8080')}",
    max_results: int = 10,
) -> list[SearchResult]:
    """Search via self-hosted SearXNG meta-search engine.

    SearXNG aggregates results from 70+ engines (Google, Bing, DuckDuckGo, Wikipedia, etc.)
    and returns structured JSON.
    """
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{base_url}/search",
                params={"q": query, "format": "json", "categories": "general"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        _log.warning("search_backend_empty", source="search_searxng", exc_info=False)
        return []

    results = []
    for item in data.get("results", [])[:max_results]:
        results.append(
            SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content", "")[:500],
                source="searxng",
                published_date=item.get("publishedDate"),
            )
        )
    return results


# ============================================================
# Semantic Scholar Backend
# ============================================================


async def search_semantic_scholar(query: str, max_results: int = 10) -> list[SearchResult]:
    """Search academic papers via Semantic Scholar API (free, no key required).

    Returns paper titles, abstracts, TLDR summaries, and URLs.
    """
    data = await _api_get(
        "https://api.semanticscholar.org/graph/v1/paper/search",
        params={"query": query, "limit": max_results, "fields": "title,url,year,abstract,tldr"},
    )
    if not data:
        return []

    results = []
    for paper in data.get("data", []):
        if not paper:
            continue
        tldr = paper.get("tldr", {})
        snippet = (tldr.get("text") or paper.get("abstract") or "")[:500]
        results.append(
            SearchResult(
                title=paper.get("title", ""),
                url=paper.get("url", f"https://api.semanticscholar.org/paper/{paper.get('paperId', '')}"),
                snippet=snippet,
                source="scholar",
                published_date=str(paper.get("year", "")),
            )
        )
    return results


# ============================================================
# Exa API Backend
# ============================================================


async def search_exa(query: str, api_key: str, max_results: int = 10) -> list[SearchResult]:
    """Search via Exa API — semantic web search with content extraction.

    Requires API key from https://exa.ai. Free tier: 1000 queries/month.
    """
    if not api_key:
        return []
    data = await _api_post(
        "https://api.exa.ai/search",
        json_data={"query": query, "numResults": max_results, "useAutoprompt": True},
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
    )
    if not data:
        return []

    results = []
    for item in data.get("results", []):
        snippet = item.get("text", "")[:500] if item.get("text") else ""
        published = item.get("publishedDate", "")
        results.append(
            SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=snippet,
                source="exa",
                published_date=published[:10] if published else "",
            )
        )
    return results


# ============================================================
# arXiv Backend
# ============================================================


async def search_arxiv(query: str, max_results: int = 10) -> list[SearchResult]:
    """Search preprints via arXiv API (free, no key required).

    Returns paper titles, abstracts, authors, and arXiv URLs.
    """
    import urllib.parse

    try:
        encoded = urllib.parse.quote(query)
        url = f"https://export.arxiv.org/api/query?search_query=all:{encoded}&start=0&max_results={max_results}&sortBy=relevance&sortOrder=descending"
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            raw = resp.text
    except Exception:
        _log.warning("search_backend_empty", source="search_searxng", exc_info=False)
        return []

    results = []
    try:
        import xml.etree.ElementTree as ET

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(raw)
        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            summary_el = entry.find("atom:summary", ns)
            link_el = entry.find("atom:id", ns)
            if link_el is None:
                link_el = entry.find("atom:link", ns)
            published_el = entry.find("atom:published", ns)
            authors: list[str] = [
                t
                for a in entry.findall("atom:author", ns)
                if (el := a.find("atom:name", ns)) is not None and (t := el.text or "") is not None
            ]

            title = title_el.text.strip() if title_el is not None and title_el.text else ""
            snippet = summary_el.text.strip()[:500] if summary_el is not None and summary_el.text else ""
            url = link_el.text.strip() if link_el is not None and link_el.text else ""
            published = published_el.text[:10] if published_el is not None and published_el.text else ""

            if title:
                results.append(
                    SearchResult(
                        title=title,
                        url=url,
                        snippet=f"{', '.join(authors[:3])}. {snippet}" if authors else snippet,
                        source="arxiv",
                        published_date=published,
                    )
                )
    except Exception:
        pass
    return results


# ============================================================
# 秘塔AI搜索 Backend
# ============================================================


async def search_metaso(query: str, api_key: str | None = None, max_results: int = 10) -> list[SearchResult]:
    """Search via 秘塔AI搜索 (Metaso) — Chinese-optimized AI search.

    Requires API key from https://metaso.cn/search-api/api-keys
    Credits: ~3 per search, free 5000 on signup.
    """
    if not api_key:
        api_key = __import__("os").environ.get("METASO_API_KEY", "")
    if not api_key:
        return []

    data = await _api_post(
        "https://metaso.cn/api/v1/search",
        json_data={
            "q": query,
            "scope": "webpage",
            "size": str(max_results),
            "includeSummary": False,
            "includeRawContent": False,
            "conciseSnippet": False,
        },
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    if not data:
        return []

    results = []
    for item in data.get("webpages", []):
        results.append(
            SearchResult(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", "")[:500],
                source="metaso",
                published_date=item.get("date", ""),
            )
        )
    return results


# ============================================================
# Brave Search Backend
# ============================================================


async def search_brave(query: str, api_key: str, max_results: int = 10) -> list[SearchResult]:
    """Search via Brave Search API — independent index of 35B pages.

    Free tier: 2000 queries/month. https://brave.com/search/api/
    """
    if not api_key:
        return []
    data = await _api_get(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": query, "count": min(max_results, 20)},
        headers={
            "X-Subscription-Token": api_key,
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
        },
    )
    if not data:
        return []

    results = []
    web = data.get("web", {})
    for item in web.get("results", []):
        results.append(
            SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("description", "")[:500],
                source="brave",
                published_date=item.get("age", ""),
            )
        )
    return results


# ============================================================
# DuckDuckGo Backend
# ============================================================


async def search_duckduckgo(query: str, max_results: int = 10) -> list[SearchResult]:
    """Search web via DuckDuckGo (free, no API key required).

    Uses duckduckgo-search library as SearXNG alternative when Docker unavailable.
    """
    try:
        from ddgs import DDGS

        loop = __import__("asyncio").get_event_loop()
        results_raw = await loop.run_in_executor(None, lambda: list(DDGS().text(query, max_results=max_results)))
    except Exception:
        _log.warning("search_backend_empty", source="ddg", exc_info=False)
        return []

    results = []
    for item in results_raw:
        results.append(
            SearchResult(
                title=item.get("title", ""),
                url=item.get("href", ""),
                snippet=item.get("body", "")[:500],
                source="ddg",
            )
        )
    return results


# ============================================================
# Jina Reader — Content Extraction
# ============================================================


async def extract_jina(url: str, api_key: str | None = None) -> str:
    """Extract clean markdown content from URL using Jina Reader API.

    Free tier: 10M tokens/month without API key.
    With API key: 500-5000 RPM.
    """
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"https://r.jina.ai/{url}",
                headers=headers,
            )
            resp.raise_for_status()
            content = resp.text
            if len(content) > 200:
                return content
    except Exception:
        pass

    return ""


# ============================================================
# BS4 + readability — Content Extraction Fallback
# ============================================================


async def extract_bs4(url: str) -> str:
    """Extract main content from URL using BeautifulSoup + readability-lxml.

    Fallback when Jina Reader is unavailable or rate-limited.
    """
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Minerva/0.1 Research Bot"})
            resp.raise_for_status()
            html = resp.text
    except Exception:
        return ""

    try:
        from readability import Document

        doc = Document(html)
        content_html = doc.summary()
        soup = BeautifulSoup(content_html, "html.parser")
        # Remove scripts and styles
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return text[:10000] if len(text) > 200 else ""
    except ImportError:
        # Fallback: basic BeautifulSoup extraction
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return text[:10000] if len(text) > 200 else ""
