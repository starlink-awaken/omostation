"""ZTimestampModel — §12 跨仓 Z-suffix 校验 SSOT (Round 25 P0).

原位置: omo_io_schemas.py (Round 8 P2 + Round 11 /simplify 收口)
当前位置: omo._shared.z_timestamp_model (§12 跨仓契约配套)

§12.1.3 不变量 (Z-suffix ISO8601 时间戳):
  - 每个 schema 至少 1 个 timestamp 字段 (ts / recorded_at / timestamp)
  - timestamp 字段必须以 'Z' 结尾 + ISO8601 格式合法
  - ZTimestampModel 自动 model_validator 扫描已知 timestamp 字段名, 校验
  - 子类无需重写 @field_validator — 继承 ZTimestampModel 即得 Z 校验

§12 跨仓示例 (Python):
  from omo._shared.z_timestamp_model import ZTimestampModel
  from pydantic import Field

  class TargetEventRecord(ZTimestampModel):
      ts: str  # 自动校验 Z-suffix
      actor: str = Field(..., min_length=1)

跨语言等价物 (§12.2.2 TypeScript):
  const ZTimestamp = z.string().regex(/Z$/, "must end with Z");
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, model_validator


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
TIMESTAMP_FIELDS = ("ts", "recorded_at", "timestamp")


class ZTimestampModel(BaseModel):
    """AppendOnlyLog 7 个 consumer 共享的 Z-suffix ISO8601 校验基类 (Round 11 /simplify).

    自动 model_validator 扫描已知时间戳字段名, 校验 Z 结尾 + ISO8601 格式.
    子类只需定义字段 (ts: str 或 recorded_at: str 等), 无需重写 @field_validator.

    §12.1.3 跨仓不变量: 任何仓 Pydantic schema 继承本类即得 Z 校验.
    """

    @model_validator(mode="after")
    def _check_all_timestamps(self) -> "ZTimestampModel":
        for field_name in TIMESTAMP_FIELDS:
            v = getattr(self, field_name, None)
            if v is not None and isinstance(v, str):
                _validate_z_suffix_iso8601(v)
        return self


__all__ = (
    "ZTimestampModel",
    "TIMESTAMP_FIELDS",
    "_validate_z_suffix_iso8601",
)
