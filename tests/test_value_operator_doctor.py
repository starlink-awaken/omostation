import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin/ssot/value-operator-doctor.py"


def _module():
    spec = importlib.util.spec_from_file_location("value_operator_doctor_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _digest(value):
    import hashlib

    return "sha256:" + hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _baseline(path: Path) -> dict:
    manifest = {
        "schema": "value-baseline/v1",
        "baseline_id": "baseline-test",
        "frozen_at": "2026-09-19T00:00:00+00:00",
        "metrics": {"records": 0},
    }
    manifest["digest"] = _digest(manifest)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


def _authority(path: Path, *, expires: str | None = None, digest: str | None = None) -> dict:
    receipt = {
        "principal_id": "principal:xiamingxing",
        "authority_ref": "authority:omo:v1:principal:xiamingxing",
        "credential_digest": "sha256:" + "a" * 64,
        "membership_version": 1,
        "verified_at": "2026-09-19T00:00:00+00:00",
        "expires_at": expires or "2099-01-01T00:00:00+00:00",
    }
    identity = {key: receipt[key] for key in (
        "principal_id", "authority_ref", "credential_digest", "membership_version"
    )}
    encoded = json.dumps(identity, sort_keys=True, allow_nan=False).encode("utf-8")
    import hashlib
    receipt["authority_receipt_digest"] = digest or ("sha256:" + hashlib.sha256(encoded).hexdigest())
    path.write_text(json.dumps(receipt), encoding="utf-8")
    return receipt


def _decision(path: Path) -> None:
    path.write_text(json.dumps({
        "decision_persisted": True,
        "decision_id": "decision-test",
        "principal_id": "principal:xiamingxing",
        "source_class": "real_human",
    }), encoding="utf-8")


def test_value_operator_doctor_accepts_valid_prerequisites(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "REPO", ROOT)
    baseline = tmp_path / "baseline.json"
    _baseline(baseline)
    authority = tmp_path / "authority.json"
    _authority(authority)
    decision = tmp_path / "decision.json"
    _decision(decision)
    evidence = tmp_path / "evidence.jsonl"
    evidence.write_text("", encoding="utf-8")
    baseline_dir = tmp_path / "baselines"
    baseline_dir.mkdir()
    (baseline_dir / "baseline-test.json").write_text(baseline.read_text(encoding="utf-8"), encoding="utf-8")

    report = module.build_report(
        principal_id="principal:xiamingxing",
        decision_id="decision-test",
        baseline=baseline,
        evidence=evidence,
        baseline_dir=baseline_dir,
        authority_receipt=authority,
        decision_evidence=decision,
    )

    assert report["ready_to_record"] is True
    assert report["baseline"]["valid"] is True
    assert report["authority_receipt"]["fresh"] is True
    assert report["decision_evidence"]["valid"] is True
    assert report["evidence_validation"]["ok"] is True


def test_value_operator_doctor_rejects_expired_or_mismatched_receipt(tmp_path) -> None:
    module = _module()
    baseline = tmp_path / "baseline.json"
    _baseline(baseline)
    authority = tmp_path / "authority.json"
    _authority(authority, expires="2020-01-01T00:00:00+00:00")
    bad_digest = tmp_path / "bad-digest.json"
    _authority(bad_digest, digest="sha256:" + "b" * 64)

    expired = module.validate_authority_receipt(
        authority,
        "principal:xiamingxing",
        now=datetime.now(UTC),
    )
    mismatch = module.validate_authority_receipt(
        bad_digest,
        "principal:xiamingxing",
        now=datetime.now(UTC),
    )
    assert expired["valid"] is False
    assert "expired" in expired["error"]
    assert mismatch["valid"] is False
    assert "digest mismatch" in mismatch["error"]


def test_value_operator_doctor_rejects_missing_decision_evidence(tmp_path) -> None:
    module = _module()
    report = module.validate_decision_evidence(
        tmp_path / "missing.json",
        "decision-test",
        "principal:xiamingxing",
    )
    assert report["available"] is False
    assert report["valid"] is False
