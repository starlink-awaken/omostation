"""Pipeline stage implementations — MultiSourceSearch stage."""

from __future__ import annotations

import asyncio
from typing import Any

from minerva.pipeline.engine import IPipelineStage, ResearchContext


class MultiSourceSearchStageImpl(IPipelineStage):
    """Parallel search across multiple backends."""

    name = "search"

    def __init__(self, search_engine: Any, backends: list[str], max_results: int = 25) -> None:
        self.search_engine = search_engine
        self.backends = backends
        self.max_results = max_results

    async def execute(self, ctx: ResearchContext) -> ResearchContext:
        queries = ctx.sub_questions if ctx.sub_questions else [ctx.query]
        # Parallel search across primary + all sub-questions
        tasks = [
            self.search_engine.search(q, backends=self.backends, max_results=self.max_results if i == 0 else 5)
            for i, q in enumerate(queries)
        ]
        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        results: list = []
        for r in gathered:
            if isinstance(r, list):
                results.extend(r)
            elif isinstance(r, Exception):
                pass  # Individual query failures are non-fatal

        # Deduplicate
        seen: set = set()
        deduped = []
        for r in results:
            if r.url not in seen:
                seen.add(r.url)
                deduped.append(r)
        ctx.search_results = [
            {
                "title": r.title,
                "url": r.url,
                "snippet": r.snippet,
                "source": r.source,
                "published_date": r.published_date,
                "rank_score": r.rank_score,
            }
            for r in deduped[: self.max_results]
        ]
        return ctx
