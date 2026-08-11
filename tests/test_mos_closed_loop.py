"""Tests for MOS closed-loop engine (BET-Y1Q2-T1-03).

闭环: decision_outcome → adjudication → belief confidence update.
"""

from pathlib import Path

import pytest
import yaml

from omo.omo_adjudication import VERDICT_CONFIDENCE_DELTA, AdjudicationStore
from omo.omo_autonomy_level import REGISTRY_PATH, AutonomyLadder
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

    from omo.omo_adjudication import ADJUDICATIONS_LOG
    from omo.omo_io import AppendOnlyLog, fcntl_lock

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
    mos = MOSBeliefManager(root=tmp_path)
    do_id = mos.record_decision_outcome(
        decision_type="deploy-check",
        input_summary="x",
        expected_outcome="pass",
        actual_outcome="pass",
    )

    from omo.omo_io import AppendOnlyLog, fcntl_lock

    log_path = tmp_path / "adj.jsonl"
    lock_path = tmp_path / "adj.lock"
    summary_file = tmp_path / "runtime/omo/_delivery/outcomes/calibration.yaml"
    log = AppendOnlyLog(path=log_path, lock=fcntl_lock(lock_path))
    store = AdjudicationStore(
        log=log,
        mos_manager=mos,
        calibration_summary_path=summary_file,
    )
    store.record(decision_id=do_id, verdict="accepted")

    assert summary_file.exists()
    data = yaml.safe_load(summary_file.read_text(encoding="utf-8"))
    assert "deploy-check" in data
    assert data["deploy-check"]["calibration"] == 1.0
    assert data["deploy-check"]["accepted"] == 1
    assert data["deploy-check"]["total"] == 1


def test_explicit_observation_state_stays_in_injected_runtime_paths(
    tmp_path: Path,
):
    mos = MOSBeliefManager(root=tmp_path / "mos")
    decision_id = mos.record_decision_outcome(
        decision_type="deploy-check",
        input_summary="x",
        expected_outcome="pass",
        actual_outcome="pass",
    )
    from omo.omo_adjudication import OUTCOMES_DIR
    from omo.omo_io import AppendOnlyLog, fcntl_lock

    default_summary = OUTCOMES_DIR / "capability_calibration_summary.yaml"
    before_summary = default_summary.read_bytes() if default_summary.exists() else None
    before_ladder = REGISTRY_PATH.read_bytes() if REGISTRY_PATH.exists() else None

    runtime_root = tmp_path / "runtime/omo"
    summary_path = (
        runtime_root / "_delivery/outcomes/capability_calibration_summary.yaml"
    )
    ladder_path = runtime_root / "_truth/registry/autonomy-levels.yaml"
    log_path = tmp_path / "adjudications.jsonl"
    store = AdjudicationStore(
        log=AppendOnlyLog(
            path=log_path,
            lock=fcntl_lock(log_path.with_suffix(".lock")),
        ),
        mos_manager=mos,
        calibration_summary_path=summary_path,
        autonomy_ladder=AutonomyLadder(registry_path=ladder_path),
    )

    store.record(decision_id=decision_id, verdict="accepted")

    summary = yaml.safe_load(summary_path.read_text(encoding="utf-8"))
    ladder = yaml.safe_load(ladder_path.read_text(encoding="utf-8"))
    assert summary["deploy-check"]["calibration"] == 1.0
    assert ladder["capabilities"]["deploy-check"]["observations"] == 1
    assert (
        default_summary.read_bytes() if default_summary.exists() else None
    ) == before_summary
    assert (
        REGISTRY_PATH.read_bytes() if REGISTRY_PATH.exists() else None
    ) == before_ladder


def test_missing_observation_dependencies_do_not_write_global_state(tmp_path: Path):
    mos = MOSBeliefManager(root=tmp_path / "mos")
    decision_id = mos.record_decision_outcome(
        decision_type="review",
        input_summary="x",
        expected_outcome="pass",
        actual_outcome="pass",
    )
    from omo.omo_adjudication import OUTCOMES_DIR
    from omo.omo_io import AppendOnlyLog

    default_summary = OUTCOMES_DIR / "capability_calibration_summary.yaml"
    before_summary = default_summary.read_bytes() if default_summary.exists() else None
    before_ladder = REGISTRY_PATH.read_bytes() if REGISTRY_PATH.exists() else None
    log_path = tmp_path / "adjudications.jsonl"
    store = AdjudicationStore(
        log=AppendOnlyLog(path=log_path, lock=None),
        mos_manager=mos,
    )

    store.record(decision_id=decision_id, verdict="accepted")

    assert mos._load_state()["capability_calibrations"][-1]["sample_size"] == 1
    assert (
        default_summary.read_bytes() if default_summary.exists() else None
    ) == before_summary
    assert (
        REGISTRY_PATH.read_bytes() if REGISTRY_PATH.exists() else None
    ) == before_ladder


