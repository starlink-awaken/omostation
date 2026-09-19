import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/panorama-collect.py"


def _module():
    spec = importlib.util.spec_from_file_location("panorama_claims_activation_request_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _valid_package():
    return {
        "schema": "claims-activation-request-package/v1",
        "status": "READY_FOR_OPERATION_SPECIFIC_HUMAN_REVIEW",
        "execution": "NOT_EXECUTED",
        "activation": "NOT_AUTHORIZED",
        "request_digest": "sha256:" + "a" * 64,
        "request": {
            "schema": "claim-mutation-envelope/v2",
            "operation": "activate-shadow",
            "request_id": "request-1",
            "authority_id": "omo-claims-authority-r0",
            "expected_authority_epoch": 0,
            "expected_state": "unactivated",
            "descriptor": {
                "schema": "claims-authority-descriptor/v2",
                "digest": "sha256:" + "b" * 64,
            },
        },
        "human_authorization": {
            "status": "UNPROVEN",
            "required": True,
            "not_sufficient": ["general agent authorization"],
            "required_binding": ["exact request_digest"],
            "observation_after_activation": {
                "duration_seconds": 86400,
                "minimum_samples": 1440,
                "maximum_gap_seconds": 120,
            },
        },
        "rollback": {"automatic_execution": False},
    }


def test_activation_request_projection_exposes_exact_pending_object(tmp_path, monkeypatch) -> None:
    module = _module()
    package_path = tmp_path / "request.json"
    package_path.write_text(json.dumps(_valid_package()), encoding="utf-8")
    monkeypatch.setattr(module, "CLAIMS_REQUEST_PACKAGE", package_path)

    report = module.collect_claims_activation_request()

    assert report["available"] is True
    assert report["status"] == "READY_FOR_OPERATION_SPECIFIC_HUMAN_REVIEW"
    assert report["execution"] == "NOT_EXECUTED"
    assert report["activation"] == "NOT_AUTHORIZED"
    assert report["request_id"] == "request-1"
    assert report["request_digest"] == "sha256:" + "a" * 64
    assert report["descriptor_digest"] == "sha256:" + "b" * 64
    assert report["authority_id"] == "omo-claims-authority-r0"
    assert report["operation"] == "activate-shadow"
    assert report["execution_forbidden_without_human_authorization"] is True
    assert report["human_authorization_status"] == "UNPROVEN"
    assert report["rollback_automatic_execution"] is False


def test_activation_request_projection_fails_closed_for_invalid_schema(tmp_path, monkeypatch) -> None:
    module = _module()
    package = _valid_package()
    package["schema"] = "invalid"
    package_path = tmp_path / "request.json"
    package_path.write_text(json.dumps(package), encoding="utf-8")
    monkeypatch.setattr(module, "CLAIMS_REQUEST_PACKAGE", package_path)

    report = module.collect_claims_activation_request()

    assert report["available"] is False
    assert report["status"] == "PACKAGE_SCHEMA_INVALID"
    assert report["execution"] == "NOT_EXECUTED"
    assert report["activation"] == "NOT_AUTHORIZED"


def test_activation_request_projection_fails_closed_when_missing(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "CLAIMS_REQUEST_PACKAGE", tmp_path / "missing.json")

    report = module.collect_claims_activation_request()

    assert report["available"] is False
    assert report["status"] == "PACKAGE_MISSING"
    assert report["execution"] == "NOT_EXECUTED"
    assert report["activation"] == "NOT_AUTHORIZED"
