"""Tests for omo.model_driven_bridge (Round 5 P2)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

OMO_SRC = Path(__file__).resolve().parents[1] / "src"
if str(OMO_SRC) not in sys.path:
    sys.path.insert(0, str(OMO_SRC))


def test_make_pipeline_event_logger_creates_append_only_log(tmp_path):
    """make_pipeline_event_logger 应返回 AppendOnlyLog 实例."""
    from omo.model_driven_bridge import make_pipeline_event_logger
    from omo.omo_io import AppendOnlyLog

    log = make_pipeline_event_logger(tmp_path / "test.jsonl")
    assert isinstance(log, AppendOnlyLog)


def test_make_pipeline_tracker_with_log_writes_events(tmp_path):
    """make_pipeline_tracker_with_log: 创建 tracker, start_phase 应写 log."""
    from omo.model_driven_bridge import make_pipeline_tracker_with_log
    from model_driven.lifecycle.pipeline import PipelinePhase

    log_path = tmp_path / "pipeline-events.jsonl"
    tracker = make_pipeline_tracker_with_log(
        entity_id="test-domain",
        log_path=log_path,
    )
    # 触发 start_phase → 应写 1 条 event
    tracker.start_phase(PipelinePhase.COLD_START)

    # 验证 log 文件包含 1 条 event
    assert log_path.exists()
    lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1

    import json
    event = json.loads(lines[0])
    assert event["action"] == "start_phase"
    assert event["phase"] == "cold_start"
    assert "timestamp" in event


def test_wire_pipeline_tracker_attaches_to_existing(tmp_path):
    """wire_pipeline_tracker: 给已有 tracker 挂 on_event 钩子."""
    from omo.model_driven_bridge import wire_pipeline_tracker
    from model_driven.lifecycle.pipeline import PipelineTracker, PipelinePhase

    log_path = tmp_path / "wired.jsonl"
    tracker = PipelineTracker(entity_id="x")  # 无 on_event
    # 初始: 钩子不存在
    assert tracker._on_event is None

    # 挂上
    wire_pipeline_tracker(tracker, log_path=log_path)
    assert tracker._on_event is not None

    # 触发 → 写 log
    tracker.start_phase(PipelinePhase.COLD_START)
    lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1


def test_bridge_event_hook_failure_doesnt_break_main(tmp_path, monkeypatch):
    """on_event 抛异常不应中断主流程 (兜底 try/except)."""
    from omo.model_driven_bridge import make_pipeline_event_logger
    from model_driven.lifecycle.pipeline import PipelineTracker, PipelinePhase

    log_path = tmp_path / "failing.jsonl"
    log = make_pipeline_event_logger(log_path)

    def broken_hook(event: dict) -> None:
        raise RuntimeError("disk full")

    # 挂一个会抛异常的钩子
    tracker = PipelineTracker(entity_id="x", on_event=broken_hook)
    # 主流程 start_phase 不应被 broken_hook 拖死
    result = tracker.start_phase(PipelinePhase.COLD_START)
    assert result is True  # 主流程成功
    # 但 log 里应该有 1 条 (因为 AppendOnlyLog.append 在 try/except 内)


def test_bridge_returns_chainable_tracker(tmp_path):
    """make_pipeline_tracker_with_log 返回可链式调用."""
    from omo.model_driven_bridge import make_pipeline_tracker_with_log

    tracker = make_pipeline_tracker_with_log(entity_id="chain-test", log_path=tmp_path / "x.jsonl")
    assert tracker.entity_id == "chain-test"
    assert tracker._on_event is not None
