"""
Tests for model_driven.ssot — SSOT 全生命周期化
"""

import pytest
from model_driven.ssot.lifecycle_ssot import (
    CrossStageConsistencyChecker,
    LifecycleSSOT,
    ProcessSSOT,
    SSOTSnapshot,
    ValueSSOT,
)
from model_driven.mof.m3_extended import LifecycleStage


class TestLifecycleSSOT:
    def test_record_and_get(self):
        ssot = LifecycleSSOT()
        snapshot = SSOTSnapshot(
            id="SNAP-1",
            entity_type="project",
            entity_id="proj-1",
            stage=LifecycleStage.PLANNING,
            data={"status": "active"},
        )
        ssot.record_snapshot(snapshot)
        state = ssot.get_current_state("proj-1")
        assert state == {"status": "active"}

    def test_get_history(self):
        ssot = LifecycleSSOT()
        snap1 = SSOTSnapshot(id="S-1", entity_id="proj-1", data={"v": 1})
        snap2 = SSOTSnapshot(id="S-2", entity_id="proj-1", data={"v": 2})
        ssot.record_snapshot(snap1)
        ssot.record_snapshot(snap2)
        history = ssot.get_history("proj-1")
        assert len(history) == 2

    def test_detect_drift(self):
        ssot = LifecycleSSOT()
        ssot.record_snapshot(SSOTSnapshot(id="S-1", entity_id="proj-1", data={"status": "active", "count": 5}))
        drifts = ssot.detect_drift("proj-1", {"status": "stopped", "count": 5})
        assert len(drifts) == 1
        assert drifts[0]["field"] == "status"

    def test_no_drift(self):
        ssot = LifecycleSSOT()
        ssot.record_snapshot(SSOTSnapshot(id="S-1", entity_id="proj-1", data={"status": "active"}))
        drifts = ssot.detect_drift("proj-1", {"status": "active"})
        assert len(drifts) == 0


class TestValueSSOT:
    def test_record_cost_and_benefit(self):
        ssot = ValueSSOT()
        ssot.record_cost("proj-1", {"amount": 1000, "type": "compute"})
        ssot.record_cost("proj-1", {"amount": 500, "type": "storage"})
        ssot.record_benefit("proj-1", {"amount": 3000, "type": "revenue"})

        assert ssot.get_total_cost("proj-1") == 1500
        assert ssot.get_total_benefit("proj-1") == 3000

    def test_calculate_roi(self):
        ssot = ValueSSOT()
        ssot.record_cost("proj-1", {"amount": 1000, "type": "compute"})
        ssot.record_benefit("proj-1", {"amount": 2000, "type": "revenue"})

        roi = ssot.calculate_roi("proj-1")
        assert roi["roi"] == 1.0  # (2000-1000)/1000
        assert roi["roi_pct"] == 100.0

    def test_zero_cost_roi(self):
        ssot = ValueSSOT()
        roi = ssot.calculate_roi("proj-1")
        assert roi["roi"] == 0.0


class TestProcessSSOT:
    def test_define_and_record(self):
        ssot = ProcessSSOT()
        ssot.define_process("PROC-1", {
            "name": "测试流程",
            "steps": [
                {"id": "step-1", "name": "步骤1"},
                {"id": "step-2", "name": "步骤2"},
                {"id": "step-3", "name": "步骤3"},
            ],
        })
        ssot.record_step_execution("PROC-1", "step-1", "completed")
        ssot.record_step_execution("PROC-1", "step-2", "completed")

        progress = ssot.get_process_progress("PROC-1")
        assert progress["total_steps"] == 3
        assert progress["completed_steps"] == 2


class TestCrossStageConsistencyChecker:
    def test_check_no_issues(self):
        checker = CrossStageConsistencyChecker()
        planning = [{"id": "OKR-1", "type": "okr"}]
        design = [{
            "id": "SPEC-1",
            "type": "spec_design",
            "properties": {"related_okrs": ["OKR-1"]},
        }]
        result = checker.check(planning, design, [], [], [])
        assert result["passed"]

    def test_check_missing_okr_link(self):
        checker = CrossStageConsistencyChecker()
        planning = [{"id": "OKR-1", "type": "okr"}]
        design = [{
            "id": "SPEC-1",
            "type": "spec_design",
            "properties": {},
        }]
        result = checker.check(planning, design, [], [], [])
        assert not result["passed"]
        assert result["total_issues"] >= 1

    def test_check_deploy_no_alert(self):
        checker = CrossStageConsistencyChecker()
        deploy = [{"id": "DEP-1", "type": "deployment_config"}]
        result = checker.check([], [], [], deploy, [])
        assert not result["passed"]
