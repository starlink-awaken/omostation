#!/usr/bin/env python3
"""Authority-bound value sampling, baseline freezing, and evidence validation.

v2 intentionally makes qualifying evidence hard to fake: every sample binds a
real run/scene/decision lineage, a human authority receipt, and a pre-window
baseline.  The CLI never fabricates or backfills evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
EVIDENCE_FILE = REPO / ".omo/_delivery/ingress/value-evidence.jsonl"
BASELINE_DIR = REPO / ".omo/state/value-baselines"
EVIDENCE_SCHEMA_V1 = "value-evidence/v1"
EVIDENCE_SCHEMA_V2 = "value-evidence/v2"
BASELINE_SCHEMA = "value-baseline/v1"
MINIMUM_NET_SAVED_SECONDS = 60
QUALIFYING_SAMPLE_TARGET = 30
QUALIFYING_VERDICTS = frozenset({"accepted", "modified"})
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _digest(value: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_id(value: str, field: str) -> str:
    if not _ID_RE.fullmatch(value):
        raise ValueError(f"{field} must match 3-128 safe id characters")
    return value


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _atomic_json_write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def freeze_baseline(
    *,
    baseline_id: str,
    metrics: Mapping[str, Any],
    output_dir: Path = BASELINE_DIR,
    frozen_at: str | None = None,
) -> dict[str, Any]:
    """Freeze a pre-window metrics snapshot and return its immutable manifest."""
    _require_id(baseline_id, "baseline_id")
    if not isinstance(metrics, dict):
        raise ValueError("baseline metrics must be an object")
    manifest = {
        "schema": BASELINE_SCHEMA,
        "baseline_id": baseline_id,
        "frozen_at": frozen_at or _utc_now(),
        "metrics": metrics,
    }
    manifest["digest"] = _digest(manifest)
    _atomic_json_write(output_dir / f"{baseline_id}.json", manifest)
    return manifest


def load_baseline(
    baseline_id: str, baseline_dir: Path = BASELINE_DIR
) -> tuple[dict[str, Any] | None, str | None]:
    _require_id(baseline_id, "baseline_id")
    path = baseline_dir / f"{baseline_id}.json"
    try:
        baseline = _load_json(path)
    except ValueError as exc:
        return None, str(exc)
    expected = baseline.get("digest")
    copied = {key: value for key, value in baseline.items() if key != "digest"}
    if not isinstance(expected, str) or expected != _digest(copied):
        return None, f"baseline digest mismatch: {path}"
    if baseline.get("schema") != BASELINE_SCHEMA or baseline.get("baseline_id") != baseline_id:
        return None, f"baseline identity/schema mismatch: {path}"
    return baseline, None


def record_episode(
    *,
    review_seconds: int,
    saved_seconds: int,
    verdict: str,
    run_id: str,
    scene_id: str,
    decision_id: str,
    principal_id: str,
    authority_receipt_digest: str,
    baseline_id: str,
    baseline: Mapping[str, Any] | None = None,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Validate and return a v2 episode without touching persistent state."""
    if type(review_seconds) is not int or review_seconds < 0:
        raise ValueError("review_seconds must be a non-negative integer")
    if type(saved_seconds) is not int or saved_seconds < 0:
        raise ValueError("saved_seconds must be a non-negative integer")
    if verdict not in QUALIFYING_VERDICTS:
        raise ValueError(f"verdict must be one of {sorted(QUALIFYING_VERDICTS)}")
    for name, value in (
        ("run_id", run_id),
        ("scene_id", scene_id),
        ("decision_id", decision_id),
        ("baseline_id", baseline_id),
    ):
        _require_id(value, name)
    if not principal_id.startswith("principal:"):
        raise ValueError("principal_id must use the principal:<id> form")
    if not SHA256_RE.fullmatch(authority_receipt_digest):
        raise ValueError("authority_receipt_digest must be sha256:<64 hex>")
    if not isinstance(baseline, dict) or baseline.get("baseline_id") != baseline_id:
        raise ValueError("record must bind the loaded pre-window baseline")

    net_saved_seconds = saved_seconds - review_seconds
    qualifying = (
        net_saved_seconds >= MINIMUM_NET_SAVED_SECONDS
        and baseline.get("schema") == BASELINE_SCHEMA
    )
    return {
        "schema": EVIDENCE_SCHEMA_V2,
        "timestamp": recorded_at or _utc_now(),
        "principal_id": principal_id,
        "run_id": run_id,
        "scene_id": scene_id,
        "decision_id": decision_id,
        "source_class": "real_human",
        "authority_receipt_digest": authority_receipt_digest,
        "baseline_id": baseline_id,
        "baseline_digest": baseline.get("digest"),
        "review_duration_seconds": review_seconds,
        "estimated_time_saved_seconds": saved_seconds,
        "net_saved_seconds": net_saved_seconds,
        "verdict": verdict,
        "qualifying": qualifying,
    }


