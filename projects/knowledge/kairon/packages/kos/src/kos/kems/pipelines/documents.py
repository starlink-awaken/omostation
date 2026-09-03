"""Documents Domain KEMS Pipelines.

Defines pipelines for the documents domain:
- Quarantine: Detect → Audit → Isolate → Verify → Rollback Manifest
- Audit: Scan → Classify → Report
- Cutover: Backup → Replace → Verify
- Preflight: Check Dependencies → Report
- Retire: Snapshot → Remove → Evidence
- Converge: Analyze → Migrate → Verify
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from typing import Any, Literal

from kos.kems.pipeline import PipelineRun, SourceManifest, StepRun

PipelineType = Literal[
    "documents-quarantine-v1",
    "documents-quarantine-symlink-v1",
    "documents-audit-v1",
    "documents-cutover-v1",
    "documents-preflight-v1",
    "documents-retire-v1",
    "documents-converge-v1",
    "documents-owner-v1",
]


@dataclass(frozen=True)
class QuarantineStep:
    """Steps for quarantine pipeline."""
    DETECT = "detect_runtime_files"
    COMPUTE_HASH = "compute_fingerprints"
    CONSUMER_AUDIT = "consumer_audit"
    QUARANTINE_TRANSACTION = "quarantine_transaction"
    VERIFY_INTEGRITY = "verify_integrity"
    ROLLBACK_MANIFEST = "generate_rollback_manifest"


@dataclass(frozen=True)
class AuditStep:
    """Steps for audit pipeline."""
    SCAN = "scan_documents_root"
    CLASSIFY = "classify_consumers"
    DETECT_FORBIDDEN = "detect_forbidden_executors"
    REPORT = "generate_audit_report"


@dataclass(frozen=True)
class CutoverStep:
    """Steps for cutover pipeline."""
    BACKUP = "backup_crontab"
    REPLACE = "replace_schedule_entry"
    VERIFY_NEW = "verify_new_entry"
    VERIFY_OLD_REMOVED = "verify_old_removed"


@dataclass(frozen=True)
class PreflightStep:
    """Steps for preflight pipeline."""
    CHECK_DEPS = "check_dependencies"
    VALIDATE_PATHS = "validate_paths"
    ENGINE_READINESS = "engine_readiness"
    REPORT = "generate_preflight_report"


@dataclass(frozen=True)
class RetireStep:
    """Steps for retirement pipeline."""
    SNAPSHOT = "snapshot_source"
    REMOVE = "remove_executor"
    EVIDENCE = "record_evidence"


@dataclass(frozen=True)
class ConvergeStep:
    """Steps for convergence pipeline."""
    ANALYZE = "analyze_divergence"
    MIGRATE = "migrate_state"
    VERIFY = "verify_consistency"


@dataclass(frozen=True)
class OwnerStep:
    """Steps for owner job pipeline."""
    DISCOVER = "discover_sources"
    BIND = "bind_to_workspace"
    EXECUTE = "execute_read_only"
    RECORD = "record_evidence"


# ── Pipeline Definitions ──

QUARANTINE_PIPELINE = {
    "pipeline_id": "documents-quarantine-v1",
    "description": "文档隔离 Pipeline: 检测 → 审计 → 隔离 → 验证 → 回滚清单",
    "steps": [
        QuarantineStep.DETECT,
        QuarantineStep.COMPUTE_HASH,
        QuarantineStep.CONSUMER_AUDIT,
        QuarantineStep.QUARANTINE_TRANSACTION,
        QuarantineStep.VERIFY_INTEGRITY,
        QuarantineStep.ROLLBACK_MANIFEST,
    ],
    "quarantine_transaction": {
        "preserve_paths": True,
        "preserve_modes": True,
        "compute_sha256": True,
        "no_follow_symlinks": True,
    },
}

QUARANTINE_SYMLINK_PIPELINE = {
    "pipeline_id": "documents-quarantine-symlink-v1",
    "description": "符号链接隔离 Pipeline: 检测 → no-follow 移动 → 验证",
    "steps": [
        QuarantineStep.DETECT,
        QuarantineStep.CONSUMER_AUDIT,
        "quarantine_symlink_transaction",
        QuarantineStep.VERIFY_INTEGRITY,
        QuarantineStep.ROLLBACK_MANIFEST,
    ],
    "quarantine_transaction": {
        "preserve_paths": True,
        "preserve_modes": True,
        "no_follow_symlinks": True,  # Critical: never follow symlinks
        "preserve_link_target": True,
    },
}

AUDIT_PIPELINE = {
    "pipeline_id": "documents-audit-v1",
    "description": "文档审计 Pipeline: 扫描 → 分类 → 报告",
    "steps": [
        AuditStep.SCAN,
        AuditStep.CLASSIFY,
        AuditStep.DETECT_FORBIDDEN,
        AuditStep.REPORT,
    ],
    "scan_config": {
        "scan_crontab": True,
        "scan_launch_agents": True,
        "scan_scheduled": True,
        "scan_claude": True,
    },
}

CUTOVER_PIPELINE = {
    "pipeline_id": "documents-cutover-v1",
    "description": "计划切换 Pipeline: 备份 → 替换 → 验证",
    "steps": [
        CutoverStep.BACKUP,
        CutoverStep.REPLACE,
        CutoverStep.VERIFY_NEW,
        CutoverStep.VERIFY_OLD_REMOVED,
    ],
    "rollback_on_failure": True,
}

PREFLIGHT_PIPELINE = {
    "pipeline_id": "documents-preflight-v1",
    "description": "预检 Pipeline: 检查依赖 → 验证路径 → 引擎就绪 → 报告",
    "steps": [
        PreflightStep.CHECK_DEPS,
        PreflightStep.VALIDATE_PATHS,
        PreflightStep.ENGINE_READINESS,
        PreflightStep.REPORT,
    ],
}

RETIRE_PIPELINE = {
    "pipeline_id": "documents-retire-v1",
    "description": "退役 Pipeline: 快照 → 移除 → 证据",
    "steps": [
        RetireStep.SNAPSHOT,
        RetireStep.REMOVE,
        RetireStep.EVIDENCE,
    ],
    "preserve_snapshot": True,
}

CONVERGE_PIPELINE = {
    "pipeline_id": "documents-converge-v1",
    "description": "收敛 Pipeline: 分析 → 迁移 → 验证",
    "steps": [
        ConvergeStep.ANALYZE,
        ConvergeStep.MIGRATE,
        ConvergeStep.VERIFY,
    ],
}

OWNER_PIPELINE = {
    "pipeline_id": "documents-owner-v1",
    "description": "Owner Job Pipeline: 发现 → 绑定 → 执行 → 记录",
    "steps": [
        OwnerStep.DISCOVER,
        OwnerStep.BIND,
        OwnerStep.EXECUTE,
        OwnerStep.RECORD,
    ],
    "read_only": True,
}

# Registry of all documents pipelines
DOCS_PIPELINES: dict[str, dict[str, Any]] = {
    p["pipeline_id"]: p
    for p in [
        QUARANTINE_PIPELINE,
        QUARANTINE_SYMLINK_PIPELINE,
        AUDIT_PIPELINE,
        CUTOVER_PIPELINE,
        PREFLIGHT_PIPELINE,
        RETIRE_PIPELINE,
        CONVERGE_PIPELINE,
        OWNER_PIPELINE,
    ]
}


def get_pipeline(pipeline_id: str) -> dict[str, Any]:
    """Get pipeline definition by ID."""
    if pipeline_id not in DOCS_PIPELINES:
        raise ValueError(f"Unknown pipeline: {pipeline_id}")
    return DOCS_PIPELINES[pipeline_id]


def list_pipelines() -> list[str]:
    """List all registered pipeline IDs."""
    return list(DOCS_PIPELINES.keys())


def create_pipeline_run(pipeline_id: str, source: SourceManifest) -> PipelineRun:
    """Create a new pipeline run."""
    pipeline = get_pipeline(pipeline_id)
    now = datetime.now(UTC).isoformat()
    return PipelineRun(
        run_id=f"run-{pipeline_id}-{source.source_id}-{int(datetime.now(UTC).timestamp())}",
        pipeline_id=pipeline_id,
        created_at=now,
        source=source,
        steps=[StepRun(step_id=s) for s in pipeline["steps"]],
    )
