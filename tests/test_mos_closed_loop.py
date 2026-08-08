"""Tests for MOS closed-loop engine (BET-Y1Q2-T1-03).

闭环: decision_outcome → adjudication → belief confidence update.
"""

from pathlib import Path

from omo.omo_adjudication import AdjudicationStore, VERDICT_CONFIDENCE_DELTA
from omo.omo_belief import MOSBeliefManager
from omo.scenewatcher import SceneWatcher, create_watcher


def test_update_belief_confidence_increases(tmp_path: Path):
    mos = MOSBeliefManager(root=tmp_path)
    b_id = mos.record_belief(topic="test-topic", belief_text="initial belief")
    new_conf = mos.update_belief_confidence(b_id, +0.1, reason="test")
    assert new_conf == 1.0  # was 1.0, +0.1 → clamped to 1.0


def test_update_belief_confidence_decreases(tmp_path: Path):
    mos = MOSBeliefManager(root=tmp_path)
    b_id = mos.record_belief(topic="test-topic", belief_text="initial belief")
    new_conf = mos.update_belief_confidence(b_id, -0.3, reason="rejected")
    assert abs(new_conf - 0.7) < 1e-9


def test_update_belief_confidence_floor_zero(tmp_path: Path):
    mos = MOSBeliefManager(root=tmp_path)
    b_id = mos.record_belief(topic="test-topic", belief_text="initial belief")
    new_conf = mos.update_belief_confidence(b_id, -2.0, reason="hard reject")
    assert new_conf == 0.0


def test_update_belief_confidence_unknown_id_raises(tmp_path: Path):
    mos = MOSBeliefManager(root=tmp_path)
    try:
        mos.update_belief_confidence("belief-9999", +0.1)
        assert False, "should have raised KeyError"
    except KeyError:
        pass


def test_get_decision_outcome_found(tmp_path: Path):
    mos = MOSBeliefManager(root=tmp_path)
    do_id = mos.record_decision_outcome(
        decision_type="scene_watcher:test",
        input_summary="node=n1",
        expected_outcome="pass",
        actual_outcome="pass confidence=0.9",
    )
    outcome = mos.get_decision_outcome(do_id)
    assert outcome is not None
    assert outcome["id"] == do_id
    assert "scene_watcher:test" in outcome["decision_type"]


def test_get_decision_outcome_not_found(tmp_path: Path):
    mos = MOSBeliefManager(root=tmp_path)
    assert mos.get_decision_outcome("do-9999") is None


def test_find_belief_by_topic(tmp_path: Path):
    mos = MOSBeliefManager(root=tmp_path)
    mos.record_belief(topic="engineering-delivery", belief_text="lead time is good")
    belief = mos.find_belief_by_topic("engineering-delivery")
    assert belief is not None
    assert "engineering-delivery" in belief["topic"]


def test_find_belief_by_topic_partial_match(tmp_path: Path):
    mos = MOSBeliefManager(root=tmp_path)
    mos.record_belief(
        topic="scene_watcher:engineering-delivery", belief_text="delivery ok"
    )
    belief = mos.find_belief_by_topic("engineering-delivery")
    assert belief is not None


def test_find_belief_by_topic_not_found(tmp_path: Path):
    mos = MOSBeliefManager(root=tmp_path)
    assert mos.find_belief_by_topic("nonexistent") is None


def test_adjudication_triggers_belief_update(tmp_path: Path):
    mos = MOSBeliefManager(root=tmp_path)
    mos.record_belief(
        topic="scene_watcher:test-scene", belief_text="test decision is correct"
    )
    do_id = mos.record_decision_outcome(
        decision_type="scene_watcher:test-scene",
        input_summary="node=n1",
        expected_outcome="pass",
        actual_outcome="pass confidence=0.9",
    )

    from omo.omo_io import AppendOnlyLog, fcntl_lock
    from omo.omo_adjudication import ADJUDICATIONS_LOG

    log_path = tmp_path / "adj.jsonl"
    lock_path = tmp_path / "adj.lock"
    log = AppendOnlyLog(path=log_path, lock=fcntl_lock(lock_path))
    store = AdjudicationStore(log=log, mos_manager=mos)

    store.record(decision_id=do_id, verdict="rejected")

    belief = mos.find_belief_by_topic("scene_watcher:test-scene")
    assert belief is not None
    state = mos._load_state()
    for b in state["beliefs"]:
        if b["id"] == belief["id"]:
            assert b["confidence"] < 1.0
            break


