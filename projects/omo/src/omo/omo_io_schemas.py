"""AppendOnlyLog 7 个 consumer 的 Pydantic 模型 (Round 9 P0 + Round 12 P0).

SSOT: 与 ``.omo/_knowledge/management/append-only-log-schemas-2026-06-09.md`` 一一对应.

设计:
  - 7 个 BaseModel, 必填字段 = 文档 required_fields
  - Status 字段用 Enum (type-safe)
  - 时间戳字段: type str, validator 强制 'Z' 结尾
  - 字段名 snake_case, 与 JSONL 行内字段名一致
  - Optional 字段标 Optional[...] (e.g. omo_history.source)

使用:
    from omo.omo_io_schemas import OmoAuditRecord
    from omo.omo_io import AppendOnlyLog

    rec = OmoAuditRecord.model_validate({"ts": "...", "action": "...", ...})
    AppendOnlyLog(path).append(rec.model_dump(), schema=OmoAuditRecord)
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# Round 25 P0: ZTimestampModel + 通用 validator 抽到 omo._shared (跨仓 SSOT 落地)
# 之前 Round 8 P2 + Round 11 /simplify 收口位置在 omo_io_schemas.py 内.
# §12.1.3 跨仓契约配套: 任何仓 Pydantic schema 继承 ZTimestampModel 即得 Z-suffix 校验.
from omo._shared.z_timestamp_model import ZTimestampModel  # noqa: F401  (re-export)


# ── Consumer 1: omo_audit ───────────────────────────────────


class OmoAuditRecord(ZTimestampModel):
    """governance action 审计记录 (Round 8 P2 SSOT)."""

    ts: str
    action: str = Field(..., min_length=1)
    debt_id: str = ""
    actor: str = Field(..., min_length=1)
    details: str = ""


# ── Consumer 2: omo_bos_metrics ──────────────────────────────


class BosStatus(str, Enum):
    """BOS invoke 状态枚举 (Round 8 P2 SSOT)."""

    RESOLVED = "resolved"
    AGORA_UNAVAILABLE = "agora_unavailable"
    INVALID_URI = "invalid_uri"
    ENDPOINT_MISSING = "endpoint_missing"
    TIMEOUT = "timeout"
    ERROR = "error"


class OmoBosMetricsRecord(ZTimestampModel):
    """BOS invoke 监控记录."""

    uri: str = Field(..., min_length=1)
    status: BosStatus
    elapsed_ms: float = Field(..., ge=0)
    transport: str = ""
    error: str = Field(default="", max_length=200)
    recorded_at: str


# ── Consumer 3: omo_sync ───────────────────────────────────


class OmoSyncStatus(str, Enum):
    OK = "ok"
    ERROR = "error"


class OmoSyncRecord(ZTimestampModel):
    """omo state sync 记录 (Round 8 P2 SSOT)."""

    ts: str
    kind: Literal["omo_sync"] = "omo_sync"
    phase: int
    health_score: float = Field(..., ge=0, le=100)
    dry_run: bool
    audit_checks: int = Field(..., ge=0)
    status: OmoSyncStatus
    error: str = ""

    @model_validator(mode="after")
    def _check_error_only_when_error(self) -> "OmoSyncRecord":
        if self.status == OmoSyncStatus.ERROR and not self.error:
            raise ValueError("error field required when status=error")
        return self


# ── Consumer 4: omo_alert ──────────────────────────────────


class OmoAlertSeverity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class OmoAlertRecord(ZTimestampModel):
    """KEI threshold alert 记录 (Round 8 P2 SSOT)."""

    ts: str
    kind: Literal["kei_threshold"] = "kei_threshold"
    severity: OmoAlertSeverity
    message: str
    blocked_rate: int = Field(..., ge=0)
    failed_rate: int = Field(..., ge=0)
    threshold: int = Field(..., ge=1)


# ── Consumer 5: omo_event ──────────────────────────────────


class OmoEventRecord(ZTimestampModel):
    """用户面向 emit 事件记录 (Round 5 P3 样板)."""

    ts: str
    kind: str = Field(..., min_length=1)
    source: str = Field(default="cli", min_length=1)
    payload: str = Field(default="{}", min_length=1)

    @field_validator("payload")
    @classmethod
    def _check_payload_is_json(cls, v: str) -> str:
        # payload 字段约定是 JSON 字符串, 但不强校验 schema (业务方负责)
        import json as _json
        try:
            _json.loads(v)
        except _json.JSONDecodeError as exc:
            raise ValueError(f"payload must be valid JSON string, got: {v!r} ({exc})")
        return v


# ── Consumer 6: omo_history ─────────────────────────────────


class OmoHistoryGrade(str, Enum):
    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class OmoHistoryRecord(ZTimestampModel):
    """治理审计历史记录 (Round 8 P2 SSOT).

    note: source 标 Optional — 老记录 (Round 8 P2 之前) 没有此字段.
    """

    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    timestamp: str
    total_score: float = Field(..., ge=0, le=100)
    grade: OmoHistoryGrade
    watchlist_count: int = Field(..., ge=0)
    source: Optional[str] = None  # 老记录无
    # 用户业务字段: 任意 key, 允许多余 (forward compat)
    model_config = {"extra": "allow"}


# ── Consumer 7: omo_trail ───────────────────────────────────


class OmoTrailStatus(str, Enum):
    """trail step 执行状态 (Round 12 P0)."""

    OK = "ok"
    FAIL = "fail"
    SKIP = "skip"


class OmoTrailRecord(ZTimestampModel):
    """trail step 记录 (Round 12 P0 — 第 7 个 consumer).

    区别于 omo_audit / omo_event:
      - 强制 actor (谁做的) + duration_ms (耗时)
      - 支持 parent_step_id (嵌套调用图)
      - 细粒度 step-by-step, 适合"agent 走完几步完成任务"场景
    """

    ts: str
    actor: str = Field(..., min_length=1)
    action: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)
    status: OmoTrailStatus
    duration_ms: int = Field(default=0, ge=0)
    parent_step_id: str = ""  # 空串 = 顶层


# ── Consumer 8: omo_health ──────────────────────────────────


class OmoHealthLaunchdState(str, Enum):
    """launchd 守护进程状态 (Round 20 P0)."""

    RUNNING = "running"
    DOWN = "down"


class OmoHealthRecord(ZTimestampModel):
    """健康监控记录 (Round 20 P0 — 第 8 个 consumer).

    区别于 omo_history: dashboard_monitor 是健康监控点, 不参与治理评分.
    拆到独立 .jsonl (omo-health.jsonl), 治理历史不被健康监控污染.
    字段集: launchd 状态 + HTTP 探活 + PID + port + 时间戳.
    """

    source: str = Field(..., min_length=1)  # "dashboard_monitor"
    launchd_state: OmoHealthLaunchdState
    http_code: str = Field(..., min_length=1)  # "200" / "000" (down)
    pid: str = Field(..., min_length=1)  # "-" 当 down
    port: int = Field(..., ge=0, le=65535)
    timestamp: str


# ── 索引 (AppendOnlyLog.append 用 schema= 参数查) ────────────


SCHEMA_REGISTRY: dict[str, type[BaseModel]] = {
    "omo_audit": OmoAuditRecord,
    "omo_bos_metrics": OmoBosMetricsRecord,
    "omo_sync": OmoSyncRecord,
    "omo_alert": OmoAlertRecord,
    "omo_event": OmoEventRecord,
    "omo_history": OmoHistoryRecord,
    "omo_trail": OmoTrailRecord,  # Round 12 P0 — 第 7 个 consumer
    "omo_health": OmoHealthRecord,  # Round 20 P0 — 第 8 个 consumer (dashboard_monitor 拆出)
}


__all__ = (
    "BosStatus",
    "OmoAlertRecord",
    "OmoAlertSeverity",
    "OmoAuditRecord",
    "OmoBosMetricsRecord",
    "OmoEventRecord",
    "OmoHealthLaunchdState",
    "OmoHealthRecord",
    "OmoHistoryGrade",
    "OmoHistoryRecord",
    "OmoSyncRecord",
    "OmoSyncStatus",
    "OmoTrailRecord",
    "OmoTrailStatus",
    "SCHEMA_REGISTRY",
)