def append_episode(episode: Mapping[str, Any], evidence_path: Path = EVIDENCE_FILE) -> None:
    if episode.get("schema") != EVIDENCE_SCHEMA_V2:
        raise ValueError("only value-evidence/v2 records may be appended")
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    with evidence_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(episode, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def validate_evidence(
    evidence_path: Path = EVIDENCE_FILE, baseline_dir: Path = BASELINE_DIR
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    if evidence_path.exists():
        for line_number, line in enumerate(evidence_path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                issues.append({"line": str(line_number), "reason": f"invalid JSON: {exc}"})
                continue
            records.append(record)
            if record.get("schema") != EVIDENCE_SCHEMA_V2:
                continue
            required = (
                "run_id", "scene_id", "decision_id", "principal_id",
                "authority_receipt_digest", "baseline_id", "baseline_digest",
            )
            missing = [field for field in required if not record.get(field)]
            if missing:
                issues.append({"line": str(line_number), "reason": f"missing {missing}"})
                continue
            baseline, error = load_baseline(str(record["baseline_id"]), baseline_dir)
            if baseline is None:
                issues.append({"line": str(line_number), "reason": error or "baseline unavailable"})
            elif baseline.get("digest") != record.get("baseline_digest"):
                issues.append({"line": str(line_number), "reason": "baseline digest binding mismatch"})
    qualifying = sum(1 for item in records if item.get("qualifying") is True)
    return {
        "schema": "value-evidence-validation/v2",
        "ok": not issues,
        "records": len(records),
        "v2_records": sum(1 for item in records if item.get("schema") == EVIDENCE_SCHEMA_V2),
        "qualifying": qualifying,
        "target": QUALIFYING_SAMPLE_TARGET,
        "remaining_to_target": max(0, QUALIFYING_SAMPLE_TARGET - qualifying),
        "issues": issues,
    }


def _print_validation(report: dict[str, Any]) -> None:
    print("=" * 56)
    print("  Value Evidence Validation (v2)")
    print("=" * 56)
    print(f"  Records: {report['records']} (v2: {report['v2_records']})")
    print(f"  Qualifying: {report['qualifying']}/{report['target']}")
    print(f"  Remaining to target: {report['remaining_to_target']}")
    print(f"  Valid: {report['ok']}")
    for issue in report["issues"]:
        print(f"  ISSUE line {issue['line']}: {issue['reason']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze-baseline")
    freeze.add_argument("--baseline-id", required=True)
    freeze.add_argument("--input", required=True, type=Path)
    record = commands.add_parser("record")
    record.add_argument("--review", required=True, type=int)
    record.add_argument("--saved", required=True, type=int)
    record.add_argument("--verdict", required=True, choices=sorted(QUALIFYING_VERDICTS))
    record.add_argument("--run-id", required=True)
    record.add_argument("--scene-id", required=True)
    record.add_argument("--decision-id", required=True)
    record.add_argument("--principal-id", default="principal:xiamingxing")
    record.add_argument("--authority-receipt-digest", required=True)
    record.add_argument("--baseline-id", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--evidence", type=Path, default=EVIDENCE_FILE)
    validate.add_argument("--baseline-dir", type=Path, default=BASELINE_DIR)
    args = parser.parse_args()

    try:
        if args.command == "freeze-baseline":
            payload = _load_json(args.input)
            manifest = freeze_baseline(
                baseline_id=args.baseline_id,
                metrics=payload.get("metrics", payload),
            )
            print(json.dumps(manifest, ensure_ascii=False, indent=2))
            return 0
        if args.command == "record":
            baseline, error = load_baseline(args.baseline_id)
            if baseline is None:
                raise ValueError(error or "baseline unavailable")
            episode = record_episode(
                review_seconds=args.review,
                saved_seconds=args.saved,
                verdict=args.verdict,
                run_id=args.run_id,
                scene_id=args.scene_id,
                decision_id=args.decision_id,
                principal_id=args.principal_id,
                authority_receipt_digest=args.authority_receipt_digest,
                baseline_id=args.baseline_id,
                baseline=baseline,
            )
            append_episode(episode)
            print(json.dumps(episode, ensure_ascii=False, indent=2))
            return 0
        report = validate_evidence(args.evidence, args.baseline_dir)
        _print_validation(report)
        return 0 if report["ok"] else 1
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
