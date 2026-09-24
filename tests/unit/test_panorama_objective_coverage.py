import importlib.util
import hashlib
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/panorama-collect.py"


def _module():
    spec = importlib.util.spec_from_file_location("panorama_objective_coverage_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _payload():
    gates = [{"id": f"A{i}", "verdict": "PASS", "live": True} for i in range(1, 10)]
    gates += [
        {"id": "RF0", "verdict": "PASS", "live": True},
        {"id": "RC-DL", "verdict": "PASS", "live": True},
    ]
    return {
        "gates": gates,
        "code_root_health": {"verdict": "PASS"},
        "claims_task16": {"activation_allowed": False},
        "role_registry": {
            "available": True,
            "verdict": "PASS",
            "integrity_ok": True,
            "total": 2,
            "by_state": {"admitted": 2},
        },
        "agent_cell_semantic": {
            "available": True,
            "verdict": "PASS",
            "receipt_chain_ok": True,
            "receipt_digests_ok": True,
            "role_bindings_ok": True,
            "capsule_bindings_ok": True,
            "mesh_bindings_ok": True,
            "queue_bindings_ok": True,
            "latest_run_id": "semantic-smoke-test",
            "latest_receipt_digest": "sha256:test",
        },
    }


def _write_ledger(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
bets:
  - id: BET-Y1Q4-T10-151
    status: done
    completion_evidence:
      overall_state: delivery_accepted
      axes:
        engineering: {status: VERIFIED}
        operational: {status: PROVEN}
        value: {status: NOT_PROVEN}
  - id: BET-Y1Q4-T10-165
    status: done
    completion_evidence:
      overall_state: delivery_accepted
      axes:
        engineering: {status: VERIFIED}
        operational: {status: PROVEN}
        value: {status: NOT_PROVEN}
""",
        encoding="utf-8",
    )


def _write_claims_store(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE authority_meta (
          authority_id TEXT PRIMARY KEY,
          epoch INTEGER NOT NULL,
          operating_mode TEXT NOT NULL,
          descriptor_digest TEXT,
          last_sequence INTEGER NOT NULL,
          last_receipt_digest TEXT,
          last_broker_time TEXT NOT NULL
        );
        CREATE TABLE activation (
          authority_id TEXT PRIMARY KEY,
          operating_mode TEXT NOT NULL,
          activation_state TEXT NOT NULL,
          descriptor_digest TEXT NOT NULL,
          activated_at TEXT NOT NULL,
          activation_receipt_digest TEXT NOT NULL
        );
        """
    )
    connection.execute(
        "INSERT INTO authority_meta VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "omo-claims-authority-r0",
            1,
            "shadow",
            "sha256:" + "d" * 64,
            2,
            "sha256:" + "5" * 64,
            "2026-09-23T01:53:20Z",
        ),
    )
    connection.execute(
        "INSERT INTO activation VALUES (?, ?, ?, ?, ?, ?)",
        (
            "omo-claims-authority-r0",
            "shadow",
            "shadow-active",
            "sha256:" + "d" * 64,
            "2026-09-19T10:15:36Z",
            "sha256:" + "6" * 64,
        ),
    )
    connection.commit()
    connection.close()


def _write_event_ledger(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE event_log (sequence INTEGER PRIMARY KEY, event_hash TEXT NOT NULL, previous_hash TEXT)"
    )
    connection.executemany(
        "INSERT INTO event_log VALUES (?, ?, ?)",
        [
            (1, "a" * 64, None),
            (2, "b" * 64, "a" * 64),
        ],
    )
    connection.commit()
    connection.close()


def _projection_payload() -> dict:
    return {
        "generated_at": "2026-09-24T03:30:00Z",
        "claims_authority": {
            "available": True,
            "activation_state": "shadow-active",
            "effective_claim_authority": "v1",
            "instruction_capable": False,
            "sequence": 2,
            "status": {"last_receipt_digest": "sha256:" + "5" * 64},
        },
        "agent_visibility": {
            "schema": "panorama-agent-brief/v1",
            "generated_at": "2026-09-24T03:30:00Z",
        },
    }


