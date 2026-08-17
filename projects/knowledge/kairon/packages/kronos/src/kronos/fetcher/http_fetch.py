"""HTTP-level fetch functions."""

from __future__ import annotations

import logging
import re

from kronos.fetch_router import JINA_READER_URL, _classify
from kronos.fetcher.classify import FetchLayer, FetchPlan  # type: ignore[import-not-found]

logger = logging.getLogger(__name__)

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def _try_native_http(url: str, timeout: int = 15) -> str | None:
    """L0: 原生 HTTP GET 抓取"""
    try:
        import httpx

        resp = httpx.get(url, headers=HTTP_HEADERS, timeout=timeout, follow_redirects=True)
        if resp.status_code == 200 and len(resp.text) > 200:
            return resp.text
    except Exception as e:
        logger.warning("native_http failed for %s: %s", url, e)
    return None


def _try_scrapling_fetch(url: str, timeout: int = 15) -> str | None:
    """L0.5: Scrapling 智能抓取 — TLS 指纹伪装 + Selector 解析

    Scrapling 的 StealthyFetcher 使用 curl_cffi 模拟真实浏览器 TLS 指纹,
    可绕过 Cloudflare 轻度防护.比 CloakBrowser 快得多(不启动 Chromium).

    API 文档: https://github.com/D4Vinci/Scrapling
    """
    try:
        from scrapling.fetchers import StealthyFetcher  # type: ignore[import-not-found]

        f = StealthyFetcher()
        resp = f.get(url, timeout=timeout)  # type: ignore[attr-defined]
        if resp and resp.status == 200 and len(resp.text) > 200:
            text_val: str = resp.text
            return text_val
    except ImportError:
        pass  # scrapling 或 curl_cffi 未安装
    except Exception as e:
        logger.warning("scrapling_fetch failed for %s: %s", url, e)
    return None


def _try_jina_reader(url: str, timeout: int = 30) -> str | None:
    """L0b: Jina AI Reader — GET r.jina.ai/<URL>,返回干净 Markdown"""
    try:
        import httpx

        proxy_url = f"{JINA_READER_URL}{url}"
        resp = httpx.get(proxy_url, timeout=timeout, follow_redirects=True)
        if resp.status_code == 200 and len(resp.text) > 200:
            return resp.text
    except Exception as e:
        logger.warning("jina_reader failed for %s: %s", url, e)
    return None


def _strip_html(html: str) -> str:
    """HTML → 纯文本"""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = "".join(c for c in text if c.isprintable() or c in "\n\r\t")
    return text[:50000]


def _html_to_markdown(html: str) -> str:
    """HTML → Markdown(可选 html2text,否则用纯文本降级)"""
    try:
        import html2text  # type: ignore[import-not-found]

        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.body_width = 0
        result: str = h.handle(html)[:50000]
        return result
    except ImportError:
        return _strip_html(html)


# ═══════════════════════════════════════════════════
# L0c: DuckDuckGo 搜索 (替代 web-search-prime MCP)
# ═══════════════════════════════════════════════════


def _try_web_search(query: str, timeout: int = 10) -> list[dict]:
    """DuckDuckGo HTML 搜索(不需要 API Key)"""
    try:
        import httpx
        from scrapling.parser import Selector  # type: ignore[import-not-found]

        resp = httpx.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={**HTTP_HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
            timeout=timeout,
        )
        if resp.status_code != 200:
            return []
        results = []
        # 用 Scrapling Selector 解析(比 BeautifulSoup 快 5-10x)
        try:
            sel = Selector(resp.text)
            for r in sel.css(".result") or sel.css(".web-result"):
                link = r.css("a[href]").first
                title_el = r.css(".result__title, h2 a, .result-title").first
                if link and title_el:
                    href = link.attrib.get("href", "")
                    if href.startswith("//"):
                        href = "https:" + href
                    results.append({"title": title_el.extract_first() or "", "url": href})
        except Exception as e:
            logger.warning("web_search Selector parsing failed: %s", e)
            pass
        # BeautifulSoup 没结果时用正则兜底
        if not results:
            import re

            seen = set()
            pattern = r'<a[^>]*class="[^"]*result-title[^"]*"[^>]*href="([^"]*)"[^>]*>(.*?)</a>'
            for m in re.finditer(pattern, resp.text, re.DOTALL):
                url = m.group(1)
                if url not in seen:
                    seen.add(url)
                    results.append({"title": re.sub(r"<[^>]+>", "", m.group(2)).strip(), "url": url})
        return results[:10]
    except ImportError:
        return []
    except Exception as e:
        logger.warning("web_search failed: %s", e)
        return []


# ═══════════════════════════════════════════════════
# L4: CloakBrowser 浏览器自动化(直接 import)
# ═══════════════════════════════════════════════════


from kronos.fetcher.browser import _try_cloakbrowser, _try_playwright  # type: ignore[import-not-found]  # noqa


def _extract_title(html: str) -> str:
    """从 HTML 中粗略提取标题"""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL)
    if m:
        return m.group(1).strip()
    return ""


# ═══════════════════════════════════════════════════
# L3: Cache Lookup


def build_cache_plan(url: str) -> FetchPlan:
    """通过搜索引擎查找缓存/转载版本"""
    ctype = _classify(url)
    return FetchPlan(
        url=url,
        content_type=ctype,
        layer=FetchLayer.L3_CACHE,
        method_name="web_search_prime_cache",
        method_desc="搜索引擎缓存查找 — 搜 URL 找转载/缓存版本",
        call_params={
            "tool": "mcp__web-search-prime__web_search_prime",
            "search_query": url,
            "content_size": "high",
        },
        estimated_cost="free",
    )


# ═══════════════════════════════════════════════════
# L4: CloakBrowser (浏览器自动化)
# ═══════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════
# URL 分类
# ═══════════════════════════════════════════════════
