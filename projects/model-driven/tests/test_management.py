"""
Tests for model_driven.management — 管理面
"""

import pytest
from model_driven.management.spec import Spec, SpecManager, SpecStatus
from model_driven.management.adr import ADR, ADRManager, ADRStatus
from model_driven.management.okr import OKR, OKRManager, OKRStatus
from model_driven.management.omo_bridge import OMOBridge, OMOEventType
from model_driven.management.agent_collab import AgentCollabManager, CollabTaskStatus
from model_driven.mof.m3_extended import KeyResult


class TestSpec:
    def test_lifecycle(self):
        spec = Spec(id="S-1", title="测试Spec")
        assert spec.status == SpecStatus.DRAFT

        assert spec.submit_for_review()
        assert spec.status == SpecStatus.REVIEW

        assert spec.approve()
        assert spec.status == SpecStatus.APPROVED

        assert spec.start_implementation()
        assert spec.status == SpecStatus.IMPLEMENTING

        assert spec.mark_done()
        assert spec.status == SpecStatus.DONE

        assert spec.archive()
        assert spec.status == SpecStatus.ARCHIVED

    def test_invalid_transitions(self):
        spec = Spec(id="S-1", title="测试")
        assert not spec.approve()  # 不能直接从 draft 批准
        assert not spec.start_implementation()  # 不能直接从 draft 开始实现

    def test_amend(self):
        spec = Spec(id="S-1", title="测试", status=SpecStatus.APPROVED)
        assert spec.amend()
        assert spec.status == SpecStatus.AMENDED


class TestSpecManager:
    def test_create_and_get(self):
        manager = SpecManager()
        manager.create("S-1", "测试")
        spec = manager.get("S-1")
        assert spec is not None
        assert spec.title == "测试"

    def test_list_by_status(self):
        manager = SpecManager()
        manager.create("S-1", "测试1")
        s2 = manager.create("S-2", "测试2")
        s2.submit_for_review()
        drafts = manager.list_by_status(SpecStatus.DRAFT)
        assert len(drafts) == 1

    def test_link_adr(self):
        manager = SpecManager()
        manager.create("S-1", "测试")
        assert manager.link_adr("S-1", "ADR-1")
        spec = manager.get("S-1")
        assert "ADR-1" in spec.related_adrs

    def test_stats(self):
        manager = SpecManager()
        manager.create("S-1", "测试1")
        manager.create("S-2", "测试2")
        stats = manager.get_stats()
        assert stats["total"] == 2


class TestADR:
    def test_lifecycle(self):
        adr = ADR(id="ADR-1", title="测试ADR", context="背景", decision="决策", consequences="后果")
        assert adr.status == ADRStatus.PROPOSED

        assert adr.accept()
        assert adr.status == ADRStatus.ACCEPTED

    def test_reject(self):
        adr = ADR(id="ADR-1", title="测试")
        assert adr.reject()
        assert adr.status == ADRStatus.REJECTED

    def test_supersede(self):
        adr = ADR(id="ADR-1", title="测试", status=ADRStatus.ACCEPTED)
        assert adr.supersede("ADR-2")
        assert adr.status == ADRStatus.SUPERSEDED
        assert adr.superseded_by == "ADR-2"


class TestADRManager:
    def test_create(self):
        manager = ADRManager()
        manager.create("ADR-1", "测试")
        assert manager.get("ADR-1") is not None

    def test_find_by_spec(self):
        manager = ADRManager()
        adr = manager.create("ADR-1", "测试")
        adr.related_specs.append("S-1")
        found = manager.find_by_spec("S-1")
        assert len(found) == 1