def test_projection_source_binding_uses_immutable_claims_and_logical_event_chain(tmp_path) -> None:
    module = _module()
    claims_root = tmp_path / "claims"
    store = claims_root / "store.sqlite3"
    _write_claims_store(store)
    (claims_root / "high-water.json").write_text(
        json.dumps({"sequence": 2, "receipt_digest": "sha256:" + "5" * 64}),
        encoding="utf-8",
    )
    (claims_root / "activation-witness.json").write_text(
        json.dumps({"sequence": 1, "state": "shadow-active"}), encoding="utf-8"
    )
    event_ledger = tmp_path / "event-ledger.sqlite3"
    _write_event_ledger(event_ledger)

    binding = module.collect_projection_source_binding(
        claims_root=claims_root,
        event_ledger=event_ledger,
    )

    assert binding["claims"] == {
        "sequence": 2,
        "last_receipt": "sha256:" + "5" * 64,
        "activation": "shadow-active",
        "effective_authority": "v1",
        "instruction_capable": False,
    }
    assert binding["source_hashes"]["claims_store_sha256"] == hashlib.sha256(
        store.read_bytes()
    ).hexdigest()
    assert binding["source_hashes"]["claims_high_water_sha256"] == hashlib.sha256(
        (claims_root / "high-water.json").read_bytes()
    ).hexdigest()
    assert binding["source_hashes"]["claims_witness_sha256"] == hashlib.sha256(
        (claims_root / "activation-witness.json").read_bytes()
    ).hexdigest()
    expected_event_identity = json.dumps(
        {
            "event_count": 2,
            "events": [[1, "a" * 64, None], [2, "b" * 64, "a" * 64]],
            "schema": "omo-event-ledger-identity/v1",
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    assert binding["source_hashes"]["event_ledger_sha256"] == hashlib.sha256(
        expected_event_identity
    ).hexdigest()


def test_projection_source_binding_rejects_broken_event_chain(tmp_path) -> None:
    module = _module()
    claims_root = tmp_path / "claims"
    _write_claims_store(claims_root / "store.sqlite3")
    (claims_root / "high-water.json").write_text(
        json.dumps({"sequence": 2, "receipt_digest": "sha256:" + "5" * 64}),
        encoding="utf-8",
    )
    (claims_root / "activation-witness.json").write_text(
        json.dumps({"sequence": 1, "state": "shadow-active"}), encoding="utf-8"
    )
    event_ledger = tmp_path / "event-ledger.sqlite3"
    _write_event_ledger(event_ledger)
    connection = sqlite3.connect(event_ledger)
    connection.execute("UPDATE event_log SET previous_hash = ? WHERE sequence = 2", ("c" * 64,))
    connection.commit()
    connection.close()

    with pytest.raises(RuntimeError, match="event_ledger_chain_invalid"):
        module.collect_projection_source_binding(
            claims_root=claims_root,
            event_ledger=event_ledger,
        )


def test_claims_projection_reads_storage_without_invoking_claims_status(
    tmp_path, monkeypatch
) -> None:
    module = _module()
    claims_root = tmp_path / "claims"
    _write_claims_store(claims_root / "store.sqlite3")
    (claims_root / "high-water.json").write_text(
        json.dumps({"sequence": 2, "receipt_digest": "sha256:" + "5" * 64}),
        encoding="utf-8",
    )
    (claims_root / "activation-witness.json").write_text(
        json.dumps({"sequence": 1, "state": "shadow-active"}), encoding="utf-8"
    )
    code_root = tmp_path / "code"
    verifier = code_root / "bin/gac/claims-authority-status.py"
    verifier.parent.mkdir(parents=True)
    verifier.write_text("raise SystemExit('must not run')\n", encoding="utf-8")
    monkeypatch.setattr(module, "ROOT", code_root)
    monkeypatch.setattr(module, "CLAIMS_AUTHORITY_ROOT", claims_root)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Claims status subprocess must not run")

    monkeypatch.setattr(module.subprocess, "run", forbidden)

    report = module.collect_claims_authority()

    assert report["available"] is True
    assert report["activation_state"] == "shadow-active"
    assert report["effective_claim_authority"] == "v1"
    assert report["instruction_capable"] is False
    assert report["sequence"] == 2
    assert report["mutation_performed"] is False


def test_publish_projection_revision_is_reader_compatible_and_leaves_legacy_snapshot_untouched(
    tmp_path, monkeypatch
) -> None:
    module = _module()
    state_root = tmp_path / "state"
    state_root.mkdir()
    legacy = state_root / "current.json"
    legacy.write_text('{"legacy":true}', encoding="utf-8")
    monkeypatch.setattr(
        module,
        "collect_projection_source_binding",
        lambda **_kwargs: {
            "claims": {
                "sequence": 2,
                "last_receipt": "sha256:" + "5" * 64,
                "activation": "shadow-active",
                "effective_authority": "v1",
                "instruction_capable": False,
            },
            "source_hashes": {
                "claims_store_sha256": "1" * 64,
                "claims_high_water_sha256": "2" * 64,
                "claims_witness_sha256": "3" * 64,
                "event_ledger_sha256": "4" * 64,
            },
        },
    )
    monkeypatch.setattr(
        module,
        "collect_projection_producer_identity",
        lambda **_kwargs: {
            "root_oid": "c" * 40,
            "omo_gitlink_oid": "e" * 40,
            "collector_sha256": "d" * 64,
            "process_identity": "sha256:" + "f" * 64,
        },
    )

    result = module.publish_projection_revision(
        _projection_payload(),
        state_root=state_root,
        now=datetime(2026, 9, 24, 3, 30, tzinfo=timezone.utc),
    )

    assert legacy.read_text(encoding="utf-8") == '{"legacy":true}'
    pointer = json.loads((state_root / "current-revision.json").read_text(encoding="utf-8"))
    assert pointer == {
        "schema_version": "zhixing-projection-pointer/v1",
        "revision_id": result["revision_id"],
        "manifest_sha256": result["manifest_sha256"],
    }
    revision_root = state_root / "revisions" / result["revision_id"]
    manifest_body = (revision_root / "manifest.json").read_bytes()
    manifest = json.loads(manifest_body)
    assert hashlib.sha256(manifest_body).hexdigest() == result["manifest_sha256"]
    assert manifest["schema_version"] == "zhixing-projection-manifest/v1"
    assert manifest["fresh_until"] == "2026-09-24T03:40:00Z"
    assert manifest["producer"]["root_oid"] == "c" * 40
    assert manifest["producer"]["process_identity"] == "sha256:" + "f" * 64
    assert manifest["source_hashes"]["event_ledger_sha256"] == "4" * 64
    assert manifest["claims"]["instruction_capable"] is False
    for name, filename in {
        "page": "index.html",
        "data": "data.json",
        "agent_brief": "agent-brief.json",
    }.items():
        body = (revision_root / filename).read_bytes()
        assert manifest["artifacts"][name] == {
            "filename": filename,
            "sha256": hashlib.sha256(body).hexdigest(),
        }


def test_publish_projection_revision_keeps_previous_pointer_on_swap_failure(
    tmp_path, monkeypatch
) -> None:
    module = _module()
    state_root = tmp_path / "state"
    state_root.mkdir()
    pointer_path = state_root / "current-revision.json"
    pointer_path.write_text('{"previous":true}', encoding="utf-8")
    monkeypatch.setattr(
        module,
        "collect_projection_source_binding",
        lambda **_kwargs: {
            "claims": {
                "sequence": 2,
                "last_receipt": "sha256:" + "5" * 64,
                "activation": "shadow-active",
                "effective_authority": "v1",
                "instruction_capable": False,
            },
            "source_hashes": {
                "claims_store_sha256": "1" * 64,
                "claims_high_water_sha256": "2" * 64,
                "claims_witness_sha256": "3" * 64,
                "event_ledger_sha256": "4" * 64,
            },
        },
    )
    monkeypatch.setattr(
        module,
        "collect_projection_producer_identity",
        lambda **_kwargs: {
            "root_oid": "c" * 40,
            "omo_gitlink_oid": "e" * 40,
            "collector_sha256": "d" * 64,
            "process_identity": "sha256:" + "f" * 64,
        },
    )
    original = module._atomic_replace_bytes

    def fail_pointer(path, body):
        if path.name == "current-revision.json":
            raise OSError("simulated pointer failure")
        return original(path, body)

    monkeypatch.setattr(module, "_atomic_replace_bytes", fail_pointer)

    with pytest.raises(OSError, match="simulated pointer failure"):
        module.publish_projection_revision(
            _projection_payload(),
            state_root=state_root,
            now=datetime(2026, 9, 24, 3, 30, tzinfo=timezone.utc),
        )

    assert pointer_path.read_text(encoding="utf-8") == '{"previous":true}'


def test_publish_projection_revision_rejects_payload_claims_from_another_snapshot(
    tmp_path, monkeypatch
) -> None:
    module = _module()
    monkeypatch.setattr(
        module,
        "collect_projection_source_binding",
        lambda **_kwargs: {
            "claims": {
                "sequence": 2,
                "last_receipt": "sha256:" + "5" * 64,
                "activation": "shadow-active",
                "effective_authority": "v1",
                "instruction_capable": False,
            },
            "source_hashes": {
                "claims_store_sha256": "1" * 64,
                "claims_high_water_sha256": "2" * 64,
                "claims_witness_sha256": "3" * 64,
                "event_ledger_sha256": "4" * 64,
            },
        },
    )
    payload = _projection_payload()
    payload["claims_authority"]["sequence"] = 1

    with pytest.raises(RuntimeError, match="projection_payload_claims_mismatch"):
        module.publish_projection_revision(payload, state_root=tmp_path / "state")

    assert not (tmp_path / "state/current-revision.json").exists()


def test_objective_coverage_maps_delivery_without_value_or_activation(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "CODE_ROOT", tmp_path / "code")
    _write_ledger(tmp_path / "code/docs/plans/3y-bet-ledger.yaml")

    report = module.collect_objective_coverage(_payload())

    assert report["schema"] == "panorama-objective-coverage/v1"
    assert report["activation_status"] == "AWAITING_AUTHORIZATION"
    assert report["value_proof"] == "NOT_PROVEN"
    assert report["delivery_complete"] is False
    by_id = {item["id"]: item for item in report["items"]}
    assert by_id["EXECUTION_ENVIRONMENT_A1_A9"]["status"] == "PASS"
    assert by_id["PERSISTENT_ROLE_CAPSULE_HANDOFF_CLAIM_VERIFICATION_ASD"]["status"] == "DELIVERY_ACCEPTED_RUNTIME_VERIFIED"
    assert by_id["PERSISTENT_ROLE_CAPSULE_HANDOFF_CLAIM_VERIFICATION_ASD"]["runtime_status"] == "VERIFIED"
    assert by_id["PERSISTENT_ROLE_CAPSULE_HANDOFF_CLAIM_VERIFICATION_ASD"]["value_status"] == "NOT_PROVEN"
    assert by_id["REFERENCE_CELL_DIRECT_LOCAL"]["status"] == "PASS"
    assert by_id["ORCA_R0"]["status"] == "PASS"
    assert by_id["MULTICA_AS0"]["status"] == "PASS"
    assert by_id["RUFLO_RF0"]["status"] == "PASS"
    assert by_id["CLAIMS_AUTHORITY_ACTIVATION"]["status"] == "AWAITING_AUTHORIZATION"
    assert by_id["BUSINESS_VALUE"]["status"] == "NOT_PROVEN"


def test_objective_coverage_projects_shadow_observation_without_completion(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "CODE_ROOT", tmp_path / "code")
    _write_ledger(tmp_path / "code/docs/plans/3y-bet-ledger.yaml")
    payload = _payload()
    payload["claims_authority"] = {
        "activation_state": "shadow-active",
        "effective_claim_authority": "v1",
        "instruction_capable": False,
    }
    payload["claims_observation_progress"] = {
        "state": "IN_PROGRESS",
        "sample_count": 182,
        "minimum_samples": 1440,
        "checkpoints": [{"id": "smoke", "reached": True, "diagnostic_only": True}],
    }

    report = module.collect_objective_coverage(payload)

    assert report["activation_status"] == "SHADOW_OBSERVING"
    assert report["delivery_complete"] is False
    item = by_id = {
        entry["id"]: entry for entry in report["items"]
    }["CLAIMS_AUTHORITY_ACTIVATION"]
    assert item["status"] == "SHADOW_OBSERVING"
    assert item["runtime_state"] == "shadow-active"
    assert item["observation_state"] == "IN_PROGRESS"
    assert item["value_status"] == "NOT_PROVEN"


def test_observation_progress_projects_live_shadow_window(tmp_path, monkeypatch) -> None:
    module = _module()
    request = {
        "schema": "claims-activation-request-package/v1",
        "available": True,
        "status": "EXECUTED",
        "execution": "EXECUTED_AT_2026-09-19T10:15:36Z",
        "activation": "SHADOW_ACTIVE",
        "execution_receipt": {"receipt_digest": "sha256:receipt"},
        "request": {
            "authority_id": "omo-claims-authority-r0",
            "operation": "activate-shadow",
            "descriptor": {"digest": "sha256:descriptor"},
        },
        "human_authorization": {
            "status": "GRANTED_OPERATION_SPECIFIC_2026-09-19",
            "observation_after_activation": {
                "duration_seconds": 86400,
                "minimum_samples": 1440,
                "maximum_gap_seconds": 120,
                "evidence_dir": str(tmp_path / "evidence"),
            },
        },
        "rollback": {"automatic_execution": False},
    }
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "summary.json").write_text(json.dumps({
        "started_at_utc": (datetime.now(timezone.utc) - timedelta(minutes=31)).isoformat(),
        "samples": 182,
        "invalid": False,
        "max_gap_seconds": 60.1,
        "activation_state": "shadow-active",
        "errors": 0,
        "expected_last_receipt": "sha256:receipt",
        "descriptor_digest": "sha256:descriptor",
    }), encoding="utf-8")
    monkeypatch.setattr(module, "CLAIMS_REQUEST_PACKAGE", tmp_path / "request.json")
    (tmp_path / "request.json").write_text(json.dumps(request), encoding="utf-8")

    report = module.collect_claims_observation_progress()

    assert report["available"] is True
    assert report["state"] == "IN_PROGRESS"
    assert report["activation_state"] == "shadow-active"
    # Without immutable sample records, progress may be shown but readiness
    # must not inherit the summary's unverified count.
    assert report["sample_count"] == 0
    assert {
        "graduation_samples",
        "graduation_span",
        "receipt_constant",
    } <= set(report["graduation_reasons"])
    assert report["state"] == "IN_PROGRESS"
    assert report["receipts_match"] is True
    assert report["errors"] == 0
    assert next(item for item in report["checkpoints"] if item["id"] == "smoke")["reached"] is True
    assert next(item for item in report["checkpoints"] if item["id"] == "graduation")["reached"] is False
    assert report["graduation_ready"] is False
    assert "graduation_samples" in report["graduation_reasons"]
    assert "graduation_span" in report["graduation_reasons"]


def test_observation_progress_falls_back_to_package_observation(tmp_path, monkeypatch) -> None:
    module = _module()
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "summary.json").write_text(json.dumps({
        "started_at_utc": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        "samples": 10,
        "invalid": False,
        "max_gap_seconds": 60,
        "activation_state": "shadow-active",
        "errors": 0,
        "expected_last_receipt": "sha256:receipt",
    }), encoding="utf-8")
    package = {
        "schema": "claims-activation-request-package/v1",
        "status": "EXECUTED",
        "execution": "EXECUTED",
        "activation": "SHADOW_ACTIVE",
        "request": {
            "request_id": "request-1",
            "operation": "activate-shadow",
            "descriptor": {"digest": "sha256:descriptor"},
        },
        "human_authorization": {"required": True, "status": "GRANTED"},
        "execution_receipt": {"receipt_digest": "sha256:receipt"},
        "observation": {
            "duration_seconds": 86400,
            "minimum_samples": 1440,
            "maximum_gap_seconds": 120,
            "evidence_dir": str(evidence),
        },
    }
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(package), encoding="utf-8")
    monkeypatch.setattr(module, "CLAIMS_REQUEST_PACKAGE", request_path)

    report = module.collect_claims_observation_progress()

    assert report["available"] is True
    assert report["state"] == "IN_PROGRESS"
    assert report["evidence_dir"] == str(evidence)


