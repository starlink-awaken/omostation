"""Tests for Scene Card Intake Pipeline and Task Bridge."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# The scripts are in the root workspace's bin/ssot/ directory
_WORKSPACE_ROOT = Path(__file__).resolve().parents[5]  # goes up to ws-scenario-phase1


def _load_module(name: str, rel_path: str):
    """Load a module from the workspace bin/ssot/ directory."""
    path = _WORKSPACE_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"{path} is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


inbox = None
engine = None
bridge = None


def _get_inbox():
    global inbox
    if inbox is None:
        inbox = _load_module("inbox_test", "bin/ssot/scene-card-decision-inbox.py")
    return inbox


def _get_engine():
    global engine
    if engine is None:
        engine = _load_module("engine_test", "bin/ssot/scene-card-intake-pipeline.py")
    return engine


def _get_bridge():
    global bridge
    if bridge is None:
        bridge = _load_module("bridge_test", "bin/ssot/scene-card-task-bridge.py")
    return bridge


# ── Intake pipeline tests ──


def test_intake_preview_email_parses_subject(tmp_path):
    """Preview intake should extract subject from email content."""
    eng = _get_engine()
    content = "Subject: 紧急修复通知\n\n服务器出现故障，需要立即处理。"
    result = eng.preview_intake(content, source="email")
    assert result.title == "紧急修复通知"
    assert result.priority == "P0"
    assert "email" in result.tags


def test_intake_preview_manual_returns_high_confidence(tmp_path):
    """Manual input should have high confidence."""
    eng = _get_engine()
    result = eng.preview_intake("这是一个手动输入的内容", source="manual")
    assert result.confidence == 0.9
    assert result.extraction_method == "manual_input"


def test_intake_preview_file_uses_filename(tmp_path):
    """File intake should use filename as fallback title."""
    eng = _get_engine()
    # Single line content without clear title → first line is used as title
    result = eng.preview_intake("File content here", source="file", filename="report.pdf")
    assert result.title == "File content here"  # First line is used as title
    assert "ext:.pdf" in result.tags, f"Tags: {result.tags}"


def test_intake_preview_priority_detection(tmp_path):
    """Priority should be detected from content keywords."""
    eng = _get_engine()
    assert eng.preview_intake("紧急事故", source="manual").priority == "P0"
    assert eng.preview_intake("重要截止日期今天", source="manual").priority == "P1"
    # "一般" matches P2 keyword "一般"
    result = eng.preview_intake("一般日常事项", source="manual")
    assert result.priority == "P2", f"Expected P2, got {result.priority}"


def test_intake_preview_unknown_source(tmp_path):
    """Unknown source should return error."""
    eng = _get_engine()
    result = eng.preview_intake("test", source="unknown")
    assert result.confidence == 0.0
    assert "Unknown source" in result.description


def test_intake_full_pipeline_creates_intent(tmp_path):
    """Full intake pipeline should create an intent in the decision inbox."""
    ib = _get_inbox()
    eng = _get_engine()

    # Create symlink so engine.intake() can find the inbox engine
    _link_bin(tmp_path)

    # Create a scene
    scene = ib.create_scene(tmp_path, name="测试场景", description="测试")
    ib.create_journey(tmp_path, scene_id=scene.id, name="默认流程")

    # Run intake
    result = eng.intake(
        tmp_path, source="email", raw_content="Subject: 测试邮件\n这是测试内容",
        scene_id=scene.id,
    )
    assert result.ok is True, f"Intake failed: {result.error}"
    assert result.intent_id.startswith("intent-")

    # Verify intent was created in inbox
    intents = ib.list_intents(tmp_path, scene.id)
    assert len(intents) == 1
    assert intents[0].source == "email"


def test_intake_batch_creates_multiple_intents(tmp_path):
    """Batch intake should create multiple intents."""
    ib = _get_inbox()
    eng = _get_engine()

    _link_bin(tmp_path)

    scene = ib.create_scene(tmp_path, name="批量场景", description="")
    ib.create_journey(tmp_path, scene_id=scene.id, name="批量流程")

    items = [
        {"source": "email", "content": "Subject: 邮件1\n内容1"},
        {"source": "manual", "content": "手动输入2"},
        {"source": "file", "content": "文件内容3", "filename": "doc.txt"},
    ]
    results = eng.batch_intake(tmp_path, items=items, scene_id=scene.id)
    assert len(results) == 3
    assert all(r.ok for r in results), f"Some intakes failed: {[r.error for r in results if not r.ok]}"

    intents = ib.list_intents(tmp_path, scene.id)
    assert len(intents) == 3


# ── Task bridge tests ──


def _link_bin(tmp_path):
    """Create symlink so the engine scripts can find each other."""
    bin_ssot = tmp_path / "bin" / "ssot"
    bin_ssot.mkdir(parents=True, exist_ok=True)
    actual_bin = _WORKSPACE_ROOT / "bin" / "ssot"
    for f in actual_bin.iterdir():
        if f.suffix == ".py":
            link = bin_ssot / f.name
            if not link.exists():
                link.symlink_to(f)


def _setup_scene(tmp_path, name="测试场景"):
    """Create a scene with one journey for testing."""
    ib = _get_inbox()
    _link_bin(tmp_path)
    scene = ib.create_scene(tmp_path, name=name, description="")
    journey = ib.create_journey(tmp_path, scene_id=scene.id, name="默认流程")
    # Re-load scene to get updated journeys list
    scene = ib.load_scene(tmp_path, scene.id)
    intent = ib.add_intent(
        tmp_path, scene_id=scene.id, journey_id=journey.id,
        source="manual", raw_content="测试任务内容"
    )
    return ib, scene, intent


def test_task_bridge_approve_intent_creates_binding(tmp_path):
    """Approving an intent should create a task binding."""
    br = _get_bridge()
    ib, scene, intent = _setup_scene(tmp_path)

    result = br.approve_intent_and_create_task(tmp_path, intent_id=intent.id)
    assert result["ok"] is True, f"Approval failed: {result.get('error')}"
    assert result["binding_id"].startswith("bind-")
    assert result["task_id"].startswith("task-")
    assert result["status"] == "task_created"

    # Verify binding exists
    status = br.get_binding_status(tmp_path, intent.id)
    assert status is not None
    assert status["binding_id"] == result["binding_id"]


def test_task_bridge_complete_task(tmp_path):
    """Completing a task should update binding status."""
    br = _get_bridge()
    ib, scene, intent = _setup_scene(tmp_path)

    approve = br.approve_intent_and_create_task(tmp_path, intent_id=intent.id)
    result = br.complete_task(tmp_path, binding_id=approve["binding_id"])
    assert result["ok"] is True
    assert result["status"] == "completed"

    # Verify binding status updated
    status = br.get_binding_status(tmp_path, intent.id)
    assert status["status"] == "completed"


def test_task_bridge_list_bindings(tmp_path):
    """List bindings should return all created bindings."""
    br = _get_bridge()
    ib, scene, intent1 = _setup_scene(tmp_path)
    intent2 = ib.add_intent(tmp_path, scene_id=scene.id, journey_id=scene.journeys[0].id, source="manual", raw_content="任务2")

    br.approve_intent_and_create_task(tmp_path, intent_id=intent1.id)
    br.approve_intent_and_create_task(tmp_path, intent_id=intent2.id)

    bindings = br.list_bindings(tmp_path)
    assert len(bindings) == 2


def test_task_bridge_approve_nonexistent_intent(tmp_path):
    """Approving a non-existent intent should return error."""
    br = _get_bridge()
    _link_bin(tmp_path)
    result = br.approve_intent_and_create_task(tmp_path, intent_id="intent-nonexistent")
    assert result["ok"] is False
    assert "not found" in result["error"]
