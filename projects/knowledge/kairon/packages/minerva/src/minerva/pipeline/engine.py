"""
Minerva Pipeline Engine — Tiered research pipeline execution.

Executes research at L0-L4 levels with pluggable, composable stages.
Each level is a predefined sequence of stages with appropriate models and budgets.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import structlog

from minerva.triage.router import ResearchLevel, TriageResult

logger = structlog.get_logger(__name__)


# ============================================================
# Data Models
# ============================================================


@dataclass
class ResearchContext:
    """Mutable context passed through pipeline stages."""

    query: str
    level: ResearchLevel
    triage: TriageResult

    # Populated by stages
    sub_questions: list[str] = field(default_factory=list)
    search_results: list[dict] = field(default_factory=list)
    extracted_content: list[str] = field(default_factory=list)
    entities: list[Any] = field(default_factory=list)
    relations: list[dict] = field(default_factory=list)
    contradictions: list[dict] = field(default_factory=list)
    report: str | None = None
    deep_analysis: str = ""
    report_path: str | None = None

    # Stage metadata (flags, audit results, etc.)
    metadata: dict = field(default_factory=dict)

    # Metrics
    cost: float = 0.0
    started_at: str | None = None
    completed_at: str | None = None
    stage_timings: dict[str, float] = field(default_factory=dict)


# ============================================================
# Stage Interface
# ============================================================


class IPipelineStage(ABC):
    """A single stage in the research pipeline."""

    name: str = "base_stage"

    @abstractmethod
    async def execute(self, ctx: ResearchContext) -> ResearchContext:
        """Execute this stage. Returns (possibly mutated) context."""
        ...


# ============================================================
# Pipeline Definition
# ============================================================


class Pipeline:
    """Execute tiered research pipelines.

    Usage:
        pipeline = Pipeline(stages_by_level)
        ctx = await pipeline.run("What is MoE?", ResearchLevel.L2)
    """

    def __init__(self, stages: dict[ResearchLevel, list[IPipelineStage]]) -> None:
        self.stages = stages

    async def run(self, query: str, level: ResearchLevel, triage: TriageResult) -> ResearchContext:
        """Execute pipeline at given level.

        Flow:
        1. Create ResearchContext with query, level, triage
        2. For each stage in stages[level]:
           a. Execute stage
           b. Log timing
           c. Check for QualityGate failure → retry
        3. Return completed context
        """
        ctx = ResearchContext(query=query, level=level, triage=triage)

        import time

        stage_list = self.stages.get(level, [])
        retries = 0
        max_retries = 2

        i = 0
        while i < len(stage_list):
            stage = stage_list[i]
            t0 = time.time()

            try:
                ctx = await stage.execute(ctx)
            except QualityGateError:
                if retries < max_retries:
                    logger.warning("quality_gate_failed", stage=stage.name, retry=retries + 1)
                    retries += 1
                    i = max(0, i - 2)  # Go back 2 stages, retry DeepRead
                    continue
                else:
                    logger.error("quality_gate_max_retries", max_retries=max_retries)
                    # Proceed with degraded quality

            elapsed = time.time() - t0
            ctx.stage_timings[stage.name] = elapsed
            logger.info("stage_complete", stage=stage.name, elapsed_s=elapsed, cost=ctx.cost)
            i += 1

        ctx.completed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return ctx


class QualityGateError(Exception):
    """Raised when research quality checks fail."""

    pass


# ============================================================
# Pipeline Factory
# ============================================================


def create_default_pipeline(
    llm_client: Any = None,
    search_engine: Any = None,
    nlp_pipeline: Any = None,
    knowledge_store: Any = None,
    creative_tool: Any = None,
    nlp_pipeline_zh: Any = None,
    cloud_llm_client: Any = None,
    glm_llm_client: Any = None,
    kos_save_enabled: bool = False,
    immune_audit_enabled: bool = False,
    vault_sink_enabled: bool = False,
) -> Pipeline:
    """Create pipeline with default stage configurations for each level.

    L0-L2 use local llm_client. L3-L4 use cloud_llm_client (DeepSeek V4 Pro).
    DeepRead uses glm_llm_client (GLM-4.7 Flash, 128K context, free) when available.

    Args:
        kos_save_enabled: Append KOSSaveStage after the output stage.
        immune_audit_enabled: Insert ImmuneAuditStage before quality gate.
    """

    from minerva.pipeline.stages import (
        CounterArgumentStageImpl,
        CrossAnalyzeStageImpl,
        DecomposeStageImpl,
        DeepReadStageImpl,
        EntityExtractionStageImpl,
        ExtendedOutputStageImpl,
        ImmuneAuditStage,
        KOSSaveStage,
        MultiModelVotingStageImpl,
        MultiSourceSearchStageImpl,
        OutputStageImpl,
        QualityGateStageImpl,
    )
    from minerva.sinks.vault_sink import VaultSinkStage

    # L3/L4 use cloud client for enterprise reasoning (DeepSeek V4 Pro).
    # Falls back to local qwen3.6:27b if cloud is unavailable.
    reasoner = cloud_llm_client or llm_client
    # DeepRead uses cloud client (V4 Pro 1M ctx) > GLM (128K free) > local
    long_context = cloud_llm_client or glm_llm_client or llm_client

    stages = {
        ResearchLevel.L0: [
            MultiSourceSearchStageImpl(
                search_engine,
                backends=["ddg", "scholar", "metaso", "exa", "brave", "zhipu"],
                max_results=5,
            ),
            QualityGateStageImpl(),
            OutputStageImpl(llm_client=llm_client, knowledge_store=knowledge_store),
        ],
        ResearchLevel.L1: [
            DecomposeStageImpl(llm_client, max_sub_questions=5),
            MultiSourceSearchStageImpl(
                search_engine,
                backends=["ddg", "scholar", "metaso", "exa", "brave", "zhipu"],
                max_results=10,
            ),
            CrossAnalyzeStageImpl(llm_client),
            QualityGateStageImpl(),
            OutputStageImpl(llm_client=llm_client, knowledge_store=knowledge_store),
        ],
        ResearchLevel.L2: [
            DecomposeStageImpl(llm_client, max_sub_questions=10),
            MultiSourceSearchStageImpl(
                search_engine,
                backends=["ddg", "scholar", "arxiv", "metaso", "exa", "brave", "zhipu"],
                max_results=25,
            ),
            EntityExtractionStageImpl(nlp_pipeline, llm_client, knowledge_store, nlp_zh=nlp_pipeline_zh),
            DeepReadStageImpl(llm=long_context, search_engine=search_engine, top_n=15),
            CrossAnalyzeStageImpl(llm_client),
            QualityGateStageImpl(),
            OutputStageImpl(llm_client=llm_client, knowledge_store=knowledge_store),
        ],
        ResearchLevel.L3: [
            DecomposeStageImpl(llm_client, max_sub_questions=15),
            MultiSourceSearchStageImpl(
                search_engine,
                backends=["ddg", "scholar", "arxiv", "metaso", "exa", "brave", "zhipu"],
                max_results=35,
            ),
            EntityExtractionStageImpl(nlp_pipeline, llm_client, knowledge_store, nlp_zh=nlp_pipeline_zh),
            DeepReadStageImpl(llm=long_context, search_engine=search_engine, top_n=20),
            CrossAnalyzeStageImpl(reasoner),
            CounterArgumentStageImpl(reasoner),
            QualityGateStageImpl(),
            OutputStageImpl(llm_client=llm_client, knowledge_store=knowledge_store),
        ],
        ResearchLevel.L4: [
            DecomposeStageImpl(llm_client, max_sub_questions=15),
            MultiSourceSearchStageImpl(
                search_engine,
                backends=["ddg", "scholar", "arxiv", "metaso", "exa", "brave", "zhipu"],
                max_results=50,
            ),
            EntityExtractionStageImpl(nlp_pipeline, llm_client, knowledge_store, nlp_zh=nlp_pipeline_zh),
            DeepReadStageImpl(llm=long_context, search_engine=search_engine, top_n=25),
            CrossAnalyzeStageImpl(reasoner),
            CounterArgumentStageImpl(reasoner),
            MultiModelVotingStageImpl(reasoner),
            QualityGateStageImpl(),
            ExtendedOutputStageImpl(llm_client=llm_client, knowledge_store=knowledge_store),
        ],
    }

    if kos_save_enabled:
        for level in list(stages):
            stages[level] = stages[level] + [KOSSaveStage()]

    if immune_audit_enabled:
        # Insert ImmuneAuditStage before the quality gate in each level
        for level in list(stages):
            quality_idx = None
            for i, stage in enumerate(stages[level]):
                if stage.name == "quality_gate":
                    quality_idx = i
                    break
            if quality_idx is not None:
                stages[level].insert(quality_idx, ImmuneAuditStage())
            else:
                # Append at end if no quality gate
                stages[level] = stages[level] + [ImmuneAuditStage()]

    if vault_sink_enabled:
        # Append VaultSinkStage after all output stages
        for level in list(stages):
            stages[level] = stages[level] + [VaultSinkStage()]

    return Pipeline(stages)
