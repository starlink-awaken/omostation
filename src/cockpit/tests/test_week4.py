"""Tests for Week 4 - Connector and Review engines."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_WORKSPACE_ROOT = Path(__file__).resolve().parents[5]


def _load(name: str, rel_path: str):
    path = _WORKSPACE_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"{path} is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_inbox = None
_connector = None
_review = None


def _get_inbox():
    global _inbox
    if _inbox is None:
        _inbox = _load("w4_inbox", "bin/ssot/scene-card-decision-inbox.py")
    return _inbox


def _get_connector():
    global _connector
    if _connector is None:
        _connector = _load("w4_connector", "bin/ssot/scene-card-connector.py")
    return _connector


def _get_review():
    global _review
    if _review is None:
        _review = _load("w4_review", "bin/ssot/scene-card-review.py")
    return _review


def _link_bin(tmp_path):
    bin_ssot = tmp_path / "bin" / "ssot"
    bin_ssot.mkdir(parents=True, exist_ok=True)
    actual_bin = _WORKSPACE_ROOT / "bin" / "ssot"
    for f in actual_bin.iterdir():
        if f.suffix == ".py":
            link = bin_ssot / f.name
            if not link.exists():
                link.symlink_to(f)


def _setup_scene(tmp_path, name="Week4测试"):
    ib = _get_inbox()
    _link_bin(tmp_path)
    scene = ib.create_scene(tmp_path, name=name, description="")
    journey = ib.create_journey(tmp_path, scene_id=scene.id, name="默认流程")
    scene = ib.load_scene(tmp_path, scene.id)
    return ib, scene, journey


def test_connector_import_jsonl(tmp_path):
    """Connector should import items from a JSONL file."""
    ib = _get_inbox()
    conn = _get_connector()
    _link_bin(tmp_path)

    scene = ib.create_scene(tmp_path, name="JSONL导入", description="")
    ib.create_journey(tmp_path, scene_id=scene.id, name="JSONL流程")
    scene = ib.load_scene(tmp_path, scene.id)

    jsonl_path = tmp_path / "items.jsonl"
    items = [
        {"source": "email", "content": "Subject: 测试1\n内容1"},
        {"source": "manual", "content": "手动输入2"},
        {"source": "message", "content": "消息3"},
    ]
    jsonl_path.write_text("\n".join(json.dumps(i) for i in items))

    result = conn.run_connector(tmp_path, source="jsonl", scene_id=scene.id, source_path=str(jsonl_path))
    assert result.items_found == 3
    assert result.items_imported == 3
    assert len(result.errors) == 0

    intents = ib.list_intents(tmp_path, scene.id)
    assert len(intents) == 3


def test_connector_import_directory(tmp_path):
    """Connector should import files from a directory."""
    ib = _get_inbox()
    conn = _get_connector()
    _link_bin(tmp_path)

    scene = ib.create_scene(tmp_path, name="目录导入", description="")
    ib.create_journey(tmp_path, scene_id=scene.id, name="目录流程")
    scene = ib.load_scene(tmp_path, scene.id)

    source_dir = tmp_path / "input_files"
    source_dir.mkdir()
    (source_dir / "file1.txt").write_text("File 1 content")
    (source_dir / "file2.txt").write_text("File 2 content")

    result = conn.run_connector(tmp_path, source="file", scene_id=scene.id, source_path=str(source_dir))
    assert result.items_found >= 2
    assert result.items_imported >= 2


def test_connector_stats(tmp_path):
    """Connector stats should return aggregated counts."""
    ib = _get_inbox()
    conn = _get_connector()
    _link_bin(tmp_path)

    scene = ib.create_scene(tmp_path, name="统计测试", description="")
    ib.create_journey(tmp_path, scene_id=scene.id, name="统计流程")
    scene = ib.load_scene(tmp_path, scene.id)

    jsonl_path = tmp_path / "stats_items.jsonl"
    jsonl_path.write_text(json.dumps({"source": "manual", "content": "test"}))

    conn.run_connector(tmp_path, source="jsonl", scene_id=scene.id, source_path=str(jsonl_path))

    stats = conn.get_connector_stats(tmp_path)
    assert stats["total_runs"] >= 1
    assert stats["total_found"] >= 1
    assert stats["total_imported"] >= 1


def test_connector_unknown_source(tmp_path):
    """Unknown source should return error."""
    conn = _get_connector()
    _link_bin(tmp_path)

    result = conn.run_connector(tmp_path, source="unknown", scene_id="scene-test")
    assert result.items_found == 0
    assert len(result.errors) > 0
    assert "Unknown source" in result.errors[0]


def test_review_weekly_returns_summary(tmp_path):
    """Weekly review should return summary statistics."""
    ib = _get_inbox()
    rev = _get_review()
    _link_bin(tmp_path)

    ib, scene, journey = _setup_scene(tmp_path)

    ib.add_intent(tmp_path, scene_id=scene.id, journey_id=journey.id, source="email", raw_content="测试1", priority="P0")
    ib.add_intent(tmp_path, scene_id=scene.id, journey_id=journey.id, source="manual", raw_content="测试2", priority="P2")

    report = rev.generate_weekly_review(tmp_path, weeks=1)
    assert "summary" in report
    assert report["summary"]["total_intents"] >= 2
    assert "distribution" in report
    assert "daily_trend" in report


def test_review_pilot_report(tmp_path):
    """Pilot report should return comprehensive summary."""
    ib = _get_inbox()
    rev = _get_review()
    _link_bin(tmp_path)

    ib, scene, journey = _setup_scene(tmp_path)
    ib.add_intent(tmp_path, scene_id=scene.id, journey_id=journey.id, source="manual", raw_content="试点测试")

    report = rev.generate_pilot_report(tmp_path)
    assert "pilot_name" in report
    assert "scenes" in report
    assert "total_intents" in report
    assert report["total_intents"] >= 1
    assert len(report["scenes"]) >= 1


def test_review_time_saved_estimation(tmp_path):
    """Review should estimate time saved based on approved intents."""
    ib = _get_inbox()
    rev = _get_review()
    _link_bin(tmp_path)

    ib, scene, journey = _setup_scene(tmp_path)
    intent = ib.add_intent(tmp_path, scene_id=scene.id, journey_id=journey.id, source="email", raw_content="紧急", priority="P0")

    # Use approval flow to approve the intent
    approval = _load("w4_approval", "bin/ssot/scene-card-approval-flow.py")
    approval.approve_intent(tmp_path, intent_id=intent.id, reviewer="test")

    report = rev.generate_weekly_review(tmp_path, weeks=1)
    # P0 intent = 15 minutes
    assert report["summary"]["time_saved_minutes"] >= 15
