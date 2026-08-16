"""Tech Radar 数据抓取 — ArXiv / GitHub Trending / HuggingFace。"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class TechItem:
    """单条技术情报条目。"""

    title: str
    description: str
    url: str
    source: str  # "arxiv" | "github" | "huggingface"
    tags: list[str] = field(default_factory=list)
    published_at: str = ""
    relevance_score: float = 0.0
    upgrade_candidate: bool = False


# ── ArXiv ─────────────────────────────────────────────────────────────────

_ARXIV_NS = "http://www.w3.org/2005/Atom"
_ARXIV_CATEGORIES = "cat:cs.AI+OR+cat:cs.IR+OR+cat:cs.MA+OR+cat:cs.LG"
_ARXIV_URL = (
    "https://export.arxiv.org/api/query"
    f"?search_query={_ARXIV_CATEGORIES}"
    "&sortBy=submittedDate&sortOrder=descending&max_results=30"
)


async def fetch_arxiv(client: Any) -> list[TechItem]:
    """从 ArXiv 拉取最新 cs.AI/cs.IR/cs.MA/cs.LG 论文。"""
    try:
        resp = await client.get(_ARXIV_URL, timeout=20)
        resp.raise_for_status()
    except Exception as exc:
        return [TechItem(title="ArXiv fetch failed", description=str(exc), url="", source="arxiv")]

    root = ET.fromstring(resp.text)
    items: list[TechItem] = []

    for entry in root.findall(f"{{{_ARXIV_NS}}}entry"):
        title_el = entry.find(f"{{{_ARXIV_NS}}}title")
        summary_el = entry.find(f"{{{_ARXIV_NS}}}summary")
        id_el = entry.find(f"{{{_ARXIV_NS}}}id")
        published_el = entry.find(f"{{{_ARXIV_NS}}}published")

        title = (title_el.text or "").strip().replace("\n", " ") if title_el is not None else ""
        description = (summary_el.text or "").strip().replace("\n", " ")[:500] if summary_el is not None else ""
        url = (id_el.text or "").strip() if id_el is not None else ""
        published = (published_el.text or "")[:10] if published_el is not None else ""

        cats = [c.get("term", "") for c in entry.findall(f"{{{_ARXIV_NS}}}category")]

        if title:
            items.append(
                TechItem(
                    title=title,
                    description=description,
                    url=url,
                    source="arxiv",
                    tags=cats,
                    published_at=published,
                )
            )

    return items


# ── GitHub Trending ────────────────────────────────────────────────────────

_GITHUB_TRENDING_URLS = [
    "https://github.com/trending/python?since=weekly",
    "https://github.com/trending/typescript?since=weekly",
]


def _parse_github_trending(html: str, language: str) -> list[TechItem]:
    items: list[TechItem] = []
    # 每个 repo 都在 <article class="Box-row"> 里
    articles = re.split(r'<article\s[^>]*class="[^"]*Box-row[^"]*"', html)[1:]
    for block in articles[:20]:
        # 提取 href="/owner/repo"
        repo_match = re.search(r'href="/([^"/]+/[^"/]+)"[^>]*>\s*\n', block)
        if not repo_match:
            repo_match = re.search(r'href="/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)"', block)
        if not repo_match:
            continue
        repo_path = repo_match.group(1)

        # 提取 description (<p class="col-9 ...")
        desc_match = re.search(r'<p\s[^>]*class="col-9[^"]*"[^>]*>\s*(.*?)\s*</p>', block, re.DOTALL)
        description = re.sub(r"<[^>]+>", "", desc_match.group(1)).strip() if desc_match else ""

        items.append(
            TechItem(
                title=repo_path,
                description=description[:300],
                url=f"https://github.com/{repo_path}",
                source="github",
                tags=[language],
                published_at=datetime.now(UTC).strftime("%Y-%m-%d"),
            )
        )
    return items


async def fetch_github_trending(client: Any) -> list[TechItem]:
    """从 GitHub Trending 拉取 Python/TypeScript 本周热门仓库。"""
    items: list[TechItem] = []
    for url in _GITHUB_TRENDING_URLS:
        lang = "python" if "python" in url else "typescript"
        try:
            resp = await client.get(url, timeout=20, follow_redirects=True)
            resp.raise_for_status()
            items.extend(_parse_github_trending(resp.text, lang))
        except Exception as exc:
            items.append(
                TechItem(
                    title=f"GitHub Trending {lang} fetch failed",
                    description=str(exc),
                    url=url,
                    source="github",
                )
            )
    return items


# ── HuggingFace ────────────────────────────────────────────────────────────

_HF_API_URL = "https://huggingface.co/api/models?sort=trending&limit=20&full=false"


async def fetch_huggingface(client: Any) -> list[TechItem]:
    """从 HuggingFace 拉取 trending 模型/工具。"""
    try:
        resp = await client.get(_HF_API_URL, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        return [TechItem(title="HuggingFace fetch failed", description=str(exc), url="", source="huggingface")]

    items: list[TechItem] = []
    for model in data:
        model_id = model.get("id", "")
        tags = model.get("tags", []) or []
        pipeline_tag = model.get("pipeline_tag", "")
        likes = model.get("likes", 0)
        downloads = model.get("downloads", 0)

        items.append(
            TechItem(
                title=model_id,
                description=f"pipeline={pipeline_tag} likes={likes} downloads={downloads}",
                url=f"https://huggingface.co/{model_id}",
                source="huggingface",
                tags=[pipeline_tag] + tags[:5],
                published_at=model.get("lastModified", "")[:10],
            )
        )
    return items


# ── 入口 ──────────────────────────────────────────────────────────────────


async def fetch_all(sources: list[str] | None = None) -> list[TechItem]:
    """并发抓取所有数据源，返回合并结果。"""
    import asyncio

    import httpx

    sources = sources or ["arxiv", "github", "huggingface"]
    headers = {"User-Agent": "omostation-tech-radar/1.0 (research bot)"}

    async with httpx.AsyncClient(headers=headers) as client:
        tasks = []
        if "arxiv" in sources:
            tasks.append(fetch_arxiv(client))
        if "github" in sources:
            tasks.append(fetch_github_trending(client))
        if "huggingface" in sources:
            tasks.append(fetch_huggingface(client))

        results = await asyncio.gather(*tasks, return_exceptions=True)

    items: list[TechItem] = []
    for r in results:
        if isinstance(r, list):
            items.extend(r)
    return items
