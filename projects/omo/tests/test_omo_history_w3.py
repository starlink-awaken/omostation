"""Tests for omo.omo_history — Round 7 P2 (AppendOnlyLog 第 6 个 consumer)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

OMO_SRC = Path(__file__).resolve().parents[1] / "src"
if str(OMO_SRC) not in sys.path:
    sys.path.insert(0, str(OMO_SRC))


def test_append_entry_uses_append_only_log(tmp_path):
    """append_entry 应写 1 条 record 到 log, 含 date/timestamp 自动注入."""
    from omo.omo_history import append_entry

    log_path = tmp_path / "history.jsonl"
    result = append_entry(
        {"total_score": 99.0, "grade": "A+", "source": "pytest"},
        path=log_path,
    )
    assert result == log_path

    # 验证: log 文件 1 条结构化 record
    records = [json.loads(l) for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(records) == 1
    rec = records[0]
    assert rec["total_score"] == 99.0
    assert rec["grade"] == "A+"
    assert rec["source"] == "pytest"
    assert "date" in rec  # 自动注入
    assert "timestamp" in rec


def test_append_entry_preserves_sort_keys_compatibility(tmp_path):
    """Round 7 P2 锁: 与 kairon-governance 旧 JSONL 字节级兼容 (sort_keys=True)."""
    from omo.omo_history import append_entry

    log_path = tmp_path / "history.jsonl"
    append_entry(
        {"z_field": "z", "a_field": "a", "m_field": "m"},
        path=log_path,
    )
    # 读行 — sort_keys=True 让所有 key 字母序 (a_field, date, m_field, timestamp, z_field)
    raw_line = log_path.read_text(encoding="utf-8").strip()
    parsed = json.loads(raw_line, object_pairs_hook=list)
    keys = [k for k, _ in parsed]
    # 5 个 key 全字母序: a_field, date, m_field, timestamp, z_field
    assert keys == ["a_field", "date", "m_field", "timestamp", "z_field"], (
        f"keys must be globally sorted (sort_keys=True), got: {keys}"
    )


def test_append_entry_overrides_user_date_timestamp(tmp_path):
    """date / timestamp 由本函数注入, 用户传入的会被覆盖 (Round 7 P2 行为不变)."""
    from omo.omo_history import append_entry

    log_path = tmp_path / "history.jsonl"
    append_entry(
        {"date": "user-attempt-1900-01-01", "timestamp": "user-bad-ts"},
        path=log_path,
    )
    records = [json.loads(l) for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert records[0]["date"] != "user-attempt-1900-01-01"
    assert records[0]["timestamp"] != "user-bad-ts"
    # 注入的 date 应是今天
    from datetime import date
    assert records[0]["date"] == date.today().isoformat()


def test_append_entry_creates_parent_dir(tmp_path):
    """AppendOnlyLog 自动创父目录 — append_entry 继承该能力."""
    from omo.omo_history import append_entry

    log_path = tmp_path / "subdir" / "nested" / "history.jsonl"
    append_entry({"x": 1}, path=log_path)
    assert log_path.exists()


def test_append_entry_via_append_only_log_class(tmp_path):
    """验证 append_entry 内部用 AppendOnlyLog (通过类属性推断)."""
    from omo.omo_history import append_entry
    from omo.omo_io import AppendOnlyLog

    # 间接验证: append_entry 走 AppendOnlyLog.append, 故 sort_keys=True 通过 kwargs 传入
    log_path = tmp_path / "trace.jsonl"
    append_entry({"b": 2, "a": 1}, path=log_path)
    raw = log_path.read_text(encoding="utf-8").strip()
    # sort_keys 验证: "a" 应在 "b" 之前
    assert raw.index('"a"') < raw.index('"b"')

    # 也直接用 AppendOnlyLog 写, 应该兼容
    AppendOnlyLog(log_path).append({"x": 1}, sort_keys=True)
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    # 第 2 行用 sort_keys
    parsed2 = json.loads(lines[1], object_pairs_hook=list)
    assert [k for k, _ in parsed2] == ["x"]  # 单字段无所谓
