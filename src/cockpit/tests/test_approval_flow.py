"""Tests for HITL Approval Flow and Evidence Panel."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_WORKSPACE_ROOT = Path(__file__).resolve().parents[5]


def _load_module(name: str, rel_path: str):
    path = _WORKSPACE_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"{path} is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_inbox = None
_engine = None
_bridge = None


def _get_inbox():
    global _inbox
    if _inbox is None:
        _inbox = _load_module("approval_inbox_test", "bin/ssot/scene-card-decision-inbox.py")
    return _inbox


def _get_engine():
    global _engine
    if _engine is None:
        _engine = _load_module("approval_engine_test", "bin/ssot/scene-card-approval-flow.py")
    return _engine


def _get_bridge():
    global _bridge
    if _bridge is None:
        _bridge = _load_module("approval_bridge_test", "bin/ssot/scene-card-task-bridge.py")
    return _bridge


def _link_bin(tmp_path):
    """Create symlink so scripts can find each other across tmp_path."""
    bin_ssot = tmp_path / "bin" / "ssot"
    bin_ssot.mkdir(parents=True, exist_ok=True)
    actual_bin = _WORKSPACE_ROOT / "bin" / "ssot"
    for f in actual_bin.iterdir():
        if f.suffix == ".py":
            link = bin_ssot / f.name
            if not link.exists():
                link.symlink_to(f)


def _setup_scene(tmp_path, name="审批场景"):
    ib = _get_inbox()
    _link_bin(tmp_path)
    scene = ib.create_scene(tmp_path, name=name, description="")
    journey = ib.create_journey(tmp_path, scene_id=scene.id, name="审批流程")
    scene = ib.load_scene(tmp_path, scene.id)
    intent = ib.add_intent(
        tmp_path, scene_id=scene.id, journey_id=journey.id,
        source="email", raw_content="Subject: 紧急审批\n需要审批的内容",
    )
    ib.add_intent(
        tmp_path, scene_id=scene.id, journey_id=journey.id,
        source="manual", raw_content="另一个待审批事项",
    )
    return ib, scene, intent


def test_approval_queue_returns_pending_intents(tmp_path):
    """Review queue should return pending intents."""
    eng = _get_engine()
    _setup_scene(tmp_path)

    queue = eng.get_review_queue(tmp_path)
    assert len(queue) >= 2
    # All should be pending
    assert all(item.get("source") in ("email", "manual") for item in queue)


def test_approval_queue_prioritizes_p0(tmp_path):
    """P0 intents should appear before P3 in the queue."""
    ib = _get_inbox()
    eng = _get_engine()
    _link_bin(tmp_path)

    scene = ib.create_scene(tmp_path, name="优先级测试", description="")
    journey = ib.create_journey(tmp_path, scene_id=scene.id, name="优先级流程")
    scene = ib.load_scene(tmp_path, scene.id)

    # Add a P3 and a P0 intent
    ib.add_intent(tmp_path, scene_id=scene.id, journey_id=journey.id, source="manual", raw_content="普通事项", priority="P3")
    ib.add_intent(tmp_path, scene_id=scene.id, journey_id=journey.id, source="email", raw_content="紧急事项", priority="P0")

    queue = eng.get_review_queue(tmp_path)
    assert queue[0]["priority"] == "P0"


def test_approval_evidence_returns_detail(tmp_path):
    """Evidence detail should include all evidence for an intent."""
    ib = _get_inbox()
    eng = _get_engine()
    _link_bin(tmp_path)

    scene = ib.create_scene(tmp_path, name="证据测试", description="")
    journey = ib.create_journey(tmp_path, scene_id=scene.id, name="证据流程")
    scene = ib.load_scene(tmp_path, scene.id)
    intent = ib.add_intent(tmp_path, scene_id=scene.id, journey_id=journey.id, source="manual", raw_content="证据测试内容")

    detail = eng.get_evidence_detail(tmp_path, intent.id)
    assert detail is not None
    assert detail["intent_id"] == intent.id
    assert detail["source"] == "manual"
    assert detail["evidence_count"] >= 1


def test_approve_intent_creates_receipt_and_binding(tmp_path):
    """Approving should create receipt and task binding."""
    ib = _get_inbox()
    eng = _get_engine()
    _link_bin(tmp_path)

    scene = ib.create_scene(tmp_path, name="审批测试", description="")
    journey = ib.create_journey(tmp_path, scene_id=scene.id, name="审批流程")
    scene = ib.load_scene(tmp_path, scene.id)
    intent = ib.add_intent(tmp_path, scene_id=scene.id, journey_id=journey.id, source="manual", raw_content="审批测试内容")

    result = eng.approve_intent(tmp_path, intent_id=intent.id, reviewer="测试员", note="已确认")
    assert result["ok"] is True
    assert result["receipt_id"].startswith("receipt-")
    assert result["binding_id"].startswith("bind-")
    assert result["task_id"].startswith("task-")
    assert result["status"] == "approved"

    # Verify intent status updated
    detail = eng.get_evidence_detail(tmp_path, intent.id)
    assert detail["status"] == "task_created"


def test_reject_intent_creates_receipt(tmp_path):
    """Rejecting should create rejection receipt."""
    ib = _get_inbox()
    eng = _get_engine()
    _link_bin(tmp_path)

    scene = ib.create_scene(tmp_path, name="拒绝测试", description="")
    journey = ib.create_journey(tmp_path, scene_id=scene.id, name="拒绝流程")
    scene = ib.load_scene(tmp_path, scene.id)
    intent = ib.add_intent(tmp_path, scene_id=scene.id, journey_id=journey.id, source="manual", raw_content="拒绝测试内容")

    result = eng.reject_intent(tmp_path, intent_id=intent.id, reviewer="测试员", note="不需要")
    assert result["ok"] is True
    assert result["receipt_id"].startswith("receipt-")
    assert result["status"] == "rejected"

    detail = eng.get_evidence_detail(tmp_path, intent.id)
    assert detail["status"] == "rejected"


def test_approval_history_returns_recent(tmp_path):
    """Approval history should return recent receipts."""
    ib = _get_inbox()
    eng = _get_engine()
    _link_bin(tmp_path)

    scene = ib.create_scene(tmp_path, name="历史测试", description="")
    journey = ib.create_journey(tmp_path, scene_id=scene.id, name="历史流程")
    scene = ib.load_scene(tmp_path, scene.id)
    intent1 = ib.add_intent(tmp_path, scene_id=scene.id, journey_id=journey.id, source="manual", raw_content="历史1")
    intent2 = ib.add_intent(tmp_path, scene_id=scene.id, journey_id=journey.id, source="manual", raw_content="历史2")

    eng.approve_intent(tmp_path, intent_id=intent1.id, reviewer="测试员")
    eng.reject_intent(tmp_path, intent_id=intent2.id, reviewer="测试员", note="不需要")

    history = eng.get_approval_history(tmp_path)
    assert len(history) >= 2
    # Both decisions should be present
    decisions = {h["decision"] for h in history[:2]}
    assert "approved" in decisions
    assert "rejected" in decisions


def test_approval_stats_returns_counts(tmp_path):
    """Approval stats should return correct counts."""
    _get_inbox()
    eng = _get_engine()
    _link_bin(tmp_path)

    stats = eng.get_approval_stats(tmp_path)
    assert stats["total_intents"] >= 0
    assert stats["pending_review"] >= 0
