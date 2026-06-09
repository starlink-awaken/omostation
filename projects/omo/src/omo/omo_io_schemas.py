"""AppendOnlyLog 6 个 consumer 的 Pydantic 模型 (Round 9 P0).

SSOT: 与 ``.omo/_knowledge/management/append-only-log-schemas-2026-06-09.md`` 一一对应.

设计:
  - 6 个 BaseModel, 必填字段 = 文档 required_fields
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

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ── 通用 validators ──────────────────────────────────────────


def _validate_z_suffix_iso8601(v: str) -> str:
    """校验 ISO8601 UTC 时间戳以 'Z' 结尾 (与 omo_audit._utc_now() 协议)."""
    if not v.endswith("Z"):
        raise ValueError(f"timestamp must end with 'Z' (omo_audit convention), got: {v!r}")
    try:
        datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid ISO8601 timestamp: {v!r} ({exc})")
    return v


# 已知时间戳字段名 (按 SSOT, 不同 consumer 用不同名)
_TIMESTAMP_FIELDS = ("ts", "recorded_at", "timestamp")


class ZTimestampModel(BaseModel):
    """AppendOnlyLog 6 个 consumer 共享的 Z-suffix ISO8601 校验基类 (Round 11 /simplify).

    自动 model_validator 扫描已知时间戳字段名, 校验 Z 结尾 + ISO8601 格式.
    子类只需定义字段 (ts: str 或 recorded_at: str 等), 无需重写 @field_validator.
    """

    @model_validator(mode="after")
    def _check_all_timestamps(self) -> "ZTimestampModel":
        for field_name in _TIMESTAMP_FIELDS:
            v = getattr(self, field_name, None)
            if v is not None and isinstance(v, str):
                _validate_z_suffix_iso8601(v)
        return self


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


# ── 索引 (AppendOnlyLog.append 用 schema= 参数查) ────────────


SCHEMA_REGISTRY: dict[str, type[BaseModel]] = {
    "omo_audit": OmoAuditRecord,
    "omo_bos_metrics": OmoBosMetricsRecord,
    "omo_sync": OmoSyncRecord,
    "omo_alert": OmoAlertRecord,
    "omo_event": OmoEventRecord,
    "omo_history": OmoHistoryRecord,
}


__all__ = (
    "BosStatus",
    "OmoAlertRecord",
    "OmoAlertSeverity",
    "OmoAuditRecord",
    "OmoBosMetricsRecord",
    "OmoEventRecord",
    "OmoHistoryGrade",
    "OmoHistoryRecord",
    "OmoSyncRecord",
    "OmoSyncStatus",
    "SCHEMA_REGISTRY",
)
