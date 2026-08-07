"""Tests for SceneWatcher MOS integration (BET-Y1Q1-T3-02)."""

from pathlib import Path

from omo.omo_belief import MOSBeliefManager
from omo.scenewatcher import DecisionResult, SceneWatcher


def test_evaluate_without_mos_backwards_compatible(tmp_path: Path):
    watcher = SceneWatcher(scene_id="test-scene", scene_path=tmp_path)
    result = watcher.evaluate_confidence({"status": "ok"}, node="node_a")
    assert isinstance(result, DecisionResult)
    assert len(watcher.decision_log) == 1


def test_evaluate_persists_to_mos(tmp_path: Path):
    mos = MOSBeliefManager(root=tmp_path)
    watcher = SceneWatcher(
        scene_id="engineering-delivery",
        scene_path=tmp_path,
        mos_manager=mos,
    )
    result = watcher.evaluate_confidence(
        {"status": "ok", "metrics": {"lead_time": 2.5}},
        node="agent_decisions",
    )
    assert result.action in ("pass", "escalate", "human_veto")

    state = mos._load_state()
    assert len(state["decision_outcomes"]) == 1
    rec = state["decision_outcomes"][0]
    assert "engineering-delivery" in rec["decision_type"]
    assert "agent_decisions" in rec["input_summary"]
    assert rec["source_run_id"] == "scene-watcher:engineering-delivery"


def test_multiple_decisions_persist(tmp_path: Path):
    mos = MOSBeliefManager(root=tmp_path)
    watcher = SceneWatcher(scene_id="s1", scene_path=tmp_path, mos_manager=mos)
    watcher.evaluate_confidence({"a": 1}, node="n1")
    watcher.evaluate_confidence({"b": 2}, node="n2")
    watcher.evaluate_confidence({"c": 3}, node="n3")

    state = mos._load_state()
    assert len(state["decision_outcomes"]) == 3
    assert len(watcher.decision_log) == 3


def test_mos_failure_does_not_break_decision(tmp_path: Path):
    class BrokenMOS:
        def record_decision_outcome(self, **kwargs):
            raise RuntimeError("MOS unavailable")

    watcher = SceneWatcher(scene_id="s1", scene_path=tmp_path, mos_manager=BrokenMOS())
    result = watcher.evaluate_confidence({"x": 1}, node="n1")
    assert isinstance(result, DecisionResult)
    assert len(watcher.decision_log) == 1


def test_persistence_survives_reinit(tmp_path: Path):
    mos = MOSBeliefManager(root=tmp_path)
    w1 = SceneWatcher(scene_id="s1", scene_path=tmp_path, mos_manager=mos)
    w1.evaluate_confidence({"key": "val"}, node="decision_node")

    w2 = SceneWatcher(
        scene_id="s1", scene_path=tmp_path, mos_manager=MOSBeliefManager(root=tmp_path)
    )
    state = w2.mos_manager._load_state()
    assert len(state["decision_outcomes"]) == 1
    assert "decision_node" in state["decision_outcomes"][0]["input_summary"]


def test_on_journey_decision_also_persists(tmp_path: Path):
    mos = MOSBeliefManager(root=tmp_path)
    watcher = SceneWatcher(scene_id="doc-review", scene_path=tmp_path, mos_manager=mos)
    result = watcher.on_journey_decision("escalate_node", {"priority": "high"})
    assert isinstance(result, DecisionResult)

    state = mos._load_state()
    assert len(state["decision_outcomes"]) == 1
    assert "doc-review" in state["decision_outcomes"][0]["decision_type"]
