"""卫生政策数据抓取 — 国家卫健委/医保局/药监局。

数据源（全部公开）：
  - 国家卫健委: http://www.nhc.gov.cn/wjw/xwfb/list.shtml
  - 国家医保局: https://www.nhsa.gov.cn/col/col104/index.html
  - 国家药监局: https://www.nmpa.gov.cn/xxgk/fgwj/index.html

网络不可达时自动 fallback 到 ``seeds.py`` 的种子数据，避免单元测试
和受限网络环境失败。
"""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from minerva.policy_tracker.seeds import SEED_POLICIES
from minerva.policy_tracker.types import PolicyItem

__all__ = ["PolicyItem", "fetch_recent", "fetch_nhc", "fetch_nhsa"]

# ── 数据源定义 ────────────────────────────────────────────────────────────

# 卫健委新闻发布
NHC_NEWS_URL = "http://www.nhc.gov.cn/wjw/xwfb/list.shtml"
# 医保局政策法规
NHSA_POLICY_URL = "https://www.nhsa.gov.cn/col/col104/index.html"
# 药监局公告（备用）
NMPA_NOTICE_URL = "https://www.nmpa.gov.cn/xxgk/fgwj/index.html"

UA_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


# ── HTML 解析工具 ──────────────────────────────────────────────────────────


def _strip_html(text: str) -> str:
    """去除 HTML 标签 + 折叠空白。"""
    if not text:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text)).strip()


def _parse_nhc_html(html: str) -> list[PolicyItem]:
    """解析卫健委新闻列表 HTML。

    卫健委页面典型结构：
        <li><a href="...">标题</a><span>YYYY-MM-DD</span></li>
    """
    items: list[PolicyItem] = []
    # 抓取 <a href>...title...</a> + 后面紧跟的日期
    pattern = re.compile(
        r'<a[^>]+href="([^"]+)"[^>]*>([^<]{6,200})</a>.*?(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
        re.DOTALL,
    )
    for m in pattern.finditer(html):
        url, title, date = m.group(1), m.group(2).strip(), m.group(3).replace("/", "-")
        if not title or "javascript" in url:
            continue
        if not url.startswith("http"):
            url = "http://www.nhc.gov.cn" + url if url.startswith("/") else url
        items.append(
            PolicyItem(
                title=title[:200],
                issuing_agency="国家卫健委",
                doc_number="",
                published_at=date,
                summary=title[:200],
                url=url,
                tags=["#health-policy", "#source:nhc"],
            )
        )
    return items[:20]


def _parse_nhsa_html(html: str) -> list[PolicyItem]:
    """解析医保局政策法规列表 HTML。

    医保局页面典型结构：
        <li><a href="..." target="_blank">标题</a><span>YYYY-MM-DD</span></li>
    """
    items: list[PolicyItem] = []
    pattern = re.compile(
        r'<a[^>]+href="([^"]+)"[^>]*>([^<]{6,200})</a>.*?(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
        re.DOTALL,
    )
    for m in pattern.finditer(html):
        url, title, date = m.group(1), m.group(2).strip(), m.group(3).replace("/", "-")
        if not title or "javascript" in url:
            continue
        if url.startswith("/"):
            url = "https://www.nhsa.gov.cn" + url
        elif not url.startswith("http"):
            continue
        items.append(
            PolicyItem(
                title=title[:200],
                issuing_agency="国家医保局",
                doc_number="",
                published_at=date,
                summary=title[:200],
                url=url,
                tags=["#health-policy", "#source:nhsa"],
            )
        )
    return items[:20]


# ── 单源抓取 ──────────────────────────────────────────────────────────────


async def fetch_nhc(client: Any, days: int = 7) -> list[PolicyItem]:
    """抓取国家卫健委新闻发布（最近 N 天）。"""
    try:
        resp = await client.get(NHC_NEWS_URL, timeout=15)
        resp.raise_for_status()
        html = resp.text
    except Exception as exc:
        print(f"[policy-tracker] NHC fetch failed: {exc}")
        return []

    items = _parse_nhc_html(html)
    cutoff = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")
    return [i for i in items if i.published_at >= cutoff]


async def fetch_nhsa(client: Any, days: int = 7) -> list[PolicyItem]:
    """抓取国家医保局政策法规（最近 N 天）。"""
    try:
        resp = await client.get(NHSA_POLICY_URL, timeout=15)
        resp.raise_for_status()
        html = resp.text
    except Exception as exc:
        print(f"[policy-tracker] NHSA fetch failed: {exc}")
        return []

    items = _parse_nhsa_html(html)
    cutoff = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")
    return [i for i in items if i.published_at >= cutoff]


# ── 主入口 ────────────────────────────────────────────────────────────────


async def fetch_recent(days: int = 7, sources: list[str] | None = None) -> tuple[list[PolicyItem], dict[str, str]]:
    """并发抓取所有数据源，网络失败时 fallback 到种子。

    Returns:
        (items, source_status) — items 为去重后的政策列表；
        source_status 记录每个源的可用性: "ok" | "failed" | "seed"
    """
    sources = sources or ["nhc", "nhsa"]
    items: list[PolicyItem] = []
    status: dict[str, str] = {}

    try:
        import httpx
    except ImportError:
        print("[policy-tracker] httpx not available, using seeds")
        for src in sources:
            status[src] = "seed"
        return _filter_seeds_by_days(days), status

    async with httpx.AsyncClient(headers=UA_HEADERS, follow_redirects=True) as client:
        tasks = []
        if "nhc" in sources:
            tasks.append(("nhc", fetch_nhc(client, days)))
        if "nhsa" in sources:
            tasks.append(("nhsa", fetch_nhsa(client, days)))

        for src, coro in tasks:
            try:
                result = await coro
                if result:
                    items.extend(result)
                    status[src] = "ok"
                else:
                    status[src] = "failed"
            except Exception as exc:
                print(f"[policy-tracker] {src} error: {exc}")
                status[src] = "failed"

    # 网络失败 / 全部失败 → fallback 到种子
    if not items:
        print("[policy-tracker] 全部数据源抓取失败，fallback 到种子数据")
        for src in sources:
            status[src] = "seed"
        return _filter_seeds_by_days(days), status

    # 合并种子数据作为基线（种子已经覆盖场景 A 关键词），保证 E2E-DEMO 有稳定供数
    seed_items = _filter_seeds_by_days(days)

    # 去重（优先保留真实抓取，种子只补空缺）
    seen: set[str] = set()
    unique: list[PolicyItem] = []
    for item in items:
        if item.url and item.url in seen:
            continue
        seen.add(item.url)
        unique.append(item)
    for seed in seed_items:
        if not seed.url or seed.url not in seen:
            unique.append(seed)
            if seed.url:
                seen.add(seed.url)

    # 标记 seed 来源条目
    for item in unique:
        if item in seed_items and "#source:seed" not in item.tags:
            item.tags.append("#source:seed")

    return unique, status


def _filter_seeds_by_days(days: int) -> list[PolicyItem]:
    """从 SEED_POLICIES 选出 published_at 在最近 N 天内的条目。"""
    cutoff = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")
    return [s for s in SEED_POLICIES if s.published_at >= cutoff]


# 同步包装（CLI 友好）
def fetch_recent_sync(days: int = 7, sources: list[str] | None = None) -> tuple[list[PolicyItem], dict[str, str]]:
    return asyncio.run(fetch_recent(days=days, sources=sources))
