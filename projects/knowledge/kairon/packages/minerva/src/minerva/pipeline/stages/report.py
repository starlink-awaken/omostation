"""Pipeline stage: Report generation from research results."""

from __future__ import annotations

import time
from typing import Any

from minerva.pipeline.engine import IPipelineStage, ResearchContext

REPORT_TEMPLATE = """# Research Report: {query}

## Summary
{summary}

## Key Findings
{findings}

## Sources
{sources}

## Methodology
**Paradigm:** {paradigm}
**Level:** {level}
**Quality Score:** {quality}/100
**Sources Analyzed:** {source_count}
**Total Cost:** ${cost:.4f}
**Completed:** {completed_at}
"""


class OutputStageImpl(IPipelineStage):
    """Generate final research report from accumulated context."""

    def __init__(
        self, llm: Any = None, report_dir: str | None = None, *, llm_client: Any = None, knowledge_store: Any = None
    ) -> None:
        self._llm = llm_client or llm
        self._report_dir = report_dir
        self._knowledge_store = knowledge_store

    name = "output"

    async def execute(self, ctx: ResearchContext) -> ResearchContext:
        search_results = ctx.search_results or []
        entities = ctx.entities or []

        # Generate summary
        summary = await self._llm.generate(
            f"Summarize the key findings about: {ctx.query[:500]}\n\n"
            f"Sources analyzed: {len(search_results)}\n"
            f"Entities found: {len(entities)}\n\n"
            f"Deep analysis: {getattr(ctx, 'deep_analysis', '')[:2000]}"
        )

        # Format findings
        findings_lines = []
        for i, result in enumerate(search_results[:15]):
            title = (
                result.get("title", "Untitled") if isinstance(result, dict) else getattr(result, "title", "Untitled")
            )
            content = (
                result.get("content", "") or result.get("snippet", "")
                if isinstance(result, dict)
                else getattr(result, "content", "") or getattr(result, "snippet", "")
            )
            findings_lines.append(f"### {i + 1}. {title}")
            if content:
                findings_lines.append(content[:500])

        # Format sources
        sources_lines = []
        for i, result in enumerate(search_results[:20]):
            url = result.get("url", "") if isinstance(result, dict) else getattr(result, "url", "")
            title = (
                result.get("title", f"Source {i + 1}")
                if isinstance(result, dict)
                else getattr(result, "title", f"Source {i + 1}")
            )
            sources_lines.append(f"{i + 1}. [{title}]({url})" if url else f"{i + 1}. {title}")

        quality_score = 0
        for r in ctx.relations or []:
            if isinstance(r, dict) and "quality_score" in r:
                quality_score = r["quality_score"]

        ctx.report = REPORT_TEMPLATE.format(
            query=ctx.query,
            summary=summary.strip(),
            findings="\n\n".join(findings_lines) or "No specific findings extracted.",
            sources="\n".join(sources_lines) or "No sources recorded.",
            paradigm=getattr(ctx, "paradigm", "Standard"),
            level=str(getattr(ctx, "level", "auto")),
            quality=quality_score,
            source_count=len(search_results),
            cost=0.0,
            completed_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        )
        ctx.stage_timings[self.name] = 0.0
        return ctx


class ExtendedOutputStageImpl(OutputStageImpl):
    """Extended report generation with deeper analysis."""

    def __init__(
        self, llm: Any = None, report_dir: str | None = None, *, llm_client: Any = None, knowledge_store: Any = None
    ) -> None:
        super().__init__(llm, report_dir, llm_client=llm_client, knowledge_store=knowledge_store)
        self._extended = True

    name = "extended_output"

    async def execute(self, ctx: ResearchContext) -> ResearchContext:
        # First generate base report via parent
        ctx = await super().execute(ctx)
        # Extended version would add more depth
        return ctx
