"""
Tests for model_driven.lifecycle — 全生命周期引擎
"""

import pytest
from model_driven.lifecycle.stages import LifecycleTracker, StageInstance, StageStatus
from model_driven.lifecycle.gates import GateEngine, GateResult, CheckResult
from model_driven.lifecycle.transitions import TransitionEngine, STANDARD_TRANSITIONS
from model_driven.lifecycle.tracking import LifecycleManager
from model_driven.mof.m3_extended import LifecycleStage


class TestStageInstance:
    def test_initial_status(self):
        instance = StageInstance(id="test-1", entity_id="entity-1", stage=LifecycleStage.PLANNING)
        assert instance.status == StageStatus.NOT_STARTED

    def test_start(self):
        instance = StageInstance(id="test-1", entity_id="entity-1", stage=LifecycleStage.PLANNING)
        instance.start()
        assert instance.status == StageStatus.IN_PROGRESS
        assert instance.started_at != ""

    def test_complete(self):
        instance = StageInstance(id="test-1", entity_id="entity-1", stage=LifecycleStage.PLANNING)
        instance.start()
        instance.complete()
        assert instance.status == StageStatus.COMPLETED
        assert instance.completed_at != ""

    def test_block_unblock(self):
        instance = StageInstance(id="test-1", entity_id="entity-1", stage=LifecycleStage.PLANNING)
        instance.start()
        instance.block("测试阻塞原因")
        assert instance.status == StageStatus.BLOCKED
        assert "测试阻塞原因" in instance.issues
        instance.unblock()
        assert instance.status == StageStatus.IN_PROGRESS


class TestLifecycleTracker:
    def test_initialization(self):
        tracker = LifecycleTracker(entity_id="proj-1")
        assert len(tracker.stages) == 7
        for stage in LifecycleStage:
            assert stage in tracker.stages
            assert tracker.stages[stage].status == StageStatus.NOT_STARTED

    def test_advance_to_first_stage(self):
        tracker = LifecycleTracker(entity_id="proj-1")
        assert tracker.advance_to(LifecycleStage.PLANNING)
        assert tracker.current_stage == LifecycleStage.PLANNING
        assert tracker.stages[LifecycleStage.PLANNING].status == StageStatus.IN_PROGRESS

    def test_advance_blocked_by_prerequisite(self):
        tracker = LifecycleTracker(entity_id="proj-1")
        # 尝试跳过规划直接到开发
        assert not tracker.advance_to(LifecycleStage.DEVELOPMENT)
        assert tracker.current_stage is None

    def test_sequential_advance(self):
        tracker = LifecycleTracker(entity_id="proj-1")
        assert tracker.advance_to(LifecycleStage.PLANNING)
        tracker.complete_current()
        assert tracker.advance_to(LifecycleStage.DESIGN)
        tracker.complete_current()
        assert tracker.advance_to(LifecycleStage.DEVELOPMENT)
        assert tracker.current_stage == LifecycleStage.DEVELOPMENT

    def test_get_progress(self):
        tracker = LifecycleTracker(entity_id="proj-1")
        tracker.advance_to(LifecycleStage.PLANNING)
        tracker.complete_current()
        progress = tracker.get_progress()
        assert progress["completed_stages"] == 1
        assert progress["total_stages"] == 7

    def test_transitions_history(self):
        tracker = LifecycleTracker(entity_id="proj-1")
        tracker.advance_to(LifecycleStage.PLANNING)
        tracker.complete_current()
        tracker.advance_to(LifecycleStage.DESIGN)
        assert len(tracker.transitions) == 2


class TestGateEngine:
    def test_get_gate(self):
        engine = GateEngine()
        gate = engine.get_gate(LifecycleStage.PLANNING, LifecycleStage.DESIGN)
        assert gate is not None
        assert gate.id == "GATE-PLAN-TO-DESIGN"

    def test_no_gate_for_invalid_transition(self):
        engine = GateEngine()
        gate = engine.get_gate(LifecycleStage.PLANNING, LifecycleStage.RUNTIME)
        assert gate is None

    def test_check_gate_with_all_passed(self):
        engine = GateEngine()
        gate = engine.get_gate(LifecycleStage.PLANNING, LifecycleStage.DESIGN)
        assert gate is not None

        context = {
            "approvals": {"OKR 审批": True},
            "documents": {"Spec 草案完成": True, "关键 ADR 记录": True},
        }
        execution = engine.check_gate(gate, context)
        assert execution.result == GateResult.PASSED

    def test_check_gate_with_failures(self):
        engine = GateEngine()
        gate = engine.get_gate(LifecycleStage.DESIGN, LifecycleStage.DEVELOPMENT)
        assert gate is not None

        context = {"approvals": {}, "documents": {}, "reviews": {}}
        execution = engine.check_gate(gate, context)
        assert execution.result == GateResult.FAILED

    def test_auto_pass_gate(self):
        engine = GateEngine()
        gate = engine.get_gate(LifecycleStage.DEPLOYMENT, LifecycleStage.RUNTIME)
        assert gate is not None
        execution = engine.check_gate(gate)
        assert execution.result == GateResult.PASSED
        assert execution.notes == "自动通过"

    def test_custom_check(self):
        engine = GateEngine()

        def custom_check(check, context):
            return True, "自定义检查通过"

        engine.register_check("custom_type", custom_check)
        # 验证注册成功
        assert "custom_type" in engine._custom_checks

    def test_metric_check(self):
        engine = GateEngine()
        gate = engine.get_gate(LifecycleStage.DEVELOPMENT, LifecycleStage.DEPLOYMENT)
        assert gate is not None

        context = {
            "metrics": {"测试通过率 >= 95%": 98.0},
            "reviews": {"Code Review 通过": True},
            "ci_status": "success",
        }
        execution = engine.check_gate(gate, context)
        assert execution.result == GateResult.PASSED


