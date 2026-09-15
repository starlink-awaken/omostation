"""Pipeline stage: Query decomposition and deep content extraction."""

from __future__ import annotations

import asyncio
from typing import Any

from minerva.knowledge.store import Entity
from minerva.pipeline.engine import IPipelineStage, ResearchContext
from minerva.shared import spacy_to_entity_type

DECOMPOSE_PROMPT = """Decompose this research question into 3-5 specific sub-questions.
Each sub-question should cover a distinct aspect. Output one question per line.

Question: {query}
Sub-questions:"""

DEEP_READ_PROMPT = """Analyze the following documents about: {query}
Extract:
1. Key claims and their evidence level (strong / moderate / weak)
2. Named entities (people, orgs, technologies, concepts)
3. Contradictions or disagreements between sources
4. Open questions or gaps

Focus on factual content over opinion. Output in structured sections.

Documents:
{documents}

Analysis:"""


class DecomposeStageImpl(IPipelineStage):
    """Decompose query into sub-questions for parallel search."""

    name = "decompose"

    def __init__(self, llm: Any, prompt: str | None = None, *, max_sub_questions: int = 5) -> None:
        self._llm = llm
        self._prompt = prompt or DECOMPOSE_PROMPT
        self._max_sub_questions = max_sub_questions

    async def execute(self, ctx: ResearchContext) -> ResearchContext:
        resp = await self._llm.generate(self._prompt.format(query=ctx.query))
        ctx.sub_questions = [q.strip() for q in resp.split("\n") if q.strip() and len(q.strip()) > 10]
        ctx.stage_timings[self.name] = 0.0
        return ctx


class EntityExtractionStageImpl(IPipelineStage):
    """Extract named entities from search results."""

    name = "extract"

    def __init__(self, nlp: Any, llm_client: Any = None, knowledge_store: Any = None, *, nlp_zh: Any = None) -> None:
        self._nlp = nlp
        self._nlp_zh = nlp_zh
        self._llm_client = llm_client
        self._knowledge_store = knowledge_store

    async def execute(self, ctx: ResearchContext) -> ResearchContext:
        if self._nlp is None:
            return ctx
        text = " ".join(s.get("content", "") or "" for s in (ctx.search_results or []))
        if not text:
            return ctx
        loop = asyncio.get_running_loop()
        doc = await loop.run_in_executor(None, self._nlp, text[:50000])
        seen = set()
        for ent in doc.ents:
            e_type = spacy_to_entity_type(ent.label_)
            key = (ent.text.lower(), e_type)
            if key not in seen:
                seen.add(key)
                ctx.entities.append(Entity(id=ent.text.lower(), name=ent.text, type=e_type))
        ctx.stage_timings[self.name] = 0.0
        return ctx


class DeepReadStageImpl(IPipelineStage):
    """Deep content analysis of search results."""

    name = "deep_read"

    def __init__(
        self,
        llm: Any = None,
        prompt: str | None = None,
        *,
        top_n: int = 15,
        search_engine: Any = None,
        long_context: Any = None,
    ) -> None:
        self._llm = llm or long_context
        self._prompt = prompt or DEEP_READ_PROMPT
        self._top_n = top_n
        self._search_engine = search_engine

    async def execute(self, ctx: ResearchContext) -> ResearchContext:
        if not ctx.search_results:
            return ctx
        docs_text = "\n\n".join(
            f"[{i + 1}] {s.get('content', '') or s.get('snippet', '') or ''}"
            for i, s in enumerate(ctx.search_results[:8])
        )
        try:
            analysis = await self._llm.generate(self._prompt.format(query=ctx.query, documents=docs_text[:8000]))
        except Exception as exc:
            import logging

            logging.getLogger("minerva.deep_read").warning(f"deep_read LLM 调用失败 (降级): {exc}")
            analysis = (
                f"[降级摘要 - LLM 不可用] 基于 {len(ctx.search_results or [])} 个来源的原始内容摘录:\n"
                + docs_text[:4000]
            )
        ctx.deep_analysis = analysis
        ctx.stage_timings[self.name] = 0.0
        return ctx
