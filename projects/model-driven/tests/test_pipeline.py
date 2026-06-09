"""
Tests for model_driven.lifecycle.pipeline — 三阶段宏观流水线
"""

from model_driven.lifecycle.pipeline import (
    STANDARD_PHASE_GATES,
    PhaseStatus,
    PipelinePhase,
    PipelineTracker,
)
from model_driven.mof.m3_extended import LifecycleStage


class TestPipelinePhase:
    def test_from_stage(self):
        assert PipelinePhase.from_stage(LifecycleStage.PLANNING) == PipelinePhase.COLD_START
        assert PipelinePhase.from_stage(LifecycleStage.DESIGN) == PipelinePhase.COLD_START
        assert PipelinePhase.from_stage(LifecycleStage.DEVELOPMENT) == PipelinePhase.EVOLUTION
        assert PipelinePhase.from_stage(LifecycleStage.DEPLOYMENT) == PipelinePhase.EVOLUTION
        assert PipelinePhase.from_stage(LifecycleStage.RUNTIME) == PipelinePhase.HARDENING
        assert PipelinePhase.from_stage(LifecycleStage.OPERATIONS) == PipelinePhase.HARDENING
        assert PipelinePhase.from_stage(LifecycleStage.BUSINESS_OPS) == PipelinePhase.HARDENING

    def test_get_stages(self):
        cold_start = PipelinePhase.get_stages(PipelinePhase.COLD_START)
        assert len(cold_start) == 2
        assert LifecycleStage.PLANNING in cold_start
        assert LifecycleStage.DESIGN in cold_start

        evolution = PipelinePhase.get_stages(PipelinePhase.EVOLUTION)
        assert len(evolution) == 2

        hardening = PipelinePhase.get_stages(PipelinePhase.HARDENING)
        assert len(hardening) == 3

    def test_enum_values(self):
        assert PipelinePhase.COLD_START.value == "cold_start"
        assert PipelinePhase.EVOLUTION.value == "evolution"
        assert PipelinePhase.HARDENING.value == "hardening"


