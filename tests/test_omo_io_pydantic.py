"""Tests for AppendOnlyLog Pydantic 写时校验 (Round 9 P1)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

OMO_SRC = Path(__file__).resolve().parents[1] / "src"
if str(OMO_SRC) not in sys.path:
    sys.path.insert(0, str(OMO_SRC))


def test_append_with_schema_valid_record(tmp_path):
    """传 schema + 合法 record → 正常写入, 文件含 1 条."""
    from omo.omo_io import AppendOnlyLog
    from omo.omo_io_schemas import OmoBosMetricsRecord

    log = AppendOnlyLog(tmp_path / "test.jsonl")
    log.append(
        {
            "uri": "bos://memory/kos/search",
            "status": "resolved",
            "elapsed_ms": 12.3,
            "transport": "stdio",
            "error": "",
            "recorded_at": "2026-06-09T02:00:00Z",
        },
        schema=OmoBosMetricsRecord,
    )
    lines = log.path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1


def test_append_with_schema_invalid_record_raises(tmp_path):
    """传 schema + 非法 record → 抛 ValidationError, 不写入."""
    from pydantic import ValidationError

    from omo.omo_io import AppendOnlyLog
    from omo.omo_io_schemas import OmoBosMetricsRecord

    log = AppendOnlyLog(tmp_path / "test.jsonl")
    # elapsed_ms 必填, status 必填
    with pytest.raises(ValidationError) as exc_info:
        log.append(
            {"uri": "bos://x/y/z", "status": "resolved"},  # 缺 elapsed_ms
            schema=OmoBosMetricsRecord,
        )
    # 验证错误信息提到 elapsed_ms
    assert "elapsed_ms" in str(exc_info.value)
    # 文件未被写入
    assert not log.path.exists()


def test_append_with_schema_invalid_status_enum_raises(tmp_path):
    """status 字段非法值 → 校验失败 (BosStatus Enum)."""
    from pydantic import ValidationError

    from omo.omo_io import AppendOnlyLog
    from omo.omo_io_schemas import OmoBosMetricsRecord

    log = AppendOnlyLog(tmp_path / "test.jsonl")
    with pytest.raises(ValidationError):
        log.append(
            {
                "uri": "bos://x/y/z",
                "status": "invalid_status_xyz",  # 不在 Enum 中
                "elapsed_ms": 1.0,
                "recorded_at": "2026-06-09T02:00:00Z",
            },
            schema=OmoBosMetricsRecord,
        )


def test_append_with_schema_z_suffix_violation_raises(tmp_path):
    """timestamp 不以 'Z' 结尾 → 校验失败 (Round 8 P2 锁)."""
    from pydantic import ValidationError

    from omo.omo_io import AppendOnlyLog
    from omo.omo_io_schemas import OmoAuditRecord

    log = AppendOnlyLog(tmp_path / "test.jsonl")
    with pytest.raises(ValidationError) as exc_info:
        log.append(
            {
                "ts": "2026-06-09T02:00:00+00:00",  # +00:00 而非 Z
                "action": "test",
                "actor": "pytest",
            },
            schema=OmoAuditRecord,
        )
    assert "Z" in str(exc_info.value) or "endswith" in str(exc_info.value).lower()


def test_append_without_schema_unchanged_behavior(tmp_path):
    """不传 schema = 旧行为不变 (0 破坏)."""
    from omo.omo_io import AppendOnlyLog

    log = AppendOnlyLog(tmp_path / "test.jsonl")
    # 故意写一个"非法" record (无 schema 校验)
    log.append({"anything": "goes", "no": "validation"})
    assert log.path.exists()
    assert len(log.read_all()) == 1


def test_append_with_pydantic_instance_auto_dump(tmp_path):
    """传 Pydantic BaseModel 实例 → 自动 model_dump."""
    from omo.omo_io import AppendOnlyLog
    from omo.omo_io_schemas import OmoBosMetricsRecord

    log = AppendOnlyLog(tmp_path / "test.jsonl")
    rec = OmoBosMetricsRecord(
        uri="bos://test",
        status="resolved",
        elapsed_ms=1.0,
        recorded_at="2026-06-09T02:00:00Z",
    )
    log.append(rec)  # 不传 schema, 走自动 model_dump
    # 验证写入成功
    raw = log.read_all()
    assert len(raw) == 1
    assert raw[0]["uri"] == "bos://test"
    # enum 已被 dump 为字符串值 (Pydantic v2 默认)
    assert raw[0]["status"] == "resolved" or raw[0]["status"] == BosStatus.RESOLVED


def test_append_with_pydantic_instance_and_schema(tmp_path):
    """传 Pydantic 实例 + schema → 跳过 model_validate (实例已 valid)."""
    from omo.omo_io import AppendOnlyLog
    from omo.omo_io_schemas import OmoBosMetricsRecord, BosStatus

    log = AppendOnlyLog(tmp_path / "test.jsonl")
    rec = OmoBosMetricsRecord(
        uri="bos://test",
        status=BosStatus.RESOLVED,
        elapsed_ms=1.0,
        recorded_at="2026-06-09T02:00:00Z",
    )
    log.append(rec, schema=OmoBosMetricsRecord)  # 双重保险
    assert len(log.read_all()) == 1


def test_append_with_invalid_instance_raises_via_schema(tmp_path):
    """传 Pydantic 实例 (但 schema 不符) → ValidationError."""
    # 这场景实际不会发生 (Pydantic 实例创建时已 valid), 但锁住 fail-fast
    from pydantic import ValidationError

    from omo.omo_io import AppendOnlyLog
    from omo.omo_io_schemas import OmoAuditRecord, OmoBosMetricsRecord

    log = AppendOnlyLog(tmp_path / "test.jsonl")
    rec = OmoAuditRecord(
        ts="2026-06-09T02:00:00Z",
        action="test",
        actor="pytest",
    )
    # 用错 schema (OmoBosMetricsRecord 不接受 OmoAuditRecord 字段)
    with pytest.raises(ValidationError):
        log.append(rec, schema=OmoBosMetricsRecord)
