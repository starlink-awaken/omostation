"""Kronos Fetch Router v2 — 综合抓取工具集.

5 层抓取方案,按速度+成功率优先级编排:

L1: MCP 直接抓取 — metaso/webFetch/GitHub/CSDN 等专用工具(最快)
L2: Jina AI Reader Proxy — r.jina.ai/<URL> 转 Markdown(绕过大部分限制)
L3: 缓存查找 — web-search-prime 找转载/缓存版本
L4: CloakBrowser — 58 处反爬补丁的 Chromium 浏览器自动化(绕过所有反爬)
L5: 归档快照 — 用户手动粘贴兜底

设计原则:编排不实现.Kronos 自己不写抓取代码,只串联已有工具.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict, cast

if TYPE_CHECKING:
    from kronos.extractor import ErrorResult, ExtractedResult

logger = logging.getLogger(__name__)


class FetchResult(TypedDict, total=False):
    """抓取结果"""

    ok: bool
    content: NotRequired[str]
    text: NotRequired[str]
    markdown: NotRequired[str]
    method: NotRequired[str]
    title: NotRequired[str]
    error: NotRequired[str]
    plan: NotRequired[list[dict]]
    _content_hash: str  # batch_fetch 内容指纹
    saved_to: str  # batch_fetch 保存路径


from kronos.fetcher.classify import ContentType, FetchLayer, FetchPlan, MCPTool  # type: ignore[import-not-found]
from kronos.fetcher.errors import (  # type: ignore[import-not-found]
    execute_fetch,
)


def _is_error_page(content: str) -> bool:
    from kronos.fetcher.errors import _is_error_page as _impl

    result: bool = _impl(content)
    return result


def diagnose_fetch_error(error: Exception) -> dict[str, str]:
    from kronos.fetcher.errors import diagnose_fetch_error as _impl

    result: dict[str, str] = _impl(error)
    return result


def extract_image_urls(html: str) -> list[str]:
    from kronos.fetcher.errors import extract_image_urls as _impl

    result: list[str] = _impl(html)
    return result


def is_image_url(url: str) -> bool:
    from kronos.fetcher.errors import is_image_url as _impl

    result: bool = _impl(url)
    return result


MCP_TOOLS: list[MCPTool] = [
    MCPTool(
        "mcp__metaso__metaso_web_reader",
        "Metaso 网页阅读器,支持公众号/知乎/通用",
        ["mp.weixin.qq.com", "zhuanlan.zhihu.com", "zhihu.com"],
    ),
    MCPTool("mcp__open-websearch__fetchWebContent", "通用网页抓取,支持 readability 模式", ["*"]),
    MCPTool("mcp__workspace__web_fetch", "Workspace 自带网页抓取", ["*"]),
    MCPTool("mcp__open-websearch__fetchGithubReadme", "GitHub README 专用抓取", ["github.com"]),
    MCPTool("mcp__open-websearch__fetchCsdnArticle", "CSDN 文章专用抓取", ["csdn.net"]),
    MCPTool("mcp__open-websearch__fetchJuejinArticle", "掘金文章专用抓取", ["juejin.cn"]),
    MCPTool("mcp__open-websearch__fetchLinuxDoArticle", "LinuxDo 帖子专用抓取", ["linux.do"]),
    MCPTool("mcp__MCP_DOCKER__convert_to_markdown", "任意 URI 转 Markdown(含 arXiv PDF)", ["arxiv.org"]),
    MCPTool("mcp__MCP_DOCKER__fetch_content", "Docker 容器网页内容提取", ["*"]),
    MCPTool("mcp__web-search-prime__web_search_prime", "AI 搜索引擎,可查找缓存内容", ["*"]),
    MCPTool("mcp__MCP_DOCKER__fetch", "Docker 容器通用抓取", ["*"]),
]


# ═══════════════════════════════════════════════════
# L2: Jina AI Reader Proxy
# ═══════════════════════════════════════════════════

JINA_READER_URL = "https://r.jina.ai/"


def build_jina_plan(url: str) -> FetchPlan:
    """通过 Jina AI Reader 代理抓取"""
    return FetchPlan(
        url=url,
        content_type=_classify(url),
        layer=FetchLayer.L2_JINA_PROXY,
        method_name="jina_reader",
        method_desc="Jina AI Reader Proxy — 在 URL 前加 r.jina.ai/ 前缀,返回干净 Markdown",
        call_params={
            "proxy_url": f"{JINA_READER_URL}{url}",
            "note": "浏览器直接打开 r.jina.ai/<URL> 即可获取 Markdown 版本",
        },
        estimated_cost="free (rate limited)",
    )


# ═══════════════════════════════════════════════════
# L0: 原生 HTTP 抓取(不依赖任何外部工具)
# ═══════════════════════════════════════════════════

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
    import re

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


def _extract_title(html: str) -> str:
    """从 HTML 中粗略提取标题"""
    import re

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


# ═══════════════════════════════════════════════════
# URL 分类
# ═══════════════════════════════════════════════════

URL_RULES: list[tuple[str, ContentType]] = [
    (r"arxiv\.org|\.pdf$", ContentType.PAPER),
    (r"mp\.weixin\.qq\.com", ContentType.WEIXIN),
    (r"zhuanlan\.zhihu\.com|zhihu\.com", ContentType.ARTICLE),
    (r"github\.com", ContentType.GITHUB),
    (r"csdn\.net", ContentType.CODE),
    (r"juejin\.cn", ContentType.CODE),
    (r"linux\.do", ContentType.FORUM),
    (r"gov\.cn|gov\.com", ContentType.POLICY),
    (r"(twitter|x)\.com", ContentType.SOCIAL),
    (r"youtube\.com|bilibili\.com", ContentType.VIDEO),
]


def _classify(url: str) -> ContentType:
    for pattern, ctype in URL_RULES:
        if re.search(pattern, url.lower()):
            return ctype
    return ContentType.UNKNOWN


def _pick_mcp_tool(ctype: ContentType, url: str) -> FetchPlan | None:
    """L1: 选最佳 MCP 工具"""
    for tool in MCP_TOOLS:
        if tool.name == "mcp__metaso__metaso_web_reader":
            if ctype in (ContentType.WEIXIN, ContentType.ARTICLE):
                return FetchPlan(
                    url=url,
                    content_type=ctype,
                    layer=FetchLayer.L1_MCP_DIRECT,
                    method_name=tool.name,
                    method_desc=tool.description,
                    call_params={"tool": tool.name, "url": url, "format": "markdown"},
                )
        elif tool.name == "mcp__open-websearch__fetchWebContent":
            # 通用兜底
            return FetchPlan(
                url=url,
                content_type=ctype,
                layer=FetchLayer.L1_MCP_DIRECT,
                method_name=tool.name,
                method_desc=tool.description,
                call_params={"tool": tool.name, "url": url, "readability": True, "maxChars": 50000},
            )
    return None


# ═══════════════════════════════════════════════════
# 主入口: 完整 fallback 链
# ═══════════════════════════════════════════════════


def plan_for_url(url: str) -> FetchPlan:
    """生成完整 fallback 链,返回最高优先级的方案"""
    ctype = _classify(url)

    # L0: 原生 HTTP 直连(最快,不依赖外部工具)
    native_plan = FetchPlan(
        url=url,
        content_type=ctype,
        layer=FetchLayer.L0_NATIVE,
        method_name="native_http",
        method_desc="原生 HTTP GET(httpx),最快速尝试",
        call_params={"url": url, "timeout": 15},
        estimated_cost="free",
    )

    # L1: 看有没有专用 MCP 工具
    mcp_plan = _pick_mcp_tool(ctype, url)
    if mcp_plan:
        native_plan.fallback_plan = mcp_plan
        mcp_plan.fallback_plan = build_jina_plan(url)
        mcp_plan.fallback_plan.fallback_plan = build_cache_plan(url)
        mcp_plan.fallback_plan.fallback_plan.fallback_plan = build_cloakbrowser_plan(url)
        return native_plan

    # 没有专用 MCP 工具 → L0 → L2 → ...
    native_plan.fallback_plan = build_jina_plan(url)
    native_plan.fallback_plan.fallback_plan = build_cache_plan(url)
    native_plan.fallback_plan.fallback_plan.fallback_plan = build_cloakbrowser_plan(url)
    return native_plan


def execute_fallback_chain(url: str) -> list[dict]:
    """生成完整的 fallback 链方案列表(供 CLI/MCP 输出)"""
    results = []
    plan: FetchPlan | None = plan_for_url(url)
    depth = 1
    while plan:
        results.append(
            {
                "priority": depth,
                "layer": plan.layer.value,
                "layer_name": f"L{plan.layer.value}_{plan.method_name}",
                "method": plan.method_name,
                "description": plan.method_desc,
                "params": plan.call_params,
                "estimated_cost": plan.estimated_cost,
            }
        )
        plan = plan.fallback_plan
        depth += 1
    return results


# ═══════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:8]


def content_type_label(ctype: ContentType) -> str:
    labels = {
        ContentType.ARTICLE: "文章",
        ContentType.PAPER: "论文",
        ContentType.SOCIAL: "社交动态",
        ContentType.POLICY: "政策文件",
        ContentType.RESOURCE: "资源",
        ContentType.VIDEO: "视频",
        ContentType.GITHUB: "GitHub仓库",
        ContentType.CODE: "技术文章",
        ContentType.FORUM: "论坛帖子",
        ContentType.WEIXIN: "公众号",
        ContentType.UNKNOWN: "未知",
    }
    return labels.get(ctype, "未知")


def list_all_methods() -> list[dict]:
    """列出全集抓取方法"""
    methods = []
    # L1
    for tool in MCP_TOOLS:
        methods.append({"layer": "L1_MCP", "name": tool.name, "description": tool.description})
    # L2
    methods.append(
        {
            "layer": "L2_JINA",
            "name": "jina_reader",
            "description": f"Jina AI Reader: {JINA_READER_URL}<URL>",
        }
    )
    # L3
    methods.append({"layer": "L3_CACHE", "name": "web_search_prime_cache", "description": "搜索引擎缓存查找"})
    # L4
    methods.append(
        {
            "layer": "L4_BROWSER",
            "name": "cloakbrowser",
            "description": "CloakBrowser 浏览器自动化(58 处反爬补丁)",
        }
    )
    return methods


# ═══════════════════════════════════════════════════
# Ollama 本地模型集成(提取阶段)


def check_ollama(timeout: float = 3.0) -> tuple[bool, str]:
    """委派到 extractor(保持向后兼容)"""
    from kronos.extractor import check_ollama as _co  # type: ignore[import-not-found]

    ok = _co(timeout)
    return ok, "Ollama 已连接" if ok else "Ollama 未连接"


def _detect_ollama_model() -> str:
    """委派到 extractor"""
    from kronos.extractor import _detect_ollama_model

    result: str = _detect_ollama_model()
    return result


def call_ollama(prompt: str, model: str | None = None, system_prompt: str | None = None) -> str:
    """委派到 extractor"""
    from kronos.extractor import call_ollama

    result: str = call_ollama(prompt, model, system_prompt)
    return result


def extract_with_ollama(text: str, model: str | None = None) -> ExtractedResult | ErrorResult:
    """委派到 extractor"""
    from kronos.extractor import extract_with_ollama as _impl

    return _impl(text, model)


def batch_fetch(urls: list[str], max_concurrent: int = 3, save_dir: str | None = None) -> list[dict]:
    """批量抓取多个 URL,带并发控制和去重.

    Args:
        urls: URL 列表
        max_concurrent: 最大并发数
        save_dir: 可选,保存目录

    Returns:
        [{"url": ..., "ok": bool, "method": ..., "title": ..., "error": ...}, ...]
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from hashlib import sha256

    seen_hashes: set[str] = set()
    results: list[dict] = []

    def _fetch_one(url: str) -> dict:
        # 去重
        url_hash = sha256(url.encode()).hexdigest()[:16]
        if url_hash in seen_hashes:
            return {"url": url, "ok": False, "error": "重复 URL"}
        seen_hashes.add(url_hash)

        result = execute_fetch(url)
        if result.get("ok"):
            # 内容去重(内容指纹)
            content = result.get("markdown", "") or result.get("text", "")
            content_hash = sha256(content.encode()).hexdigest()[:16]
            result["_content_hash"] = content_hash
            if save_dir and content:
                import os
                import re

                title = result.get("title", "article")[:40]
                safe = re.sub(r"[^\w\- ]", "", title).strip() or "article"
                fpath = os.path.join(save_dir, f"{safe}-{content_hash[:8]}.md")
                if not os.path.exists(fpath):
                    with open(fpath, "w") as f:
                        f.write(f"# {title}\n\n{content}\n")
                result["saved_to"] = fpath
        return {
            "url": url,
            "ok": result.get("ok", False),
            "method": result.get("method"),
            "title": result.get("title", ""),
            "error": result.get("error"),
            "saved_to": result.get("saved_to"),
        }

    with ThreadPoolExecutor(max_workers=max_concurrent) as pool:
        futures = [pool.submit(_fetch_one, u) for u in urls]
        for future in as_completed(futures):
            results.append(future.result())

    return results
