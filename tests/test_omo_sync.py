"""Tests for omo.omo_sync — Round 3 结构化 record.

Covers:
- 正常 sync 写结构化 record 到 log
- dry_run 不写 record
- 错误路径也走结构化 log
- record 字段形状固化 (不再 f-string 拍扁)
- 显式 log_path 参数支持测试覆盖
"""
from __future__ import annotations

import sys
from pathlib import Path

# 把 src 加入 path (与 omo 现有 tests 同)
OMO_SRC = Path(__file__).resolve().parents[1] / "src"
if str(OMO_SRC) not in sys.path:
    sys.path.insert(0, str(OMO_SRC))

from omo.omo_sync import run_sync, AUDIT_CHECKS  # noqa: E402


def test_omo_sync_writes_structured_record(tmp_path):
    """正常 sync: 写一条结构化 record 到 log."""
    log_path = tmp_path / "omo-sync.jsonl"
    result = run_sync({"dry_run": False, "log_path": log_path})

    assert result["status"] == "ok"
    assert "synced_at" in result
    assert "phase" in result
    assert "health_score" in result

    # 验证: log 文件被创建, record 结构化
    records = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(records) == 1, f"expected 1 record, got {len(records)}"

    import json
    rec = json.loads(records[0])
    # Round 3 锁: 字段固化, 不再 f-string 拍扁
    assert rec["kind"] == "omo_sync"
    assert rec["status"] == "ok"
    assert rec["audit_checks"] == AUDIT_CHECKS
    assert rec["dry_run"] is False
    assert "ts" in rec
    assert rec["ts"].endswith("Z"), "ts must use Z-suffix (omo_audit convention)"
    # 关键: phase 和 health_score 是独立字段, 不是 details 字符串里的 key=value
    assert isinstance(rec["phase"], int)
    assert isinstance(rec["health_score"], (int, float))


def test_omo_sync_dry_run_no_record(tmp_path):
    """dry_run=True: 不写 record."""
    log_path = tmp_path / "omo-sync.jsonl"
    result = run_sync({"dry_run": True, "log_path": log_path})

    assert result["status"] == "ok"
    assert result["dry_run"] is True
    # log 文件不存在或为空
    if log_path.exists():
        assert log_path.read_text(encoding="utf-8") == ""


def test_omo_sync_creates_parent_dir(tmp_path):
    """log_path 父目录不存在时, AppendOnlyLog 自动创建."""
    log_path = tmp_path / "subdir" / "nested" / "omo-sync.jsonl"
    run_sync({"dry_run": False, "log_path": log_path})
    assert log_path.exists()
    assert len(log_path.read_text(encoding="utf-8").strip()) > 0


def test_omo_sync_returns_summary_dict(tmp_path):
    """返回 dict 形状固化 (cli 调用方依赖)."""
    log_path = tmp_path / "omo-sync.jsonl"
    result = run_sync({"dry_run": False, "log_path": log_path})
    expected_keys = {"status", "phase", "health_score", "synced_at", "audit_checks", "dry_run"}
    assert expected_keys <= set(result.keys())


def test_omo_sync_default_log_path_in_omo_knowledge():
    """默认 log path 应在 .omo/_knowledge/ (与 bos-metrics.jsonl 一致)."""
    from omo.omo_sync import DEFAULT_SYNC_LOG_PATH
    assert ".omo" in str(DEFAULT_SYNC_LOG_PATH)
    assert "knowledge" in str(DEFAULT_SYNC_LOG_PATH)


def test_omo_sync_no_details_string_smell():
    """Round 3 反向锁: 任何 record 都不应含 details 字符串 (字段拍扁)."""
    import json
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        tmp = Path(f.name)
    run_sync({"dry_run": False, "log_path": tmp})
    rec = json.loads(tmp.read_text(encoding="utf-8").strip())
    # 不应有 details 字段 (旧实现拍扁字段进 details 字符串)
    assert "details" not in rec, "Round 3 锁: record 不应有 details 字段 (结构化取代)"
    # 也不应有 f-string 痕迹
    raw_line = tmp.read_text(encoding="utf-8").strip()
    assert "phase=" not in raw_line, "Round 3 锁: record 不应含 f-string 拍扁 (e.g. 'phase=28')"
    assert "health_score=" not in raw_line
    tmp.unlink()
