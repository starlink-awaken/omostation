import importlib.util
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/panorama-collect.py"


def _module():
    spec = importlib.util.spec_from_file_location("panorama_claims_authority", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _iso(moment: datetime) -> str:
    return moment.isoformat()


def _write_observation_fixture(tmp_path, *, include_malformed_record: bool):
    evidence = tmp_path / "claims-observation"
    evidence.mkdir()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    started = now - timedelta(minutes=10)
    descriptor = "sha256:" + "0" * 64
    receipt = "sha256:" + "1" * 64
    summary = {
        "started_at_utc": _iso(started),
        "samples": 2,
        "invalid": False,
        "invalid_reason": None,
        "max_gap_seconds": 60.0,
        "last_seq": 1,
        "descriptor_digest": descriptor,
        "expected_last_receipt": receipt,
        "activation_state": "shadow-active",
        "errors": 0,
        "window_valid": None,
    }
    old = started - timedelta(minutes=20)
    records = [
        {"sample_no": 1, "sampled_at_utc": _iso(old), "status": {
            "descriptor_digest": descriptor,
            "activation_state": "shadow-active",
            "last_receipt_digest": receipt,
            "sequence": 1,
        }},
        {"sample_no": 2, "sampled_at_utc": _iso(old + timedelta(seconds=300)), "status": {
            "descriptor_digest": descriptor,
            "activation_state": "shadow-active",
            "last_receipt_digest": receipt,
            "sequence": 1,
        }},
        {"sample_no": 1, "sampled_at_utc": _iso(started + timedelta(seconds=1)), "status": {
            "descriptor_digest": descriptor,
            "activation_state": "shadow-active",
            "last_receipt_digest": receipt,
            "sequence": 1,
        }},
        {"sample_no": 2, "sampled_at_utc": _iso(started + timedelta(seconds=61)), "status": {
            "descriptor_digest": descriptor,
            "activation_state": "shadow-active",
            "last_receipt_digest": receipt,
            "sequence": 1,
        }},
    ]
    if include_malformed_record:
        records.append({"broken": True})
    (evidence / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    (evidence / "samples.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
    package = {
        "schema": "claims-activation-request-package/v1",
        "status": "EXECUTED",
        "request": {
            "schema": "claim-mutation-envelope/v2",
            "request_id": "request-id",
            "authority_id": "omo-claims-authority-r0",
            "operation": "activate-shadow",
            "expected_authority_epoch": 0,
            "expected_state": "unactivated",
            "descriptor": {"digest": descriptor},
        },
        "request_digest": "sha256:" + "2" * 64,
        "human_authorization": {
            "required": True,
            "status": "GRANTED_OPERATION_SPECIFIC",
            "observation_after_activation": {},
        },
        "execution_receipt": {
            "receipt_digest": receipt,
            "authority_epoch": 1,
            "sequence": 1,
        },
        "observation": {
            "schema": "claims-authority-observation-window/v1",
            "evidence_dir": str(evidence),
            "duration_seconds": 86400,
            "minimum_samples": 1440,
            "maximum_gap_seconds": 120,
        },
    }
    package_path = tmp_path / "request.json"
    package_path.write_text(json.dumps(package), encoding="utf-8")
    return package_path, started


def test_claims_observation_progress_grades_current_run_only(tmp_path, monkeypatch) -> None:
    module = _module()
    package_path, started = _write_observation_fixture(
        tmp_path,
        include_malformed_record=False,
    )
    monkeypatch.setattr(module, "CLAIMS_REQUEST_PACKAGE", package_path)

    report = module.collect_claims_observation_progress()

    assert report["available"] is True
    assert report["state"] == "IN_PROGRESS"
    assert report["sample_count"] == 2
    assert report["errors"] == 0
    assert report["observed_max_gap_seconds"] == 60.0
    assert report["first_sample_at_utc"] == _iso(started + timedelta(seconds=1))
    assert report["last_sample_at_utc"] == _iso(started + timedelta(seconds=61))


def test_claims_observation_progress_counts_malformed_current_record(tmp_path, monkeypatch) -> None:
    module = _module()
    package_path, _ = _write_observation_fixture(
        tmp_path,
        include_malformed_record=True,
    )
    monkeypatch.setattr(module, "CLAIMS_REQUEST_PACKAGE", package_path)

    report = module.collect_claims_observation_progress()

    assert report["available"] is True
    assert report["state"] == "INVALID"
    assert report["sample_count"] == 2
    assert report["errors"] == 1
    assert report["observed_max_gap_seconds"] == 60.0


def test_claims_authority_projection_is_read_only_and_fail_closed(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    report = module.collect_claims_authority()
    assert report["schema"] == "claims-authority-projection/v1"
    assert report["available"] is False
    assert report["verdict"] == "UNAVAILABLE"
    assert report["mutation_performed"] is False
    assert report["authorization_granted"] is False


def test_claims_authority_projection_projects_whitelisted_status(tmp_path, monkeypatch) -> None:
    module = _module()
    verifier_report = {
        "schema": "claims-authority-observation/v1",
        "ok": True,
        "verdict": "READ_ONLY",
        "available": True,
        "mutation_performed": False,
        "authorization_granted": False,
        "status": {
            "activation_state": "unactivated",
            "authority_id": "omo-claims-authority-r0",
            "code": "not_activated",
            "effective_claim_authority": "v1",
            "instruction_capable": False,
            "security_level": "R0_COOPERATIVE",
            "sequence": 0,
        },
    }
    monkeypatch.setattr(module, "_verify_claims_authority", lambda: verifier_report)
    result = module.collect_claims_authority()
    assert result["available"] is True
    assert result["verdict"] == "READ_ONLY"
    assert result["mutation_performed"] is False
    assert result["authorization_granted"] is False
    assert result["status"]["effective_claim_authority"] == "v1"
    assert result["status"]["instruction_capable"] is False
