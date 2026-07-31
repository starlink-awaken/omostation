"""runtime executor I/O schemas — Pydantic models for AppendOnlyLog (§11 X1 审计契约).

R51 P0: engine.py 裸 open() → AppendOnlyLog.append() 迁移.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class ZTimestampModel(BaseModel):
    """Z-suffix ISO8601 时间戳校验 mixin — §11.2.3 / §12.1.3.

    所有 timestamp 字段必须以 Z 结尾 (UTC).
    """

    @model_validator(mode="after")
    def _check_z_timestamp(self) -> "ZTimestampModel":
        for field_name in ("ts", "timestamp", "recorded_at"):
            v = getattr(self, field_name, None)
            if v and not v.endswith("Z"):
                raise ValueError(f"{field_name}={v!r} must end with Z (UTC ISO8601)")
        return self


class ExecutorLogRecord(ZTimestampModel):
    """executor execution_log.jsonl 记录 schema — §11.2.3.

    engine.py _log_execution() 写入的每条记录.
    """

    ts: str = Field(
        ..., description="UTC ISO8601 with Z suffix, e.g. 2026-06-11T05:30:00Z"
    )
    task_id: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    summary: str
    turns: int = Field(default=0, ge=0)
    tokens_used: int = Field(default=0, ge=0)
    duration_sec: float = Field(default=0.0, ge=0)


SCHEMA_REGISTRY: dict[str, type[ZTimestampModel]] = {
    "executor_log": ExecutorLogRecord,
}
