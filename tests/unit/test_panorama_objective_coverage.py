import importlib.util
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone


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
    assert report["sample_count"] == 182
    assert report["state"] == "IN_PROGRESS"
    assert report["receipts_match"] is True
    assert report["errors"] == 0
    assert next(item for item in report["checkpoints"] if item["id"] == "smoke")["reached"] is True
    assert next(item for item in report["checkpoints"] if item["id"] == "graduation")["reached"] is False


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
