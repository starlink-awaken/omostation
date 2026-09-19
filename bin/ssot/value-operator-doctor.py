#!/usr/bin/env python3
"""Read-only doctor for authority-bound real-use value recording.

This command validates prerequisites before a human records value evidence.
It never fabricates evidence, writes the append-only evidence log, or accepts
an HTTP request.  ``--issue-authority-receipt`` only verifies the registered
local principal and emits a fresh receipt with its deterministic digest.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DEFAULT_BASELINE = REPO / ".omo/state/value-baselines/value-recorder-baseline-20260919-unique-exec.json"
DEFAULT_EVIDENCE = REPO / ".omo/_delivery/ingress/value-evidence.jsonl"
DEFAULT_BASELINE_DIR = REPO / ".omo/state/value-baselines"
DEFAULT_PRINCIPAL = "principal:xiamingxing"
DEFAULT_CREDENTIAL_REF = "credential:key:1:sha256:a3bba3adae0ebc76d0c42035e9f2c45172edaf945683ccdb9b4d9e40ccaf47ed"
SHA256_RE = re.compile(r"^sha256:[a-f0-9]{64}$")
REQUIRED_RECEIPT_FIELDS = {
    "principal_id",
    "authority_ref",
    "credential_digest",
    "membership_version",
    "verified_at",
    "expires_at",
    "authority_receipt_digest",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    return value


def _parse_time(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} is missing")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def authority_receipt_digest(receipt: dict[str, Any]) -> str:
    identity = {
        key: receipt[key]
        for key in ("principal_id", "authority_ref", "credential_digest", "membership_version")
    }
    encoded = json.dumps(identity, sort_keys=True, allow_nan=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def validate_authority_receipt(path: Path, principal_id: str, *, now: datetime | None = None) -> dict[str, Any]:
    try:
        receipt = _load_json(path)
        missing = sorted(REQUIRED_RECEIPT_FIELDS - set(receipt))
        if missing:
            raise ValueError(f"missing fields: {', '.join(missing)}")
        if receipt["principal_id"] != principal_id:
            raise ValueError("principal_id mismatch")
        expected_digest = authority_receipt_digest(receipt)
        if receipt["authority_receipt_digest"] != expected_digest:
            raise ValueError("authority_receipt_digest mismatch")
        if not SHA256_RE.fullmatch(str(receipt["authority_receipt_digest"])):
            raise ValueError("authority_receipt_digest is malformed")
        verified = _parse_time(receipt["verified_at"], "verified_at")
        expires = _parse_time(receipt["expires_at"], "expires_at")
        current = now or datetime.now(UTC)
        if verified > current:
            raise ValueError("verified_at is in the future")
        if current >= expires:
            raise ValueError("authority receipt is expired")
        return {
            "available": True,
            "valid": True,
            "fresh": True,
            "principal_id": principal_id,
            "authority_receipt_digest": expected_digest,
            "expires_at": receipt["expires_at"],
        }
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return {
            "available": path.is_file(),
            "valid": False,
            "fresh": False,
            "principal_id": principal_id,
            "error": str(exc),
        }


def validate_decision_evidence(path: Path, decision_id: str, principal_id: str) -> dict[str, Any]:
    try:
        evidence = _load_json(path)
        if evidence.get("decision_persisted") is not True:
            raise ValueError("decision_persisted is not true")
        if evidence.get("decision_id") != decision_id:
            raise ValueError("decision_id mismatch")
        if evidence.get("principal_id") != principal_id:
            raise ValueError("principal_id mismatch")
        if evidence.get("source_class") not in (None, "real_human"):
            raise ValueError("source_class is not real_human")
        return {"available": True, "valid": True, "decision_id": decision_id}
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return {"available": path.is_file(), "valid": False, "decision_id": decision_id, "error": str(exc)}


def validate_baseline(path: Path) -> dict[str, Any]:
    try:
        baseline = _load_json(path)
        copied = {key: value for key, value in baseline.items() if key != "digest"}
        expected = "sha256:" + hashlib.sha256(_canonical_json(copied).encode("utf-8")).hexdigest()
        if baseline.get("digest") != expected:
            raise ValueError("baseline digest mismatch")
        if baseline.get("schema") != "value-baseline/v1" or not baseline.get("baseline_id"):
            raise ValueError("baseline schema or identity mismatch")
        return {
            "available": True,
            "valid": True,
            "baseline_id": baseline["baseline_id"],
            "digest": expected,
            "frozen_at": baseline.get("frozen_at"),
        }
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return {"available": path.is_file(), "valid": False, "error": str(exc)}


def _validate_evidence(evidence: Path, baseline_dir: Path) -> dict[str, Any]:
    recorder_path = REPO / "bin/ssot/value-recorder.py"
    try:
        spec = importlib.util.spec_from_file_location("canonical_value_recorder_doctor", recorder_path)
        if spec is None or spec.loader is None:
            raise ValueError("canonical value recorder unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.validate_evidence(evidence, baseline_dir)
    except Exception as exc:  # noqa: BLE001 - readiness must show, not hide, faults
        return {"available": evidence.is_file(), "ok": False, "error": f"{type(exc).__name__}: {exc}"}


def build_report(
    *,
    principal_id: str,
    decision_id: str,
    baseline: Path,
    evidence: Path,
    baseline_dir: Path,
    authority_receipt: Path,
    decision_evidence: Path,
) -> dict[str, Any]:
    baseline_report = validate_baseline(baseline)
    authority_report = validate_authority_receipt(authority_receipt, principal_id)
    decision_report = validate_decision_evidence(decision_evidence, decision_id, principal_id)
    evidence_report = _validate_evidence(evidence, baseline_dir)
    ready = all((
        baseline_report.get("valid") is True,
        authority_report.get("fresh") is True,
        decision_report.get("valid") is True,
        evidence_report.get("ok") is True,
    ))
    return {
        "schema": "value-operator-doctor-report/v1",
        "read_only": True,
        "ready_to_record": ready,
        "principal_id": principal_id,
        "decision_id": decision_id,
        "baseline": baseline_report,
        "authority_receipt": authority_report,
        "decision_evidence": decision_report,
        "evidence_validation": evidence_report,
        "evidence_path": str(evidence),
        "note": "Ready means prerequisites pass; it does not create or prove a value sample.",
    }


def issue_authority_receipt(principal_id: str, credential_ref: str) -> dict[str, Any]:
    sys.path.insert(0, str(REPO / "projects/ecos/src"))
    sys.path.insert(0, str(REPO / "projects/omo/src"))
    from omo.sovereignty.principal_authority import DefaultPrincipalAuthority, digest_receipt

    receipt = DefaultPrincipalAuthority(production=True).verify(
        principal_id,
        credential_ref,
        now=datetime.now(UTC).isoformat(),
    )
    payload = {
        "principal_id": receipt.principal_id,
        "authority_ref": receipt.authority_ref,
        "credential_digest": receipt.credential_digest,
        "membership_version": receipt.membership_version,
        "verified_at": receipt.verified_at,
        "expires_at": receipt.expires_at,
        "authority_receipt_digest": digest_receipt(receipt),
    }
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--principal-id", default=DEFAULT_PRINCIPAL)
    parser.add_argument("--decision-id")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--baseline-dir", type=Path, default=DEFAULT_BASELINE_DIR)
    parser.add_argument("--authority-receipt", type=Path)
    parser.add_argument("--decision-evidence", type=Path)
    parser.add_argument("--issue-authority-receipt", action="store_true")
    parser.add_argument("--credential-ref", default=DEFAULT_CREDENTIAL_REF)
    args = parser.parse_args(argv)

    if args.issue_authority_receipt:
        print(json.dumps(issue_authority_receipt(args.principal_id, args.credential_ref), ensure_ascii=False, indent=2))
        return 0
    if not args.decision_id:
        parser.error("--decision-id is required without --issue-authority-receipt")
    if args.authority_receipt is None or args.decision_evidence is None:
        parser.error("--authority-receipt and --decision-evidence are required without --issue-authority-receipt")
    report = build_report(
        principal_id=args.principal_id,
        decision_id=args.decision_id,
        baseline=args.baseline,
        evidence=args.evidence,
        baseline_dir=args.baseline_dir,
        authority_receipt=args.authority_receipt,
        decision_evidence=args.decision_evidence,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ready_to_record"] else 1


if __name__ == "__main__":
    sys.exit(main())
