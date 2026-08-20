from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "bc-os" / "north_star_meter_v2.py"
SPEC = importlib.util.spec_from_file_location("north_star_meter_v2", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
meter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(meter)


def _observation(*, readiness: str = "collecting") -> dict:
    return {
        "principal_id": "principal-private",
        "readiness": readiness,
        "total_episodes": 2,
        "verdict_distribution": {"accept": 1, "reject": 1},
        "system_evidence_count": 2,
        "user_evidence_count": 0,
        "unknown_evidence_count": 0,
        "signal_to_verdict_latency_seconds": 12.5,
        "weekly_samples": [
            {
                "week_key": "2026-W34",
                "total_episodes": 2,
                "qualifying_episodes": 1,
                "system_accept_episodes": 1,
                "complete_burden_episodes": 2,
                "review_lt_saved_episodes": 1,
                "summed_review_seconds": 30.0,
                "summed_saved_seconds": 90.0,
                "verdict_distribution": {"accept": 1, "reject": 1},
                "system_evidence_count": 2,
                "user_evidence_count": 0,
                "unknown_evidence_count": 0,
                "gate_met": False,
            }
        ],
        "gate_gaps": ["need four consecutive qualifying weeks"],
    }


def test_direct_recording_is_retired_without_creating_legacy_state(tmp_path, monkeypatch):
    legacy = tmp_path / "consumption-events.json"
    monkeypatch.setattr(meter, "CONSUMPTION_EVENTS", legacy)

    result = meter.record_consumption("scene-a", "approved", consumer="human")

    assert result == {
        "ok": False,
        "reason": "direct_recording_retired_use_omo_broker",
    }
    assert not legacy.exists()


def test_projection_is_privacy_safe_and_three_axis_truthful():
    snapshot = meter.project_value_truth(
        principal_id="principal-private",
        observation=_observation(),
        source_facts={
            "event_count": 9,
            "tip_hash": "a" * 64,
            "integrity": {"ok": True, "total": 9},
        },
        source_ref="repo://runtime/omo/event-ledger.sqlite3",
        observed_at="2026-08-20T04:30:00Z",
    )

    assert snapshot["schema"] == "value-truth-snapshot/v1"
    assert snapshot["status"] == "collecting"
    assert snapshot["truth_axes"] == {
        "engineering_delivery": "not_measured",
        "operational_proof": "proven",
        "personal_value": "collecting",
    }
    assert snapshot["metrics"]["current_week_qualifying_outcomes"] == 1
    assert snapshot["metrics"]["four_week_value_gate"] == "collecting"
    assert snapshot["principal_ref"].startswith("sha256:")
    assert snapshot["source"]["query_digest"].startswith("sha256:")
    rendered = json.dumps(snapshot, ensure_ascii=False)
    assert "principal-private" not in rendered
    assert "/Users/" not in rendered


def test_projection_privacy_normalizes_all_nested_caller_text():
    observation = _observation()
    observation["verdict_distribution"] = {
        "accept": 1,
        "/Users/private/verdict": 99,
        "reject": "PRIVATE VERDICT VALUE",
    }
    observation["weekly_samples"][0]["raw_note"] = "PRIVATE MEDICAL NOTE"
    observation["weekly_samples"][0]["verdict_distribution"] = {
        "accept": 1,
        "private-verdict-key": 7,
        "reject": "PRIVATE WEEKLY VERDICT VALUE",
    }
    observation["gate_gaps"] = [
        "no weekly samples",
        "only /Users/private/forged-gap",
        "/Users/private/medical/gate-gap",
    ]

    snapshot = meter.project_value_truth(
        principal_id="principal-private",
        observation=observation,
        source_facts={
            "event_count": 9,
            "tip_hash": "/Users/private/ledger-tip",
            "integrity": {
                "ok": True,
                "total": 9,
                "raw_error": "PRIVATE INTEGRITY ERROR",
            },
        },
        source_ref="/Users/private/medical/event-ledger.sqlite3",
        observed_at="/Users/private/observed-at",
    )

    rendered = json.dumps(snapshot, ensure_ascii=False)
    assert "/Users/private" not in rendered
    assert "PRIVATE" not in rendered
    assert snapshot["observed_at"] == "unavailable"
    assert snapshot["source"]["ref"].startswith("local-ledger:sha256:")
    assert snapshot["source"]["tip_hash"] == ""
    assert snapshot["source"]["integrity"] == {"ok": True, "total": 9}
    assert snapshot["metrics"]["verdict_distribution"] == {"accept": 1}
    assert snapshot["metrics"]["gate_gaps"] == ["no_weekly_samples"]
    assert snapshot["metrics"]["weekly_samples"] == [
        {
            "week_key": "2026-W34",
            "total_episodes": 2,
            "qualifying_episodes": 1,
            "system_accept_episodes": 1,
            "complete_burden_episodes": 2,
            "review_lt_saved_episodes": 1,
            "summed_review_seconds": 30.0,
            "summed_saved_seconds": 90.0,
            "verdict_distribution": {"accept": 1},
            "system_evidence_count": 2,
            "user_evidence_count": 0,
            "unknown_evidence_count": 0,
            "gate_met": False,
        }
    ]


def test_projection_never_promotes_broken_ledger_integrity():
    snapshot = meter.project_value_truth(
        principal_id="principal-private",
        observation=_observation(readiness="passed"),
        source_facts={
            "event_count": 9,
            "tip_hash": "a" * 64,
            "integrity": {"ok": False, "total": 9, "first_bad_sequence": 4},
        },
        source_ref="repo://runtime/omo/event-ledger.sqlite3",
        observed_at="2026-08-20T04:30:00Z",
    )

    assert snapshot["status"] == "unprovable"
    assert snapshot["truth_axes"]["operational_proof"] == "failed"
    assert snapshot["truth_axes"]["personal_value"] == "unprovable"


def test_measurement_without_principal_or_ledger_is_unprovable(tmp_path):
    missing = tmp_path / "missing.sqlite3"

    no_principal = meter.measure_value_truth(db_path=missing, principal_id="")
    no_ledger = meter.measure_value_truth(db_path=missing, principal_id="principal-private")

    assert no_principal["status"] == "unprovable"
    assert no_principal["reason"] == "principal_id_required"
    assert no_ledger["status"] == "unprovable"
    assert no_ledger["reason"] == "event_ledger_missing"
    assert not missing.exists()


def test_measurement_reads_brokered_personal_outcome_without_mutating_ledger(tmp_path, monkeypatch):
    sys.path[:0] = [str(ROOT / "projects" / "omo" / "src"), str(ROOT / "projects" / "ecos" / "src")]
    from omo.event_ledger.broker import LedgerBroker

    db_path = tmp_path / "event-ledger.sqlite3"
    principal_id = "principal-private"
    episode_id = "episode-real-1"
    signal_id = "signal-event-1"
    action_id = "action:personal-" + hashlib.sha256(episode_id.encode()).hexdigest()[:24]
    common = {
        "principal_id": principal_id,
        "space_id": "personal",
        "correlation_id": f"personal-episode|{episode_id}",
        "occurred_at": "2026-08-20T04:00:00+00:00",
    }
    with LedgerBroker.connect(db_path) as broker:
        broker.append(
            "SignalObserved.v1",
            producer="omo-personal-episode",
            idempotency_key="signal-1",
            event_id=signal_id,
            payload={"source_id": "local-files", "signal_id": "signal-1"},
            **common,
        )
        broker.append(
            "Episode.Decision.v1",
            producer="omo-personal-episode",
            idempotency_key="decision-1",
            episode_id=episode_id,
            causation_id=signal_id,
            payload={"episode_id": episode_id, "source_signal_ref": signal_id},
            **common,
        )
        broker.append(
            "Action.Succeeded.v1",
            producer="omo-pdp",
            idempotency_key="action-1",
            episode_id=episode_id,
            payload={"action_id": action_id},
            **common,
        )
        broker.append(
            "Evidence.LocalDraft.v1",
            producer="omo-personal-episode",
            idempotency_key="evidence-1",
            episode_id=episode_id,
            payload={"action_id": action_id, "output_origin": "system"},
            **common,
        )
        broker.append(
            "Outcome.Human.v1",
            producer="omo-personal-episode",
            idempotency_key="outcome-1",
            episode_id=episode_id,
            payload={
                "action_id": action_id,
                "verdict": "accept",
                "review_duration_seconds": 30.0,
                "estimated_time_saved_seconds": 90.0,
            },
            **common,
        )
        before = [(row["sequence"], row["event_hash"]) for row in broker.read()]

    original_connect = LedgerBroker.connect

    def reject_source_connect(path, *args, **kwargs):
        assert Path(path).resolve() != db_path.resolve(), (
            "measurement opened the source through the write-capable broker"
        )
        return original_connect(path, *args, **kwargs)

    monkeypatch.setattr(LedgerBroker, "connect", reject_source_connect)

    snapshot = meter.measure_value_truth(
        db_path=db_path,
        principal_id=principal_id,
        observed_at="2026-08-20T04:30:00Z",
    )

    monkeypatch.undo()
    with LedgerBroker.connect(db_path) as broker:
        after = [(row["sequence"], row["event_hash"]) for row in broker.read()]
    assert after == before
    assert snapshot["status"] == "collecting"
    assert snapshot["truth_axes"]["operational_proof"] == "proven"
    assert snapshot["metrics"]["current_week_qualifying_outcomes"] == 1
    assert snapshot["source"]["event_count"] == 5


def test_wal_source_files_are_byte_identical_after_measurement(tmp_path):
    sys.path[:0] = [str(ROOT / "projects" / "omo" / "src"), str(ROOT / "projects" / "ecos" / "src")]
    from omo.event_ledger.broker import LedgerBroker

    db_path = tmp_path / "event-ledger.sqlite3"
    broker = LedgerBroker.connect(db_path)
    try:
        broker.append(
            "SignalObserved.v1",
            producer="omo-personal-episode",
            idempotency_key="wal-signal",
            event_id="wal-signal",
            principal_id="principal-private",
            space_id="personal",
            correlation_id="personal-episode|wal",
            occurred_at="2026-08-20T04:00:00+00:00",
            payload={"source_id": "local-files", "signal_id": "wal-signal"},
        )
        shm = Path(str(db_path) + "-shm")
        if shm.exists():
            shm.unlink()
        source_paths = tuple(path for path in tmp_path.iterdir() if path.name.startswith(db_path.name))
        before = {path.name: path.read_bytes() for path in source_paths}

        snapshot = meter.measure_value_truth(
            db_path=db_path,
            principal_id="principal-private",
            observed_at="2026-08-20T04:30:00Z",
        )

        after_paths = tuple(path for path in tmp_path.iterdir() if path.name.startswith(db_path.name))
        after = {path.name: path.read_bytes() for path in after_paths}
        assert snapshot["truth_axes"]["operational_proof"] == "proven"
        assert after == before
    finally:
        broker.close()


def test_system_python39_reexecs_in_omo_runtime_for_valid_ledger(tmp_path):
    system_python = Path("/usr/bin/python3")
    if not system_python.exists():
        return
    sys.path[:0] = [str(ROOT / "projects" / "omo" / "src"), str(ROOT / "projects" / "ecos" / "src")]
    from omo.event_ledger.broker import LedgerBroker

    db_path = tmp_path / "event-ledger.sqlite3"
    with LedgerBroker.connect(db_path) as broker:
        broker.append(
            "SignalObserved.v1",
            producer="omo-personal-episode",
            idempotency_key="python39-signal",
            event_id="python39-signal",
            principal_id="principal-private",
            space_id="personal",
            correlation_id="personal-episode|python39",
            occurred_at="2026-08-20T04:00:00+00:00",
            payload={"source_id": "local-files", "signal_id": "python39-signal"},
        )

    completed = subprocess.run(
        [
            str(system_python),
            str(SCRIPT),
            "--db-path",
            str(db_path),
            "--principal-id",
            "principal-private",
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["truth_axes"]["operational_proof"] == "proven"


def test_cli_keeps_python39_compatible_timezone_imports():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "from datetime import UTC" not in source
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert json.loads(completed.stdout)["reason"] == "principal_id_required"
