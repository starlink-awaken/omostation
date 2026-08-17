"""Pipeline stages — re-export all stage implementations."""

from __future__ import annotations

from minerva.pipeline.immune_audit import ImmuneAuditStage
from minerva.pipeline.stages.extract import (
    DECOMPOSE_PROMPT,
    DEEP_READ_PROMPT,
    DecomposeStageImpl,
    DeepReadStageImpl,
    EntityExtractionStageImpl,
)
from minerva.pipeline.stages.kos_save import KOSSaveStage
from minerva.pipeline.stages.report import (
    REPORT_TEMPLATE,
    ExtendedOutputStageImpl,
    OutputStageImpl,
)
from minerva.pipeline.stages.search import MultiSourceSearchStageImpl
from minerva.pipeline.stages.verify import (
    COUNTER_ARGUMENT_PROMPT,
    CROSS_ANALYZE_PROMPT,
    MULTI_MODEL_PROMPT,
    CounterArgumentStageImpl,
    CrossAnalyzeStageImpl,
    MultiModelVotingStageImpl,
    QualityGateStageImpl,
)

__all__ = [
    "COUNTER_ARGUMENT_PROMPT",
    "CROSS_ANALYZE_PROMPT",
    "DECOMPOSE_PROMPT",
    "DEEP_READ_PROMPT",
    "MULTI_MODEL_PROMPT",
    "REPORT_TEMPLATE",
    "CounterArgumentStageImpl",
    "CrossAnalyzeStageImpl",
    "DecomposeStageImpl",
    "DeepReadStageImpl",
    "EntityExtractionStageImpl",
    "ExtendedOutputStageImpl",
    "ImmuneAuditStage",
    "KOSSaveStage",
    "MultiModelVotingStageImpl",
    "MultiSourceSearchStageImpl",
    "OutputStageImpl",
    "QualityGateStageImpl",
]