class TestTransitionEngine:
    def test_allowed_transitions(self):
        engine = TransitionEngine()
        allowed = engine.get_allowed_transitions(LifecycleStage.PLANNING)
        assert LifecycleStage.DESIGN in allowed

    def test_invalid_transition(self):
        engine = TransitionEngine()
        rule = engine.get_transition_rule(LifecycleStage.PLANNING, LifecycleStage.DEPLOYMENT)
        assert rule is None

    def test_valid_path(self):
        engine = TransitionEngine()
        path = [
            LifecycleStage.PLANNING,
            LifecycleStage.DESIGN,
            LifecycleStage.DEVELOPMENT,
            LifecycleStage.DEPLOYMENT,
            LifecycleStage.RUNTIME,
        ]
        assert engine.is_valid_path(path)

    def test_invalid_path(self):
        engine = TransitionEngine()
        path = [LifecycleStage.PLANNING, LifecycleStage.DEVELOPMENT]  # 跳过设计
        assert not engine.is_valid_path(path)

    def test_standard_transitions_count(self):
        assert len(STANDARD_TRANSITIONS) == 6

    def test_try_transition_success(self):
        engine = TransitionEngine()
        tracker = LifecycleTracker(entity_id="proj-1")
        tracker.advance_to(LifecycleStage.PLANNING)
        tracker.complete_current()

        context = {
            "approvals": {"OKR 审批": True},
            "documents": {"Spec 草案完成": True, "关键 ADR 记录": True},
        }
        success, msg, gate_exec = engine.try_transition(tracker, LifecycleStage.DESIGN, context)
        assert success
        assert tracker.current_stage == LifecycleStage.DESIGN

    def test_try_transition_fail_gate(self):
        engine = TransitionEngine()
        tracker = LifecycleTracker(entity_id="proj-1")
        tracker.advance_to(LifecycleStage.PLANNING)
        tracker.complete_current()

        context = {}  # 空上下文，所有检查都会失败
        success, msg, gate_exec = engine.try_transition(tracker, LifecycleStage.DESIGN, context)
        assert not success
        assert "门禁检查未通过" in msg


class TestLifecycleManager:
    def test_create_tracker(self):
        manager = LifecycleManager()
        tracker = manager.create_tracker("proj-1", "project")
        assert tracker.entity_id == "proj-1"
        assert tracker.entity_type == "project"

    def test_list_entities(self):
        manager = LifecycleManager()
        manager.create_tracker("proj-1")
        manager.create_tracker("proj-2")
        assert set(manager.list_entities()) == {"proj-1", "proj-2"}

    def test_generate_dashboard(self):
        manager = LifecycleManager()
        tracker = manager.create_tracker("proj-1")
        tracker.advance_to(LifecycleStage.PLANNING)
        tracker.complete_current()

        dashboard = manager.generate_dashboard()
        assert dashboard.total_entities == 1
        assert dashboard.avg_progress > 0

    def test_get_all_blockers(self):
        manager = LifecycleManager()
        tracker = manager.create_tracker("proj-1")
        tracker.advance_to(LifecycleStage.PLANNING)
        tracker.stages[LifecycleStage.PLANNING].block("缺少审批")
        blockers = manager.get_all_blockers()
        assert len(blockers) == 1
        assert blockers[0]["issue"] == "缺少审批"

    def test_get_stage_summary(self):
        manager = LifecycleManager()
        manager.create_tracker("proj-1")
        summary = manager.get_stage_summary("proj-1")
        assert summary is not None
        assert summary["entity_id"] == "proj-1"

    def test_remove_tracker(self):
        manager = LifecycleManager()
        manager.create_tracker("proj-1")
        assert manager.remove_tracker("proj-1")
        assert manager.get_tracker("proj-1") is None
        assert not manager.remove_tracker("nonexistent")
