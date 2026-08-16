# ---
# domain: workflows
# layer: tool
# status: active
# ---
"""Web search — multi-provider with graceful degradation (DDG + Wikipedia fallback)."""

from __future__ import annotations

import importlib.util
import logging

_log = logging.getLogger(__name__)

_HAS_AIOHTTP = importlib.util.find_spec("aiohttp") is not None


def _search_stdlib(query: str, max_results: int = 5) -> list[dict]:
    """Search using urllib (stdlib, no extra deps). Tries Wikipedia API."""
    import json as _json
    import ssl
    import urllib.parse
    import urllib.request

    api_url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": str(max_results),
        }
    )
    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(api_url, headers={"User-Agent": "SharedBrain/1.0"})
        resp = urllib.request.urlopen(req, timeout=10, context=ctx)  # noqa: S310
        if resp.status != 200:
            return []
        data = _json.loads(resp.read().decode())
        results = []
        for sr in data.get("query", {}).get("search", []):
            title = sr.get("title", "")
            results.append(
                {
                    "title": title,
                    "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
                    "snippet": sr.get("snippet", "")[:300],
                    "source": "wikipedia",
                }
            )
            if len(results) >= max_results:
                break
        return results
    except (OSError, ValueError, _json.JSONDecodeError, TimeoutError) as exc:
        _log.debug("stdlib search failed (network unreachable?): %s", exc)
        return []


async def _async_search_ddg(query: str, max_results: int = 5) -> list[dict]:
    """Search via DuckDuckGo HTML (no API key needed, may be geo-blocked)."""
    if not _HAS_AIOHTTP:
        return []
    import re

    import aiohttp

    url = "https://html.duckduckgo.com/html/"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                data={"q": query},
                headers={"User-Agent": "SharedBrain/1.0"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text()
                results = []
                for m in re.finditer(
                    r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>.*?<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
                    html,
                    re.DOTALL,
                ):
                    url_match = m.group(1)
                    title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                    snippet = re.sub(r"<[^>]+>", "", m.group(3)).strip()
                    if url_match and title:
                        results.append(
                            {
                                "title": title,
                                "url": url_match,
                                "snippet": snippet[:300],
                                "source": "web",
                            }
                        )
                    if len(results) >= max_results:
                        break
                if results:
                    return results
    except (aiohttp.ClientError, OSError, ValueError, RuntimeError, TimeoutError) as exc:
        _log.debug("DDG search failed (may be geo-blocked): %s", exc)
    return []


async def _async_search_wikipedia(query: str, max_results: int = 5) -> list[dict]:
    """Search via Wikipedia API using aiohttp."""
    if not _HAS_AIOHTTP:
        return []
    import json as _json
    import urllib.parse

    import aiohttp

    api_url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": str(max_results),
        }
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                api_url,
                headers={"User-Agent": "SharedBrain/1.0"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                results = []
                for sr in data.get("query", {}).get("search", []):
                    results.append(
                        {
                            "title": sr.get("title", ""),
                            "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(sr.get('title', '').replace(' ', '_'))}",
                            "snippet": sr.get("snippet", "")[:300],
                            "source": "wikipedia",
                        }
                    )
                return results
    except (aiohttp.ClientError, OSError, ValueError, RuntimeError, TimeoutError, _json.JSONDecodeError) as exc:
        _log.debug("Wikipedia aiohttp search failed: %s", exc)
        return []


async def _async_search(query: str, max_results: int = 5) -> list[dict]:
    """Multi-provider search: DDG → Wikipedia (aiohttp) → Wikipedia (stdlib)."""
    if _HAS_AIOHTTP:
        results = await _async_search_ddg(query, max_results)
        if results:
            return results
        results = await _async_search_wikipedia(query, max_results)
        if results:
            return results

    # Stdlib fallback — works without aiohttp
    return _search_stdlib(query, max_results)


def web_search(query: str, max_results: int = 5) -> list[dict]:
    import asyncio

    try:
        return asyncio.run(_async_search(query, max_results))
    except (OSError, RuntimeError, ValueError, TimeoutError) as exc:
        _log.warning("web_search failed: %s", exc)
        return []