class TestOKR:
    def test_progress(self):
        kr1 = KeyResult(id="KR-1", description="完成10个", target_value=10, current_value=5, weight=1.0)
        kr2 = KeyResult(id="KR-2", description="覆盖率80%", target_value=80, current_value=60, weight=1.0)
        okr = OKR(id="O-1", objective="提升质量", key_results=[kr1, kr2])
        assert 0.5 <= okr.progress <= 0.7

    def test_lifecycle(self):
        okr = OKR(id="O-1", objective="测试")
        assert okr.status == OKRStatus.DRAFT
        assert okr.activate()
        assert okr.status == OKRStatus.ACTIVE
        assert okr.complete()
        assert okr.status == OKRStatus.COMPLETED

    def test_update_kr(self):
        kr = KeyResult(id="KR-1", description="完成10个", target_value=10, current_value=0)
        okr = OKR(id="O-1", objective="测试", key_results=[kr])
        assert okr.update_kr("KR-1", 5)
        assert okr.key_results[0].current_value == 5


class TestOKRManager:
    def test_create(self):
        manager = OKRManager()
        manager.create("O-1", "测试目标")
        assert manager.get("O-1") is not None

    def test_get_overdue(self):
        manager = OKRManager()
        okr = manager.create("O-1", "测试", deadline="2020-01-01T00:00:00+00:00")
        okr.activate()
        overdue = manager.get_overdue()
        assert len(overdue) == 1


class TestOMOBridge:
    def test_emit_event(self):
        bridge = OMOBridge()
        event = bridge.emit("test_event", {"key": "value"})
        assert event.event_type == "test_event"
        assert len(bridge.get_events()) == 1

    def test_register_debt(self):
        bridge = OMOBridge()
        debt = bridge.register_debt("测试债务", "描述", "high")
        assert debt["title"] == "测试债务"
        assert len(bridge.get_pending_debts()) == 1

    def test_create_task(self):
        bridge = OMOBridge()
        task = bridge.create_task("测试任务", priority="P1")
        assert task["priority"] == "P1"
        assert len(bridge.get_pending_tasks()) == 1

    def test_record_audit(self):
        bridge = OMOBridge()
        bridge.record_audit("create", "spec", "S-1", {"key": "val"})
        events = bridge.get_events(OMOEventType.AUDIT_RECORDED.value)
        assert len(events) == 1

    def test_stats(self):
        bridge = OMOBridge()
        bridge.emit("test", {})
        bridge.register_debt("d1", "desc")
        stats = bridge.get_stats()
        assert stats["total_events"] == 2
        assert stats["pending_debts"] == 1


class TestAgentCollab:
    def test_create_and_assign(self):
        manager = AgentCollabManager()
        task = manager.create_task("T-1", "测试任务", assigned_by="lead")
        assert task.status == CollabTaskStatus.PENDING

        assert manager.assign_task("T-1", "agent-1")
        assert task.assigned_to == "agent-1"

    def test_start_with_dependency(self):
        manager = AgentCollabManager()
        dep = manager.create_task("T-DEP", "依赖任务")
        dep.status = CollabTaskStatus.COMPLETED
        task = manager.create_task("T-1", "主任务", dependencies=["T-DEP"])
        manager.assign_task("T-1", "agent-1")
        assert manager.start_task("T-1")

    def test_block_and_complete(self):
        manager = AgentCollabManager()
        task = manager.create_task("T-1", "测试")
        manager.assign_task("T-1", "agent-1")
        manager.start_task("T-1")

        assert manager.block_task("T-1", "等待依赖")
        assert task.status == CollabTaskStatus.BLOCKED

    def test_conflict_detection(self):
        manager = AgentCollabManager()
        task = manager.create_task("T-1", "测试")
        manager.assign_task("T-1", "agent-1")
        manager.start_task("T-1")
        manager.block_task("T-1", "阻塞原因")
        conflicts = manager.detect_conflicts()
        assert len(conflicts) == 1

    def test_stats(self):
        manager = AgentCollabManager()
        manager.create_task("T-1", "任务1")
        manager.create_task("T-2", "任务2")
        stats = manager.get_stats()
        assert stats["total"] == 2
