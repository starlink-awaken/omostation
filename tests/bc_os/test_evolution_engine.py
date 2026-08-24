#!/usr/bin/env python3
"""test_evolution_engine.py — EvolutionEngine v1 测试."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

_BIN_GAC = Path(__file__).resolve().parents[2] / "bin" / "bc-os"
sys.path.insert(0, str(_BIN_GAC))
sys.path.insert(0, str(_BIN_GAC.parents[1]))

ev = importlib.import_module("evolution_engine")


def test_observe_returns_scenes(tmp_path, monkeypatch):
    """observe 返回各场景数据."""
    monkeypatch.setattr(ev, "SHADOW_STATE", tmp_path / "shadow.json")
    monkeypatch.setattr(ev, "ROUTED_SIGNALS", tmp_path / "routed.json")
    (tmp_path / "shadow.json").write_text(json.dumps({
        "samples": [
            {"source_scene": "test-scene", "quality_score": 0.7},
            {"source_scene": "test-scene", "quality_score": 0.8},
        ]
    }))
    (tmp_path / "routed.json").write_text(json.dumps([
        {"source_scene": "test-scene"},
    ]))
    engine = ev.EvolutionEngine()
    obs = engine.observe()
    assert "test-scene" in obs["scenes"]
    assert obs["scenes"]["test-scene"]["samples"] == 2


def test_propose_generates_upgrade_for_high_calibration(tmp_path, monkeypatch):
    """calibration 达标时生成升级提案."""
    monkeypatch.setattr(ev, "SHADOW_STATE", tmp_path / "shadow.json")
    monkeypatch.setattr(ev, "ROUTED_SIGNALS", tmp_path / "routed.json")
    samples = [
        {"source_scene": "high-cal-scene", "quality_score": 0.8}
        for _ in range(35)
    ]
    (tmp_path / "shadow.json").write_text(json.dumps({"samples": samples}))
    (tmp_path / "routed.json").write_text(json.dumps([]))
    engine = ev.EvolutionEngine()
    proposals = engine.propose()
    upgrade_proposals = [p for p in proposals if p.type == "scene_lifecycle" and p.target == "high-cal-scene"]
    assert len(upgrade_proposals) == 1


def test_propose_generates_route_tune_for_unscored(tmp_path, monkeypatch):
    """routed 但无 samples 时生成路由优化提案."""
    monkeypatch.setattr(ev, "SHADOW_STATE", tmp_path / "shadow.json")
    monkeypatch.setattr(ev, "ROUTED_SIGNALS", tmp_path / "routed.json")
    (tmp_path / "shadow.json").write_text(json.dumps({"samples": []}))
    (tmp_path / "routed.json").write_text(json.dumps([
        {"source_scene": "unscored-scene"} for _ in range(3)
    ]))
    engine = ev.EvolutionEngine()
    proposals = engine.propose()
    route_proposals = [p for p in proposals if p.type == "route_tune"]
    assert len(route_proposals) >= 1


def test_evaluate_returns_metrics():
    """evaluate 返回 A/B 测试指标."""
    engine = ev.EvolutionEngine()
    proposal = ev.Proposal(
        id="test-1", type="scene_lifecycle", target="test",
        title="Test", rationale="r",
        current_state={"lifecycle": "shadow"},
        proposed_state={"lifecycle": "assisted"},
        evidence=[], risk_level="L1", rollback_plan="r",
    )
    result = engine.evaluate(proposal)
    assert result["decision"] == "pending"
    assert "expected_improvement" in result


def test_approve_creates_rollout(tmp_path, monkeypatch):
    """approve 记录灰度 rollout."""
    monkeypatch.setattr(ev, "PROPOSALS_FILE", tmp_path / "proposals.json")
    monkeypatch.setattr(ev, "ROLLOUTS_FILE", tmp_path / "rollouts.json")
    engine = ev.EvolutionEngine()
    proposal = ev.Proposal(
        id="test-approve", type="scene_lifecycle", target="test",
        title="Test", rationale="r",
        current_state={"lifecycle": "shadow"},
        proposed_state={"lifecycle": "assisted"},
        evidence=[], risk_level="L1", rollback_plan="revert",
    )
    rollout = engine.approve(proposal, operator="test_op")
    assert rollout["status"] == "rolling_out"
    assert rollout["rollback_on_failure"] is True
    rollouts = json.loads((tmp_path / "rollouts.json").read_text())
    assert len(rollouts) == 1


def test_rollback_marks_status(tmp_path, monkeypatch):
    """rollback 标记 rollout 状态."""
    monkeypatch.setattr(ev, "PROPOSALS_FILE", tmp_path / "proposals.json")
    monkeypatch.setattr(ev, "ROLLOUTS_FILE", tmp_path / "rollouts.json")
    engine = ev.EvolutionEngine()
    proposal = ev.Proposal(
        id="rollback-test", type="scene_lifecycle", target="test",
        title="Test", rationale="r",
        current_state={}, proposed_state={}, evidence=[],
        risk_level="L1", rollback_plan="r",
    )
    engine.approve(proposal, operator="test")
    result = engine.rollback(proposal.id, reason="calibration dropped")
    assert result["status"] == "rolled_back"
    assert "rollback_reason" in result


def test_run_cycle_end_to_end(tmp_path, monkeypatch):
    """run_cycle 完整四阶段."""
    monkeypatch.setattr(ev, "SHADOW_STATE", tmp_path / "shadow.json")
    monkeypatch.setattr(ev, "ROUTED_SIGNALS", tmp_path / "routed.json")
    monkeypatch.setattr(ev, "PROPOSALS_FILE", tmp_path / "proposals.json")
    monkeypatch.setattr(ev, "ROLLOUTS_FILE", tmp_path / "rollouts.json")
    (tmp_path / "shadow.json").write_text(json.dumps({"samples": []}))
    (tmp_path / "routed.json").write_text(json.dumps([{"source_scene": "test-s"}]))
    engine = ev.EvolutionEngine()
    result = engine.run_cycle(dry_run=True)
    assert "observed" in result
    assert "proposed" in result
    assert "evaluated" in result
    assert "approved" in result
    assert result["dry_run"] is True


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