def test_observation_failure_is_not_silenced_after_primary_append(tmp_path: Path):
    class FailingLadder:
        def record_adjudication(self, capability: str, verdict: str) -> None:
            raise RuntimeError(f"ladder unavailable for {capability}:{verdict}")

    mos = MOSBeliefManager(root=tmp_path / "mos")
    decision_id = mos.record_decision_outcome(
        decision_type="review",
        input_summary="x",
        expected_outcome="pass",
        actual_outcome="pass",
    )
    from omo.omo_io import AppendOnlyLog

    log = AppendOnlyLog(path=tmp_path / "adjudications.jsonl", lock=None)
    store = AdjudicationStore(
        log=log,
        mos_manager=mos,
        autonomy_ladder=FailingLadder(),
    )

    with pytest.raises(RuntimeError, match="ladder unavailable"):
        store.record(decision_id=decision_id, verdict="accepted")

    assert len(log.read_all()) == 1


def test_calibration_summary_merges_capabilities(tmp_path: Path):
    mos = MOSBeliefManager(root=tmp_path / "mos")
    first = mos.record_decision_outcome(
        decision_type="review",
        input_summary="a",
        expected_outcome="pass",
        actual_outcome="pass",
    )
    second = mos.record_decision_outcome(
        decision_type="deploy",
        input_summary="b",
        expected_outcome="pass",
        actual_outcome="pass",
    )
    from omo.omo_io import AppendOnlyLog

    summary_path = tmp_path / "runtime/omo/calibration.yaml"
    store = AdjudicationStore(
        log=AppendOnlyLog(path=tmp_path / "adjudications.jsonl", lock=None),
        mos_manager=mos,
        calibration_summary_path=summary_path,
    )

    store.record(decision_id=first, verdict="accepted")
    store.record(decision_id=second, verdict="accepted")

    summary = yaml.safe_load(summary_path.read_text(encoding="utf-8"))
    assert set(summary) == {"deploy", "review"}


def test_feedback_composes_runtime_observation_dependencies(
    tmp_path: Path, monkeypatch
):
    import omo.omo_adjudication as adjudication_module
    import omo.omo_belief as belief_module
    import omo.omo_paths as paths_module
    from omo import cli

    workspace_root = tmp_path / "workspace"
    runtime_root = workspace_root / "runtime/omo"
    runtime_delivery = runtime_root / "_delivery"
    runtime_truth = runtime_root / "_truth"
    primary_outcomes = tmp_path / "primary-outcomes"
    monkeypatch.setattr(belief_module, "WORKSPACE_ROOT", workspace_root)
    monkeypatch.setattr(paths_module, "RUNTIME_DELIVERY_DIR", runtime_delivery)
    monkeypatch.setattr(paths_module, "RUNTIME_TRUTH_DIR", runtime_truth)
    monkeypatch.setattr(adjudication_module, "OUTCOMES_DIR", primary_outcomes)
    monkeypatch.setattr(
        adjudication_module,
        "ADJUDICATIONS_LOG",
        primary_outcomes / "adjudications.jsonl",
    )

    seed_mos = MOSBeliefManager(root=workspace_root)
    decision_id = seed_mos.record_decision_outcome(
        decision_type="deploy-check",
        input_summary="x",
        expected_outcome="pass",
        actual_outcome="pass",
    )
    root_truth = workspace_root / ".omo/_truth/registry/memory-os.yaml"
    before_root_truth = root_truth.read_bytes()

    assert (
        cli._cmd_feedback(["--decision-id", decision_id, "--verdict", "accepted"]) == 0
    )
    assert root_truth.read_bytes() == before_root_truth

    calibration_summary = (
        runtime_delivery / "outcomes/capability_calibration_summary.yaml"
    )
    autonomy_state = runtime_truth / "registry/autonomy-levels.yaml"
    memory_summary = runtime_truth / "registry/memory-os.yaml"
    assert (
        yaml.safe_load(calibration_summary.read_text(encoding="utf-8"))["deploy-check"][
            "total"
        ]
        == 1
    )
    assert (
        yaml.safe_load(autonomy_state.read_text(encoding="utf-8"))["capabilities"][
            "deploy-check"
        ]["observations"]
        == 1
    )
    assert (
        yaml.safe_load(memory_summary.read_text(encoding="utf-8"))[
            "total_capability_calibrations"
        ]
        == 1
    )
    assert (primary_outcomes / "adjudications.jsonl").read_text(encoding="utf-8").count(
        "\n"
    ) == 1
