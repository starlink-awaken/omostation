"""Browser-level fetch functions (CloakBrowser, Playwright)."""

from __future__ import annotations

import logging
from typing import Any, cast

from ..fetch_router import FetchPlan, _classify
from .classify import FetchLayer

logger = logging.getLogger(__name__)


def _try_cloakbrowser(url: str, timeout: int = 60) -> str | None:
    """L4: CloakBrowser 浏览器渲染抓取

    API: from cloakbrowser import launch_async
    launch_async() → Playwright-compatible Browser → page.goto() → page.content()
    """
    try:
        import asyncio

        from cloakbrowser import launch_async  # type: ignore[import-not-found]

        async def _fetch() -> str | None:
            try:
                browser = await asyncio.wait_for(
                    launch_async(),
                    timeout=timeout,
                )
            except TimeoutError:
                return None
            try:
                page = await asyncio.wait_for(
                    browser.new_page(),
                    timeout=30,
                )
                await asyncio.wait_for(
                    page.goto(url, wait_until="networkidle"),
                    timeout=timeout,
                )
                raw_content: Any = await page.content()
                content: str = raw_content
                return content
            finally:
                await browser.close()

        result: str | None = cast(str | None, asyncio.run(_fetch()))
        return result
    except ImportError:
        pass
    except Exception as e:
        logger.warning("cloakbrowser failed for %s: %s", url, e)
    return None


def _try_playwright(url: str, timeout: int = 60) -> str | None:
    """L4b: Playwright 浏览器渲染抓取(CloakBrowser 降级)"""
    try:
        import asyncio

        from playwright.async_api import async_playwright  # type: ignore[import-not-found]

        async def _fetch() -> str | None:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                try:
                    page = await browser.new_page()
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                    raw_content: Any = await page.content()
                    content: str = raw_content
                    return content
                finally:
                    await browser.close()

        content = asyncio.run(_fetch())
        result: str | None = cast(str | None, content)
        return result
    except ImportError:
        pass  # Playwright 未安装
    except Exception as e:
        logger.warning("playwright failed for %s: %s", url, e)
    return None


# ── 异常处理表(对齐 WPS web-importer 规范) ──────────
CLOAKBROWSER_SCRIPT = """
import asyncio
import sys
from cloakbrowser import CloakBrowser

async def fetch(url):
    browser = await CloakBrowser.create(humanize=True)
    page = await browser.new_page()
    await page.goto(url, wait_until="networkidle")
    content = await page.content()
    title = await page.title()
    text = await page.evaluate("document.body.innerText")
    await browser.close()
    # 输出 JSON
    import json
    print(json.dumps({"title": title, "content": content, "text": text[:50000]}))

asyncio.run(fetch(sys.argv[1]))
"""


def build_cloakbrowser_plan(url: str) -> FetchPlan:
    """通过 CloakBrowser 浏览器自动化抓取"""
    return FetchPlan(
        url=url,
        content_type=_classify(url),
        layer=FetchLayer.L4_BROWSER,
        method_name="cloakbrowser",
        method_desc="CloakBrowser — 58 处反爬补丁的 Chromium,绕过 Cloudflare/reCAPTCHA 等",
        call_params={
            "script": "python3 -m cloakbrowser.fetch",
            "fallback_playwright": "如果 CloakBrowser 未安装,用 Playwright 替代",
            "install": "pip install cloakbrowser playwright",
        },
        estimated_cost="local (Ollama + Chromium)",
    )