class TestPipelineTracker:
    def test_init(self):
        tracker = PipelineTracker(entity_id="proj-1")
        assert tracker.entity_id == "proj-1"
        assert len(tracker.phases) == 3
        assert tracker.current_phase is None

    def test_start_cold_start(self):
        tracker = PipelineTracker(entity_id="proj-1")
        assert tracker.start_phase(PipelinePhase.COLD_START)
        assert tracker.current_phase == PipelinePhase.COLD_START
        assert tracker.phases[PipelinePhase.COLD_START].status == PhaseStatus.IN_PROGRESS

    def test_cannot_start_evolution_before_cold_start(self):
        tracker = PipelineTracker(entity_id="proj-1")
        assert not tracker.start_phase(PipelinePhase.EVOLUTION)
        assert tracker.current_phase is None

    def test_cannot_start_hardening_before_evolution(self):
        tracker = PipelineTracker(entity_id="proj-1")
        assert not tracker.start_phase(PipelinePhase.HARDENING)

    def test_complete_phase_after_stages(self):
        from model_driven.lifecycle.stages import StageStatus
        tracker = PipelineTracker(entity_id="proj-1")
        tracker.start_phase(PipelinePhase.COLD_START)

        for stage in PipelinePhase.get_stages(PipelinePhase.COLD_START):
            tracker.lifecycle_tracker.stages[stage].status = StageStatus.COMPLETED
            # 同时设置 completed_at 让 advance_to 可以通过
            tracker.lifecycle_tracker.stages[stage].completed_at = "2026-06-09T00:00:00Z"

        result = tracker.complete_phase(PipelinePhase.COLD_START)
        assert result, f"Phase status: {tracker.phases[PipelinePhase.COLD_START].status}"
        assert tracker.phases[PipelinePhase.COLD_START].status == PhaseStatus.COMPLETED

    def test_sequential_phases(self):
        from model_driven.lifecycle.stages import StageStatus
        tracker = PipelineTracker(entity_id="proj-1")

        # Phase 1: ColdStart
        assert tracker.start_phase(PipelinePhase.COLD_START)
        for stage in PipelinePhase.get_stages(PipelinePhase.COLD_START):
            tracker.lifecycle_tracker.stages[stage].status = StageStatus.COMPLETED
        assert tracker.complete_phase(PipelinePhase.COLD_START)

        # Phase 2: Evolution
        assert tracker.start_phase(PipelinePhase.EVOLUTION)
        for stage in PipelinePhase.get_stages(PipelinePhase.EVOLUTION):
            tracker.lifecycle_tracker.stages[stage].status = StageStatus.COMPLETED
        assert tracker.complete_phase(PipelinePhase.EVOLUTION)

        # Phase 3: Hardening
        assert tracker.start_phase(PipelinePhase.HARDENING)

    def test_complete_phase_requires_all_stages(self):
        tracker = PipelineTracker(entity_id="proj-1")
        tracker.start_phase(PipelinePhase.COLD_START)
        # 不完成所有 7 阶段，直接尝试完成 Phase
        assert not tracker.complete_phase(PipelinePhase.COLD_START)

    def test_complete_phase_with_completed_at(self):
        from model_driven.lifecycle.stages import StageStatus
        tracker = PipelineTracker(entity_id="proj-1")
        tracker.start_phase(PipelinePhase.COLD_START)

        for stage in PipelinePhase.get_stages(PipelinePhase.COLD_START):
            tracker.lifecycle_tracker.stages[stage].status = StageStatus.COMPLETED
            tracker.lifecycle_tracker.stages[stage].completed_at = "2026-01-01T00:00:00Z"

        result = tracker.complete_phase(PipelinePhase.COLD_START)
        assert result, f"Phase status: {tracker.phases[PipelinePhase.COLD_START].status}"
        assert tracker.phases[PipelinePhase.COLD_START].status == PhaseStatus.COMPLETED

    def test_advance_stage_in_phase(self):
        from model_driven.lifecycle.stages import StageStatus
        tracker = PipelineTracker(entity_id="proj-1")
        tracker.start_phase(PipelinePhase.COLD_START)

        # 当前应在第一个 7 阶段 (Planning)
        assert tracker.get_current_stage_in_phase() == LifecycleStage.PLANNING
        tracker.lifecycle_tracker.stages[LifecycleStage.PLANNING].status = StageStatus.COMPLETED

        # 推进到 Design
        assert tracker.advance_stage_in_phase()
        assert tracker.get_current_stage_in_phase() == LifecycleStage.DESIGN

    def test_get_progress(self):
        tracker = PipelineTracker(entity_id="proj-1")
        tracker.start_phase(PipelinePhase.COLD_START)

        progress = tracker.get_progress()
        assert progress["entity_id"] == "proj-1"
        assert progress["current_phase"] == "cold_start"
        assert "cold_start" in progress["phases"]
        assert "evolution" in progress["phases"]
        assert "hardening" in progress["phases"]

    def test_check_phase_gate(self):
        tracker = PipelineTracker(entity_id="proj-1")

        # 冷启动→演进: 需要满足条件
        context = {
            "OKR 已审批": True,
            "Spec 已批准": True,
            "关键 ADR 已记录": True,
            "接口契约已定义": True,
            "设计评审通过": True,
        }
        passed, msg = tracker.check_phase_gate(PipelinePhase.COLD_START, PipelinePhase.EVOLUTION, context)
        assert passed

        # 不满足条件
        failed_context = {}
        passed, msg = tracker.check_phase_gate(PipelinePhase.COLD_START, PipelinePhase.EVOLUTION, failed_context)
        assert not passed

    def test_standard_gates(self):
        assert len(STANDARD_PHASE_GATES) == 2
        assert STANDARD_PHASE_GATES[0].from_phase == PipelinePhase.COLD_START
        assert STANDARD_PHASE_GATES[0].to_phase == PipelinePhase.EVOLUTION
        assert STANDARD_PHASE_GATES[1].from_phase == PipelinePhase.EVOLUTION
        assert STANDARD_PHASE_GATES[1].to_phase == PipelinePhase.HARDENING