def test_observation_progress_marks_complete_evidence_graduation_ready(tmp_path, monkeypatch) -> None:
    module = _module()
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    started = datetime.now(timezone.utc) - timedelta(hours=25)
    (evidence / "summary.json").write_text(json.dumps({
        "started_at_utc": started.isoformat(),
        "samples": 1440,
        "invalid": False,
        "max_gap_seconds": 61.0,
        "activation_state": "shadow-active",
        "errors": 0,
        "expected_last_receipt": "sha256:receipt",
        "descriptor_digest": "sha256:descriptor",
    }), encoding="utf-8")
    with (evidence / "samples.jsonl").open("w", encoding="utf-8") as handle:
        for index in range(1440):
            sampled = started + timedelta(seconds=61 * index)
            handle.write(json.dumps({
                "sample_no": index + 1,
                "sampled_at_utc": sampled.isoformat(),
                "status": {
                    "descriptor_digest": "sha256:descriptor",
                    "sequence": 1,
                    "activation_state": "shadow-active",
                    "last_receipt_digest": "sha256:receipt",
                },
            }) + "\n")
    package = {
        "schema": "claims-activation-request-package/v1",
        "status": "EXECUTED",
        "execution": "EXECUTED",
        "activation": "SHADOW_ACTIVE",
        "request": {"authority_id": "omo-claims-authority-r0", "operation": "activate-shadow", "descriptor": {"digest": "sha256:descriptor"}},
        "human_authorization": {
            "status": "GRANTED",
            "observation_after_activation": {
                "duration_seconds": 86400,
                "minimum_samples": 1440,
                "maximum_gap_seconds": 120,
                "evidence_dir": str(evidence),
            },
        },
        "execution_receipt": {"receipt_digest": "sha256:receipt"},
        "rollback": {"automatic_execution": False},
    }
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(package), encoding="utf-8")
    monkeypatch.setattr(module, "CLAIMS_REQUEST_PACKAGE", request_path)

    report = module.collect_claims_observation_progress()

    assert report["available"] is True
    assert report["state"] == "GRADUATION_REACHED"
    assert report["sample_count"] == 1440
    assert report["evidence_span_seconds"] >= 86400
    assert report["graduation_ready"] is True
    assert report["graduation_reasons"] == []
    assert all(report["graduation_criteria"].values())


