# ---
# domain: workflows
# layer: tool
# status: active
# ---
"""Web page scraping via aiohttp with sync wrapper."""

from __future__ import annotations

import importlib.util
import logging
from datetime import UTC, datetime

_log = logging.getLogger(__name__)
_USER_AGENT = "SharedBrain/1.0 Research Assistant"

_HAS_AIOHTTP = importlib.util.find_spec("aiohttp") is not None


async def _async_scrape(url: str, timeout: int = 15) -> dict | None:
    if not _HAS_AIOHTTP:
        return None
    import aiohttp

    try:
        headers = {"User-Agent": _USER_AGENT}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    return {
                        "url": url,
                        "title": url,
                        "text_content": text[:5000],
                        "extracted_at": datetime.now(UTC).isoformat(),
                    }
    except (aiohttp.ClientError, OSError, ValueError, RuntimeError, TimeoutError) as exc:
        _log.debug("async scrape failed for %s: %s", url, exc)
    return None


def scrape_url(url: str, timeout: int = 15) -> dict | None:
    import asyncio

    try:
        return asyncio.run(_async_scrape(url, timeout))
    except (OSError, RuntimeError, ValueError, TimeoutError) as exc:
        _log.warning("scrape_url failed for %s: %s", url, exc)
        return None
