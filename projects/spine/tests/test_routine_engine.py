"""Tests for RoutineEngine — 数字分身 Routine 自动受托托管引擎。"""

from __future__ import annotations

import pytest

from spine.orchestration.routine_engine import (
    CircuitBreakerTripped,
    ConfidenceBreakdown,
    RoutineCategory,
    RoutineEngine,
    RoutineStatus,
    RoutineTask,
)


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def engine() -> RoutineEngine:
    """默认引擎实例（阈值 0.95）。"""
    return RoutineEngine()


@pytest.fixture
def high_confidence_task() -> RoutineTask:
    """高置信度任务（通过熔断）。"""
    return RoutineTask(
        task_id="test-meeting-001",
        category=RoutineCategory.MEETING,
        payload={"rule_matched": True, "summary": "例行周会排期"},
    )


@pytest.fixture
def low_confidence_task() -> RoutineTask:
    """低置信度任务（触发熔断）。"""
    return RoutineTask(
        task_id="test-doc-001",
        category=RoutineCategory.DOC_REPLY,
        payload={"rule_matched": False, "content": "模糊公文内容..."},
    )


# ── ConfidenceBreakdown ──────────────────────────────────────────────────

class TestConfidenceBreakdown:
    def test_above_threshold(self):
        cb = ConfidenceBreakdown(0.97, 0.98, 0.99, 0.97)
        assert cb.is_above_threshold(0.95) is True

    def test_below_threshold(self):
        cb = ConfidenceBreakdown(0.90, 0.85, 0.80, 0.80)
        assert cb.is_above_threshold(0.95) is False

    def test_exact_threshold(self):
        cb = ConfidenceBreakdown(0.95, 0.95, 0.95, 0.95)
        assert cb.is_above_threshold(0.95) is True


# ── RoutineEngine: Submit & Circuit Breaker ──────────────────────────────

class TestRoutineEngineSubmit:
    def test_high_confidence_submits_successfully(self, engine, high_confidence_task):
        status = engine.submit(high_confidence_task)
        assert status == RoutineStatus.EXECUTING

    def test_low_confidence_triggers_circuit_breaker(self, engine, low_confidence_task):
        with pytest.raises(CircuitBreakerTripped) as exc_info:
            engine.submit(low_confidence_task)
        assert exc_info.value.confidence < 0.95
        assert exc_info.value.threshold == 0.95
        assert low_confidence_task.status == RoutineStatus.HITL


# ── RoutineEngine: Execute ────────────────────────────────────────────────

class TestRoutineEngineExecute:
    def test_execute_done(self, engine, high_confidence_task):
        engine.submit(high_confidence_task)
        result = engine.execute(high_confidence_task.task_id)
        assert result.status == RoutineStatus.DONE
        assert result.result is not None
        assert result.result["action"] == "auto_hosted"

    def test_execute_nonexistent_task_fails(self):
        engine = RoutineEngine()
        # 执行不存在的任务应失败
        with pytest.raises(KeyError, match="任务不存在"):
            engine.execute("nonexistent-task")


# ── RoutineEngine: Metrics ───────────────────────────────────────────────

class TestRoutineEngineMetrics:
    def test_initial_metrics(self, engine):
        metrics = engine.get_metrics()
        assert metrics["total_tasks"] == 0
        assert metrics["auto_rate"] == 0.0
        assert metrics["revision_rate"] == 0.0

    def test_metrics_after_execution(self, engine, high_confidence_task):
        engine.submit(high_confidence_task)
        engine.execute(high_confidence_task.task_id)
        metrics = engine.get_metrics()
        assert metrics["total_tasks"] == 1
        assert metrics["auto_done"] == 1
        assert metrics["auto_rate"] == 1.0
        assert metrics["revision_rate"] == 0.0

    def test_metrics_with_hitl(self, engine, low_confidence_task):
        try:
            engine.submit(low_confidence_task)
        except CircuitBreakerTripped:
            pass
        metrics = engine.get_metrics()
        assert metrics["hitl_fallback"] == 1
        assert metrics["revision_rate"] == 1.0


# ── RoutineEngine: State Machine ─────────────────────────────────────────

class TestStateMachine:
    def test_pending_to_executing(self, engine, high_confidence_task):
        assert high_confidence_task.status == RoutineStatus.PENDING
        engine.submit(high_confidence_task)
        assert high_confidence_task.status == RoutineStatus.EXECUTING

    def test_executing_to_done(self, engine, high_confidence_task):
        engine.submit(high_confidence_task)
        engine.execute(high_confidence_task.task_id)
        assert high_confidence_task.status == RoutineStatus.DONE

    def test_invalid_transition_raises(self, engine, high_confidence_task):
        engine.submit(high_confidence_task)
        engine.execute(high_confidence_task.task_id)
        # DONE → EXECUTING 是非法转换
        with pytest.raises(ValueError, match="无效状态转换"):
            high_confidence_task.transition(RoutineStatus.EXECUTING)

    def test_hitl_can_retry(self, engine, low_confidence_task):
        try:
            engine.submit(low_confidence_task)
        except CircuitBreakerTripped:
            pass
        assert low_confidence_task.status == RoutineStatus.HITL
        # HITL → PENDING 允许（重试）
        low_confidence_task.transition(RoutineStatus.PENDING)
        assert low_confidence_task.status == RoutineStatus.PENDING


# ── RoutineEngine: Batch Execution ───────────────────────────────────────

class TestBatchExecution:
    def test_execute_all_mixed_batch(self, engine):
        tasks = [
            RoutineTask(f"mtg-{i}", RoutineCategory.MEETING, {"rule_matched": True})
            for i in range(3)
        ] + [
            RoutineTask(f"doc-{i}", RoutineCategory.DOC_REPLY, {"rule_matched": False})
            for i in range(2)
        ]
        for t in tasks:
            engine._tasks[t.task_id] = t

        results = engine.execute_all()
        done = [r for r in results if r.status == RoutineStatus.DONE]
        hitl = [r for r in results if r.status == RoutineStatus.HITL]
        assert len(done) == 3
        assert len(hitl) == 2
