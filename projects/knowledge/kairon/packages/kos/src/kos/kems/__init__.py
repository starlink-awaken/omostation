"""KEMS domain adapters built on top of the generic KOS ingestion layer."""

from .adjudication import AdjudicationStore
from .content_checks import (
    ContentCheckReport,
    ContentIssue,
    ContentRecord,
    SourceConsistencyReport,
    check_content_records,
    check_source_consistency,
)
from .domain_profile import DomainProfile, build_domain_profile
from .enrichment import EnrichmentResult, EvaluationReport, enrich_policy, evaluate_policy_fixture
from .evaluation import EvaluationManifest, EvaluationRun, EvaluationSample, evaluate_field_mapping
from .evaluation_store import EvaluationStore
from .forecast import (
    ShadowForecast,
    ShadowForecastEvaluation,
    build_moving_average_shadow_forecast,
    build_naive_shadow_forecast,
    evaluate_shadow_forecast,
)
from .forecast_store import ForecastStore
from .graph_store import DocumentVersion, EvidenceSpan, GraphEntity, GraphRelation, GraphStore
from .health import (
    KemsPersistenceError,
    SQLiteHealth,
    backup_sqlite_database,
    inspect_databases,
    inspect_sqlite_database,
    restore_sqlite_database,
)
from .ingest import ImportedDocument, ImportPolicy, import_document
from .model_acceptance import ModelInputError, evaluate_candidate
from .model_acceptance_store import ModelAcceptanceStore
from .ocr_quality import OCRPageQuality, OCRQualityPolicy, OCRQualityReport, assess_ocr_quality
from .ocr_quality_store import OCRQualityStore
from .omo_adapter import OmoTaskAdapter
from .pipeline import PipelineRun, SourceManifest, StepRun
from .policy import PolicyAnalysis, analyze_policy_document, analyze_policy_file
from .promotion_gate import PromotionGateInputError, build_model_promotion_gate
from .run_record import KemsRunRecord, create_run_record
from .run_store import RunStore
from .runner import PipelineExecutor, PipelineStep
from .scenarios import (
    ScenarioAnalysis,
    analyze_ai_survey,
    analyze_reconsideration,
    analyze_tri_medical_minutes,
)
from .task_contract import TaskDraft

__all__ = (
    "EnrichmentResult",
    "EvaluationReport",
    "EvaluationManifest",
    "EvaluationRun",
    "EvaluationSample",
    "EvaluationStore",
    "AdjudicationStore",
    "ContentCheckReport",
    "ContentIssue",
    "ContentRecord",
    "SourceConsistencyReport",
    "check_content_records",
    "check_source_consistency",
    "DomainProfile",
    "build_domain_profile",
    "ModelAcceptanceStore",
    "ModelInputError",
    "evaluate_candidate",
    "PromotionGateInputError",
    "build_model_promotion_gate",
    "ShadowForecast",
    "ShadowForecastEvaluation",
    "ForecastStore",
    "KemsPersistenceError",
    "SQLiteHealth",
    "inspect_sqlite_database",
    "inspect_databases",
    "backup_sqlite_database",
    "restore_sqlite_database",
    "build_naive_shadow_forecast",
    "build_moving_average_shadow_forecast",
    "evaluate_shadow_forecast",
    "DocumentVersion",
    "EvidenceSpan",
    "GraphEntity",
    "GraphRelation",
    "GraphStore",
    "ImportPolicy",
    "ImportedDocument",
    "KemsRunRecord",
    "RunStore",
    "PolicyAnalysis",
    "PipelineRun",
    "SourceManifest",
    "StepRun",
    "PipelineExecutor",
    "PipelineStep",
    "TaskDraft",
    "OCRPageQuality",
    "OCRQualityPolicy",
    "OCRQualityReport",
    "OCRQualityStore",
    "OmoTaskAdapter",
    "ScenarioAnalysis",
    "analyze_ai_survey",
    "analyze_policy_document",
    "analyze_policy_file",
    "analyze_reconsideration",
    "analyze_tri_medical_minutes",
    "create_run_record",
    "enrich_policy",
    "assess_ocr_quality",
    "evaluate_field_mapping",
    "evaluate_policy_fixture",
    "import_document",
)