def test_adjudication_accepted_boosts_confidence(tmp_path: Path):
    mos = MOSBeliefManager(root=tmp_path)
    b_id = mos.record_belief(topic="test-scene", belief_text="initial")
    mos.update_belief_confidence(b_id, -0.5, reason="setup")
    do_id = mos.record_decision_outcome(
        decision_type="test-scene",
        input_summary="n",
        expected_outcome="pass",
        actual_outcome="pass",
    )

    log_path = tmp_path / "adj.jsonl"
    lock_path = tmp_path / "adj.lock"
    from omo.omo_io import AppendOnlyLog, fcntl_lock

    log = AppendOnlyLog(path=log_path, lock=fcntl_lock(lock_path))
    store = AdjudicationStore(log=log, mos_manager=mos)
    store.record(decision_id=do_id, verdict="accepted")

    state = mos._load_state()
    for b in state["beliefs"]:
        if b["topic"] == "test-scene":
            assert b["confidence"] > 0.5
            break


def test_adjudication_without_mos_no_error(tmp_path: Path):
    log_path = tmp_path / "adj.jsonl"
    lock_path = tmp_path / "adj.lock"
    from omo.omo_io import AppendOnlyLog, fcntl_lock

    log = AppendOnlyLog(path=log_path, lock=fcntl_lock(lock_path))
    store = AdjudicationStore(log=log, mos_manager=None)
    adj_id = store.record(decision_id="do-0001", verdict="rejected")
    assert adj_id.startswith("adj-")


def test_create_watcher_injects_mos(tmp_path: Path):
    watcher = create_watcher(
        scene_id="test-scene",
        scene_path=tmp_path,
        root=tmp_path,
    )
    assert watcher.mos_manager is not None
    assert isinstance(watcher.mos_manager, MOSBeliefManager)
    assert watcher.scene_id == "test-scene"


def test_create_watcher_decision_persists(tmp_path: Path):
    watcher = create_watcher(
        scene_id="eng-delivery",
        scene_path=tmp_path,
        root=tmp_path,
    )
    watcher.evaluate_confidence({"confidence": 0.9}, node="agent_decisions")

    mos = MOSBeliefManager(root=tmp_path)
    state = mos._load_state()
    assert len(state["decision_outcomes"]) == 1
    assert "eng-delivery" in state["decision_outcomes"][0]["decision_type"]


def test_full_closed_loop(tmp_path: Path):
    mos = MOSBeliefManager(root=tmp_path)
    mos.record_belief(
        topic="scene_watcher:review", belief_text="review decisions are reliable"
    )

    watcher = SceneWatcher(
        scene_id="review",
        scene_path=tmp_path,
        mos_manager=mos,
    )
    watcher.evaluate_confidence({"confidence": 0.95}, node="agent_decisions")

    state = mos._load_state()
    do_id = state["decision_outcomes"][0]["id"]

    log_path = tmp_path / "adj.jsonl"
    lock_path = tmp_path / "adj.lock"
    from omo.omo_io import AppendOnlyLog, fcntl_lock

    log = AppendOnlyLog(path=log_path, lock=fcntl_lock(lock_path))
    store = AdjudicationStore(log=log, mos_manager=mos)
    store.record(decision_id=do_id, verdict="rejected")

    state = mos._load_state()
    for b in state["beliefs"]:
        if "review" in b["topic"]:
            assert b["confidence"] < 1.0, (
                f"rejected verdict should lower confidence, got {b['confidence']}"
            )
            break
    else:
        assert False, "belief not found"


def test_verdict_confidence_delta_values():
    assert VERDICT_CONFIDENCE_DELTA["accepted"] > 0
    assert VERDICT_CONFIDENCE_DELTA["rejected"] < 0
    assert VERDICT_CONFIDENCE_DELTA["modified"] < 0
    assert abs(VERDICT_CONFIDENCE_DELTA["rejected"]) > abs(
        VERDICT_CONFIDENCE_DELTA["modified"]
    )