def test_objective_coverage_fails_partial_on_missing_ledger_or_gate(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "CODE_ROOT", tmp_path / "missing")
    payload = _payload()
    payload["gates"][0]["verdict"] = "FAIL"

    report = module.collect_objective_coverage(payload)

    by_id = {item["id"]: item for item in report["items"]}
    assert by_id["EXECUTION_ENVIRONMENT_A1_A9"]["status"] == "PARTIAL"
    assert by_id["PERSISTENT_ROLE_CAPSULE_HANDOFF_CLAIM_VERIFICATION_ASD"]["status"] == "EVIDENCE_INCOMPLETE"
    assert report["delivery_complete"] is False


def test_objective_coverage_marks_runtime_unverified_without_live_semantics(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "CODE_ROOT", tmp_path / "code")
    _write_ledger(tmp_path / "code/docs/plans/3y-bet-ledger.yaml")
    payload = _payload()
    payload["agent_cell_semantic"] = {"available": True, "verdict": "DEGRADED"}
    payload["role_registry"] = {"available": True, "verdict": "DEGRADED", "integrity_ok": False}

    report = module.collect_objective_coverage(payload)

    item = next(
        item for item in report["items"]
        if item["id"] == "PERSISTENT_ROLE_CAPSULE_HANDOFF_CLAIM_VERIFICATION_ASD"
    )
    assert item["status"] == "DELIVERY_ACCEPTED_RUNTIME_UNVERIFIED"
    assert item["runtime_status"] == "UNVERIFIED"
    assert item["value_status"] == "NOT_PROVEN"
