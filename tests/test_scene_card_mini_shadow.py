"""Tests for scene-card-mini-shadow tool (project strategy v1 §1 落地).

Validates:
- Listing shadow cards
- Recording mini-trial samples (useful / not_useful)
- 3-useful threshold → promotion_recommendation
- Non-destructive YAML edit (preserves lifecycle_gate structure)
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "bin" / "gac" / "scene-card-mini-shadow.py"
_MODULE = "_scene_card_mini_shadow_test"


def _load():
    spec = importlib.util.spec_from_file_location(_MODULE, TOOL)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def tool():
    return _load()


def test_mini_threshold_constant_is_3(tool):
    assert tool.MINI_THRESHOLD == 3


def test_format_mini_trial_inner_empty(tool):
    assert tool._format_mini_trial_inner({}) == ""


def test_format_mini_trial_inner_full(tool):
    mini = {
        "useful_count": 2,
        "not_useful_count": 1,
        "eligible_for_assisted": False,
        "last_ts": "2026-08-24T12:00:00Z",
        "samples": [{"ts": "2026-08-24T12:00:00Z", "outcome": "useful"}],
    }
    out = tool._format_mini_trial_inner(mini)
    assert "useful_count: 2" in out
    assert "threshold: 3" in out
    assert "samples:" in out
    assert "outcome: useful" in out


def test_format_mini_trial_inner_with_promotion(tool):
    mini = {
        "useful_count": 3,
        "eligible_for_assisted": True,
        "promoted_at": "2026-08-24T12:00:00Z",
        "promotion_recommendation": "promote now",
    }
    out = tool._format_mini_trial_inner(mini)
    assert "promoted_at" in out
    assert "promotion_recommendation" in out
    assert "eligible_for_assisted: true" in out


def test_record_appends_without_overwriting_existing_lifecycle_gate(tool, tmp_path: Path):
    scene = tmp_path / "test-scene.yaml"
    original = """\
scene_id: test-scene
lifecycle: shadow
lifecycle_gate:
  target: assisted
  blocking_bet: BET-FAKE-001
  thresholds:
    min_samples: 30
    min_calibration: 0.6
  measured_2026_08_19:
    samples: 0
    calibration: null
  status: applied_by_evolution_engine
  rationale: original rationale should not be lost
approval:
  confirmed_by: someone
"""
    scene.write_text(original)
    saved_dir = tool.SCENES_DIR
    tool.SCENES_DIR = tmp_path
    try:
        result = tool.record_mini_sample("test-scene", "useful")
    finally:
        tool.SCENES_DIR = saved_dir
    assert result["ok"] is True
    assert result["useful_count"] == 1
    text = scene.read_text()
    assert "target: assisted" in text
    assert "blocking_bet: BET-FAKE-001" in text
    assert "min_samples: 30" in text
    assert "status: applied_by_evolution_engine" in text
    assert "rationale: original rationale should not be lost" in text
    assert "mini_trial:" in text
    assert "useful_count: 1" in text
    assert "threshold: 3" in text


def test_record_three_useful_triggers_promotion_recommendation(tool, tmp_path: Path):
    scene = tmp_path / "promote-me.yaml"
    scene.write_text("scene_id: promote-me\nlifecycle: shadow\nlifecycle_gate:\n  target: assisted\n")
    saved_dir = tool.SCENES_DIR
    tool.SCENES_DIR = tmp_path
    try:
        tool.record_mini_sample("promote-me", "useful")
        tool.record_mini_sample("promote-me", "useful")
        result = tool.record_mini_sample("promote-me", "useful")
    finally:
        tool.SCENES_DIR = saved_dir
    assert result["useful_count"] == 3
    assert result["eligible_for_assisted"] is True
    assert result["promotion_recommendation"] is not None
    assert "升级到 assisted" in result["promotion_recommendation"]


def test_record_not_useful_does_not_count_toward_threshold(tool, tmp_path: Path):
    scene = tmp_path / "fail-scene.yaml"
    scene.write_text("scene_id: fail-scene\nlifecycle: shadow\nlifecycle_gate:\n  target: assisted\n")
    saved_dir = tool.SCENES_DIR
    tool.SCENES_DIR = tmp_path
    try:
        for _ in range(5):
            tool.record_mini_sample("fail-scene", "not_useful")
    finally:
        tool.SCENES_DIR = saved_dir
    text = scene.read_text()
    assert "useful_count: 0" in text
    assert "not_useful_count: 5" in text
    assert "eligible_for_assisted: false" in text


def test_record_rejects_non_shadow_card(tool, tmp_path: Path):
    scene = tmp_path / "already-assisted.yaml"
    scene.write_text("scene_id: already-assisted\nlifecycle: assisted\n")
    saved_dir = tool.SCENES_DIR
    tool.SCENES_DIR = tmp_path
    try:
        result = tool.record_mini_sample("already-assisted", "useful")
    finally:
        tool.SCENES_DIR = saved_dir
    assert result["ok"] is False
    assert "not in shadow" in result["error"]


def test_record_rejects_invalid_outcome(tool, tmp_path: Path):
    scene = tmp_path / "any-scene.yaml"
    scene.write_text("scene_id: any-scene\nlifecycle: shadow\n")
    saved_dir = tool.SCENES_DIR
    tool.SCENES_DIR = tmp_path
    try:
        result = tool.record_mini_sample("any-scene", "meh")
    finally:
        tool.SCENES_DIR = saved_dir
    assert result["ok"] is False
    assert "invalid outcome" in result["error"]


def test_cli_list_succeeds_against_real_workspace():
    result = subprocess.run(
        [sys.executable, str(TOOL), "--list"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "document-review" in result.stdout