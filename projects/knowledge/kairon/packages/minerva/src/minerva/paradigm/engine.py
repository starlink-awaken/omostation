# DEPRECATED — This module has concept overlap with the sophia package.
# Retained for backward compatibility. New code should use sophia directly.
# This module will be removed in a future release.

"""Paradigm Engine — execute research within a structured paradigm framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from minerva.paradigm.types import (
    PARADIGMS,
    ParadigmResult,
    ResearchParadigm,
    VerificationMode,
)

logger = structlog.get_logger(__name__)


@dataclass
class ParadigmContext:
    """Context for paradigm execution — extends the pipeline ResearchContext."""

    paradigm: ResearchParadigm
    paradigm_result: ParadigmResult
    max_iterations: int = 3
    iteration: int = 0
    completion_met: bool = False
    verification_passed: bool = True
    stage_history: list[dict] = field(default_factory=list)
    paradigm_prompts: dict[str, str] = field(default_factory=dict)


async def execute_with_paradigm(
    pipeline: Any,
    llm_client: Any,
    ctx: Any,  # ResearchContext
    paradigm_result: ParadigmResult,
    max_iterations: int = 3,
) -> ParadigmContext:
    """Execute research within a paradigm framework.

    The paradigm determines:
    1. Which stages run and in what order
    2. What verification gates apply
    3. Whether to iterate (re-search + re-verify) if criteria not met
    4. Completion conditions
    """
    paradigm_def = PARADIGMS[paradigm_result.paradigm]
    pctx = ParadigmContext(
        paradigm=paradigm_result.paradigm,
        paradigm_result=paradigm_result,
        max_iterations=max_iterations,
    )

    logger.info(
        "paradigm_selected",
        paradigm=paradigm_def.name,
        verification=paradigm_def.verification_mode.value,
        stages=paradigm_def.stages,
        confidence=paradigm_result.confidence,
    )

    # Run the pipeline with paradigm-aware stages
    for iteration in range(max_iterations):
        pctx.iteration = iteration
        logger.info("paradigm_iteration", paradigm=paradigm_def.name, iteration=iteration + 1)

        ctx = await pipeline.run(ctx.query, ctx.level, ctx.triage)

        # Check completion criteria
        criteria_met, failures = _check_completion(ctx, paradigm_def, paradigm_result.paradigm)
        if criteria_met:
            pctx.completion_met = True
            logger.info("paradigm_complete", paradigm=paradigm_def.name, iteration=iteration + 1)
            break
        else:
            logger.warning(
                "paradigm_iteration_failed",
                paradigm=paradigm_def.name,
                iteration=iteration + 1,
                failures=failures,
            )
            if paradigm_def.verification_mode == VerificationMode.STRICT and iteration < max_iterations - 1:
                logger.info("paradigm_reiterating", reason="strict verification requires retry")
                # Enrich the query with failure feedback for next iteration
                ctx.query = _enrich_query_for_retry(ctx.query, failures)
            else:
                pctx.verification_passed = False
                break

    pctx.verification_passed = True
    return pctx


def _check_completion(ctx: Any, paradigm_def: Any, paradigm: ResearchParadigm) -> tuple[bool, list[str]]:
    """Check if the paradigm's completion criteria are satisfied."""
    failures = []
    criteria = paradigm_def.completion_criteria

    for i, criterion in enumerate(criteria):
        if not _check_criterion(ctx, criterion, paradigm):
            failures.append(f"[C{i + 1}] {criterion}")

    return len(failures) == 0, failures


def _check_criterion(ctx: Any, criterion: str, paradigm: ResearchParadigm) -> bool:
    """Check a single completion criterion against the research context."""
    c = criterion.lower()

    if "traceable source" in c:
        return len(ctx.search_results) >= 3

    if "counter-argument" in c:
        return any(
            rel.get("counter_argument") and len(rel.get("counter_argument", "")) > 50 for rel in (ctx.relations or [])
        )

    if "confidence level" in c:
        return len(ctx.entities) > 0 or len(ctx.search_results) >= 2

    if "verification gate" in c:
        return any("quality_score" in rel and rel["quality_score"] >= 60 for rel in ctx.relations or [])

    if "comparison criteria" in c or "each option" in c or "trade-off" in c:
        return len(ctx.search_results) >= 5

    if "hypotheses" in c or "problem" in c or "solution verified" in c:
        has_verification = any(rel.get("verification", {}).get("verified", False) for rel in (ctx.relations or []))
        return len(ctx.search_results) >= 4 and (has_verification or len(ctx.entities) >= 2)

    if "scope" in c or "categor" in c or "taxonom" in c or "gap" in c:
        return len(ctx.search_results) >= 5

    if "stakeholder" in c or "policy context" in c or "impact" in c:
        return len(ctx.search_results) >= 5

    # Default: has enough sources
    return len(ctx.search_results) >= 3


def _enrich_query_for_retry(query: str, failures: list[str]) -> str:
    """Enrich the query with feedback from failed completion criteria."""
    failure_text = "; ".join(failures[:3])
    return f"{query} [Re-search needed: {failure_text}]"


def get_paradigm_report_header(paradigm: ResearchParadigm) -> str:
    """Generate a paradigm-specific report header showing the framework used."""
    pdef = PARADIGMS[paradigm]
    lines = [
        f"> **Research Paradigm**: {pdef.name}",
        f"> **Verification Mode**: {pdef.verification_mode.value.upper()}",
        f"> **Framework Stages**: {' → '.join(pdef.stages)}",
        "> **Completion Criteria**:",
    ]
    for c in pdef.completion_criteria:
        lines.append(f">   - {c}")
    return "\n".join(lines)
