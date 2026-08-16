"""Pipeline stage implementations — CrossAnalyze, QualityGate, CounterArgument, MultiModelVoting stages."""

from __future__ import annotations

from typing import Any

from minerva.pipeline.engine import IPipelineStage, QualityGateError, ResearchContext

CROSS_ANALYZE_PROMPT = """Given this analysis of multiple sources about: {query}

{analysis}

Perform deep reasoning:
1. For each contradiction: which claim is more credible and why?
2. For each gap: is it unexplored or unsolvable with current methods?
3. Based on evolution patterns: what is the likely next development?
4. Assign confidence scores (HIGH/MEDIUM/LOW) to each conclusion.

Output structured reasoning in markdown."""

COUNTER_ARGUMENT_PROMPT = """Given this research on: {query}

{findings}

You are playing devil's advocate. Identify:
1. The strongest counter-arguments to the main conclusions
2. Alternative interpretations of the evidence
3. Weaknesses in methodology or assumptions
4. Missing perspectives or stakeholders
5. Overlooked risks or downsides

Be specific and cite sources where possible. Output in markdown."""

MULTI_MODEL_PROMPT = """Given this research analysis on: {query}

{analysis}

You are a panel of expert reviewers. Provide:
1. Voting on each major conclusion (AGREE/DISAGREE/NEUTRAL with justification)
2. Confidence score for each conclusion (HIGH/MEDIUM/LOW)
3. Areas where models disagree and why
4. Recommended follow-up research questions
5. Final consensus summary

Output in structured markdown."""


class CrossAnalyzeStageImpl(IPipelineStage):
    """Deep reasoning analysis on extracted content."""

    name = "cross_analyze"

    def __init__(self, llm_client: Any) -> None:
        self.llm = llm_client

    async def execute(self, ctx: ResearchContext) -> ResearchContext:
        # Build analysis text from multiple sources
        parts = []

        # 1. DeepRead contradiction analysis
        for c in ctx.contradictions or []:
            analysis_text = c.get("analysis", "")
            if analysis_text and analysis_text != "Deep read analysis unavailable.":
                parts.append(analysis_text)

        # 2. Extracted document content (from DeepRead)
        for doc in (ctx.extracted_content or [])[:5]:
            if doc:
                parts.append(doc[:500])

        analysis = "\n---\n".join(parts)

        if not analysis.strip():
            ctx.relations = []
            return ctx

        try:
            reasoning = await self.llm.generate(
                system="You perform deep cross-analysis on research findings. Identify patterns, consensus, contradictions, gaps, and synthesize key insights.",
                prompt=CROSS_ANALYZE_PROMPT.format(query=ctx.query, analysis=analysis[:4000]),
                temperature=0.5,
                max_tokens=1500,
            )
        except Exception:
            reasoning = "Cross-analysis unavailable."

        ctx.relations = ctx.relations or []
        ctx.relations.append({"reasoning": reasoning})
        return ctx


class QualityGateStageImpl(IPipelineStage):
    """Verify research quality and assign a quality score."""

    name = "quality_gate"

    async def execute(self, ctx: ResearchContext) -> ResearchContext:
        failures = []
        score = 100

        # Source count
        if not ctx.search_results:
            failures.append("No search results found")
            score = 0
        elif len(ctx.search_results) < 3:
            failures.append("Insufficient sources (<3)")
            score -= 30
        elif len(ctx.search_results) < 5:
            score -= 10

        # Entity extraction
        if not ctx.entities:
            score -= 10  # No entities found — but not a failure

        # Contradiction depth
        has_analysis = any(c.get("analysis") and len(c.get("analysis", "")) > 50 for c in (ctx.contradictions or []))
        if not has_analysis and ctx.contradictions:
            score -= 10

        # Source diversity
        if ctx.search_results:
            sources = {r.get("source", "") for r in ctx.search_results}
            if len(sources) == 1:
                score -= 15  # Only one backend

        ctx.relations = ctx.relations or []
        ctx.relations.append(
            {
                "quality_score": max(0, score),
                "quality_gate_checks": {
                    "source_count": len(ctx.search_results),
                    "entity_count": len(ctx.entities),
                    "contradiction_analysis": has_analysis,
                },
                "failures": failures,
            }
        )

        if failures:
            raise QualityGateError(f"[score:{score}] {'; '.join(failures)}")

        return ctx


class CounterArgumentStageImpl(IPipelineStage):
    """Generate counter-arguments and alternative perspectives. (L3+)"""

    name = "counter_argument"

    def __init__(self, llm_client: Any) -> None:
        self.llm = llm_client

    async def execute(self, ctx: ResearchContext) -> ResearchContext:
        findings = ""
        for c in ctx.contradictions or []:
            findings += c.get("analysis", "") + "\n"
        if not findings.strip():
            findings = "\n".join(
                f"- {r.get('title', '')}: {r.get('snippet', '')[:200]}" for r in ctx.search_results[:5]
            )

        try:
            response = await self.llm.generate(
                system="You are a critical thinker who identifies weaknesses and alternative perspectives in research.",
                prompt=COUNTER_ARGUMENT_PROMPT.format(query=ctx.query, findings=findings[:4000]),
                temperature=0.5,
                max_tokens=1500,
            )
        except Exception:
            response = "Counter-argument analysis unavailable."

        ctx.relations = ctx.relations or []
        ctx.relations.append({"counter_argument": response})
        return ctx


class MultiModelVotingStageImpl(IPipelineStage):
    """Multi-model voting on conclusions. (L4)"""

    name = "multi_model_voting"

    def __init__(self, llm_client: Any) -> None:
        self.llm = llm_client

    async def execute(self, ctx: ResearchContext) -> ResearchContext:
        analysis = ""
        for r in ctx.relations or []:
            for v in r.values():
                analysis += str(v)[:2000] + "\n"

        if not analysis.strip():
            ctx.relations = ctx.relations or []
            ctx.relations.append({"voting": "Insufficient data for multi-model voting."})
            return ctx

        try:
            response = await self.llm.generate(
                system="You are a panel of expert reviewers evaluating research conclusions.",
                prompt=MULTI_MODEL_PROMPT.format(query=ctx.query, analysis=analysis[:4000]),
                temperature=0.4,
                max_tokens=1500,
            )
        except Exception:
            response = "Multi-model voting unavailable."

        ctx.relations = ctx.relations or []
        ctx.relations.append({"voting": response})
        return ctx
