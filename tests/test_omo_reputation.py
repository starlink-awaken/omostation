"""Tests for Agent reputation profile (BET-Y1Q2-T4-02)."""

from pathlib import Path

from omo.omo_adjudication import AdjudicationStore
from omo.omo_belief import MOSBeliefManager
from omo.omo_reputation import ReputationProfile, compute_reputation


def _setup_mos(tmp_path: Path) -> tuple[MOSBeliefManager, AdjudicationStore]:
    mos = MOSBeliefManager(root=tmp_path)
    log_path = tmp_path / "adj.jsonl"
    lock_path = tmp_path / "adj.lock"
    from omo.omo_io import AppendOnlyLog, fcntl_lock

    log = AppendOnlyLog(path=log_path, lock=fcntl_lock(lock_path))
    store = AdjudicationStore(log=log, mos_manager=mos)
    return mos, store


def test_empty_reputation(tmp_path: Path):
    mos, store = _setup_mos(tmp_path)
    profile = compute_reputation(mos, store)
    assert profile.total_decisions == 0
    assert profile.total_adjudicated == 0
    assert profile.reliability == 1.0
    assert profile.accuracy == 1.0
    assert profile.rejection_rate == 0.0


def test_reputation_with_decisions_and_adjudications(tmp_path: Path):
    mos, store = _setup_mos(tmp_path)

    do1 = mos.record_decision_outcome(
        decision_type="scene_watcher:test",
        input_summary="n=1",
        expected_outcome="pass",
        actual_outcome="pass confidence=0.9",
        source_run_id="agent-1",
    )
    do2 = mos.record_decision_outcome(
        decision_type="scene_watcher:test",
        input_summary="n=2",
        expected_outcome="pass",
        actual_outcome="pass confidence=0.85",
        source_run_id="agent-1",
    )
    do3 = mos.record_decision_outcome(
        decision_type="scene_watcher:test",
        input_summary="n=3",
        expected_outcome="pass",
        actual_outcome="pass confidence=0.7",
        source_run_id="agent-1",
    )

    store.record(decision_id=do1, verdict="accepted")
    store.record(decision_id=do2, verdict="accepted")
    store.record(decision_id=do3, verdict="rejected")

    profile = compute_reputation(mos, store, agent_id="agent-1")
    assert profile.total_decisions == 3
    assert profile.total_adjudicated == 3
    assert profile.accepted == 2
    assert profile.rejected == 1
    assert abs(profile.reliability - 2 / 3) < 0.01
    assert abs(profile.rejection_rate - 1 / 3) < 0.01


def test_accuracy_high_confidence_only(tmp_path: Path):
    mos, store = _setup_mos(tmp_path)

    do_high = mos.record_decision_outcome(
        decision_type="test",
        input_summary="n",
        expected_outcome="pass",
        actual_outcome="pass confidence=0.95",
    )
    do_low = mos.record_decision_outcome(
        decision_type="test",
        input_summary="n",
        expected_outcome="pass",
        actual_outcome="pass confidence=0.3",
    )

    store.record(decision_id=do_high, verdict="accepted")
    store.record(decision_id=do_low, verdict="rejected")

    profile = compute_reputation(mos, store)
    assert profile.accuracy == 1.0
    assert profile.total_adjudicated == 2


def test_reputation_to_dict(tmp_path: Path):
    mos, store = _setup_mos(tmp_path)
    profile = compute_reputation(mos, store, agent_id="test-agent")
    d = profile.to_dict()
    assert d["agent_id"] == "test-agent"
    assert "reliability" in d
    assert "accuracy" in d
    assert "rejection_rate" in d
    assert "avg_confidence" in d


def test_global_reputation(tmp_path: Path):
    mos, store = _setup_mos(tmp_path)

    do1 = mos.record_decision_outcome(
        decision_type="t",
        input_summary="n",
        expected_outcome="p",
        actual_outcome="p confidence=0.9",
        source_run_id="agent-a",
    )
    do2 = mos.record_decision_outcome(
        decision_type="t",
        input_summary="n",
        expected_outcome="p",
        actual_outcome="p confidence=0.8",
        source_run_id="agent-b",
    )

    store.record(decision_id=do1, verdict="accepted")
    store.record(decision_id=do2, verdict="accepted")

    profile = compute_reputation(mos, store)
    assert profile.agent_id == "global"
    assert profile.total_decisions == 2
    assert profile.accepted == 2