def test_adjudication_triggers_capability_calibration(tmp_path: Path):
    """BET-Y1Q2-T4-01: 每条裁决自动更新 capability_calibration."""
    mos = MOSBeliefManager(root=tmp_path)
    do_id = mos.record_decision_outcome(
        decision_type="scene_watcher:test",
        input_summary="node=n1",
        expected_outcome="pass",
        actual_outcome="pass",
    )

    log_path = tmp_path / "adj.jsonl"
    lock_path = tmp_path / "adj.lock"
    from omo.omo_io import AppendOnlyLog, fcntl_lock

    log = AppendOnlyLog(path=log_path, lock=fcntl_lock(lock_path))
    store = AdjudicationStore(log=log, mos_manager=mos)
    store.record(decision_id=do_id, verdict="accepted")

    state = mos._load_state()
    calibrations = state["capability_calibrations"]
    assert len(calibrations) >= 1
    cal = calibrations[-1]
    assert cal["capability_ref"] == "scene_watcher:test"
    assert cal["success_rate"] == 1.0
    assert cal["sample_size"] == 1


def test_calibration_formula_accepted_over_total(tmp_path: Path):
    """BET-Y1Q2-T4-01: calibration = accepted_as_is / invocations."""
    mos = MOSBeliefManager(root=tmp_path)
    do1 = mos.record_decision_outcome(
        decision_type="review",
        input_summary="a",
        expected_outcome="ok",
        actual_outcome="ok",
    )
    do2 = mos.record_decision_outcome(
        decision_type="review",
        input_summary="b",
        expected_outcome="ok",
        actual_outcome="ok",
    )
    do3 = mos.record_decision_outcome(
        decision_type="review",
        input_summary="c",
        expected_outcome="ok",
        actual_outcome="ok",
    )

    log_path = tmp_path / "adj.jsonl"
    lock_path = tmp_path / "adj.lock"
    from omo.omo_io import AppendOnlyLog, fcntl_lock

    log = AppendOnlyLog(path=log_path, lock=fcntl_lock(lock_path))
    store = AdjudicationStore(log=log, mos_manager=mos)

    store.record(decision_id=do1, verdict="accepted")
    store.record(decision_id=do2, verdict="rejected")
    store.record(decision_id=do3, verdict="accepted")

    state = mos._load_state()
    calibrations = [
        c for c in state["capability_calibrations"] if c["capability_ref"] == "review"
    ]
    assert len(calibrations) >= 1
    last = calibrations[-1]
    assert last["sample_size"] == 3
    assert abs(last["success_rate"] - 2 / 3) < 1e-3


def test_calibration_summary_yaml_written(tmp_path: Path):
    """BET-Y1Q2-T4-01: calibration 值变化可在 /outcomes 观察."""
    import yaml

    mos = MOSBeliefManager(root=tmp_path)
    do_id = mos.record_decision_outcome(
        decision_type="deploy-check",
        input_summary="x",
        expected_outcome="pass",
        actual_outcome="pass",
    )

    outcomes_dir = tmp_path / "outcomes"
    outcomes_dir.mkdir(parents=True, exist_ok=True)

    from omo.omo_io import AppendOnlyLog, fcntl_lock
    from omo import omo_adjudication as adj_mod

    original_outcomes = adj_mod.OUTCOMES_DIR
    adj_mod.OUTCOMES_DIR = outcomes_dir

    try:
        log_path = tmp_path / "adj.jsonl"
        lock_path = tmp_path / "adj.lock"
        log = AppendOnlyLog(path=log_path, lock=fcntl_lock(lock_path))
        store = AdjudicationStore(log=log, mos_manager=mos)
        store.record(decision_id=do_id, verdict="accepted")

        summary_file = outcomes_dir / "capability_calibration_summary.yaml"
        assert summary_file.exists()
        with open(summary_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "deploy-check" in data
        assert data["deploy-check"]["calibration"] == 1.0
        assert data["deploy-check"]["accepted"] == 1
        assert data["deploy-check"]["total"] == 1
    finally:
        adj_mod.OUTCOMES_DIR = original_outcomes
