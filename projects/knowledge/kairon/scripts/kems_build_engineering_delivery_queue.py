#!/usr/bin/env python3
"""Build a redacted KEMS queue from the Workflow Mesh engineering-delivery projection."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

QUEUE_SCHEMA = "kems.adjudication-queue.v1"
SOURCE_SCHEMA = "engineering-delivery-review-queue/v1"
SCENARIO_ID = "engineering-delivery-review-v1"
SPLITS = {"train", "validation", "test", "shadow"}
_PRIVATE_KEYS = {
    "body",
    "content",
    "document_body",
    "document_text",
    "model_output",
    "ocr_text",
    "prompt",
    "raw_text",
    "source_body",
    "source_text",
    "text",
}


class EngineeringDeliveryQueueError(ValueError):
    """The Workflow Mesh projection cannot safely become an annotation queue."""


def _reject_private(value: object) -> None:
    if isinstance(value, dict):
        if _PRIVATE_KEYS.intersection(str(key).lower() for key in value):
            raise EngineeringDeliveryQueueError("raw content fields are forbidden")
        for child in value.values():
            _reject_private(child)
    elif isinstance(value, list):
        for child in value:
            _reject_private(child)


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _projection(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise EngineeringDeliveryQueueError("review projection must be an object")
    candidate = payload.get("projection", payload)
    if not isinstance(candidate, dict):
        raise EngineeringDeliveryQueueError("review projection must be an object")
    _reject_private(candidate)
    if candidate.get("schema") != SOURCE_SCHEMA:
        raise EngineeringDeliveryQueueError("unsupported engineering-delivery review schema")
    scene_binding = candidate.get("scene_binding")
    expected_scene = {
        "scene_id": "engineering-delivery",
        "journey_id": "intent-to-evidence",
        "outcome_metric": "verified_delivery_lead_time",
    }
    if scene_binding != expected_scene:
        raise EngineeringDeliveryQueueError("engineering-delivery scene binding is invalid")
    controls = candidate.get("controls")
    if (
        not isinstance(controls, dict)
        or controls.get("read_only") is not True
        or controls.get("provider_invocation") is not False
    ):
        raise EngineeringDeliveryQueueError("review projection controls must remain read-only")
    rows = candidate.get("rows")
    if not isinstance(rows, list):
        raise EngineeringDeliveryQueueError("review projection rows must be a list")
    return candidate


def _sample_id(row: dict[str, Any], source_sha256: str) -> str:
    identity = "\0".join(str(row.get(field) or "") for field in ("workflow_run_id", "delivery_id", "receipt_event_id"))
    return f"sample-{hashlib.sha256(f'{identity}\0{source_sha256}'.encode()).hexdigest()[:24]}"


def build_queue(payload: object, *, split: str = "shadow") -> list[dict[str, object]]:
    if split not in SPLITS:
        raise EngineeringDeliveryQueueError(f"split is unsupported: {split}")
    projection = _projection(payload)
    rows: list[dict[str, object]] = []
    for row in projection["rows"]:
        if not isinstance(row, dict):
            raise EngineeringDeliveryQueueError("review projection row must be an object")
        if row.get("review_status") != "reviewed":
            continue
        if row.get("scene_binding") != projection["scene_binding"]:
            raise EngineeringDeliveryQueueError("reviewed row scene binding is invalid")
        if row.get("latest_decision") not in {"reviewed", "adopted", "rejected"}:
            raise EngineeringDeliveryQueueError("reviewed row must have a valid latest decision")
        required = ("workflow_run_id", "delivery_id", "receipt_event_id", "lead_time_seconds", "evidence_count")
        if any(row.get(field) in (None, "") for field in required):
            raise EngineeringDeliveryQueueError("reviewed row is missing stable delivery metadata")
        source = {
            "workflow_run_id": row["workflow_run_id"],
            "trace_id": row["trace_id"],
            "delivery_id": row["delivery_id"],
            "scene_binding": row["scene_binding"],
            "workflow_state": row["workflow_state"],
            "receipt_event_id": row["receipt_event_id"],
            "latest_decision": row["latest_decision"],
            "lead_time_seconds": row["lead_time_seconds"],
            "evidence_count": row["evidence_count"],
        }
        source_sha256 = _canonical_sha256(source)
        sample_id = _sample_id(row, source_sha256)
        rows.append(
            {
                "queue_schema": QUEUE_SCHEMA,
                "sample_id": sample_id,
                "source_sha256": source_sha256,
                "source_ref": f"vault://redacted/workflow-mesh/engineering-delivery/{sample_id}",
                "scenario_id": SCENARIO_ID,
                "split": split,
                "annotation_status": "pending",
                "annotation_version": "",
                "labels": {},
            }
        )
    if not rows:
        raise EngineeringDeliveryQueueError("no reviewed engineering-delivery rows found")
    rows.sort(key=lambda item: str(item["sample_id"]))
    return rows


def write_queue(rows: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        temporary.chmod(0o600)
        temporary.replace(output_path)
        output_path.chmod(0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", required=True, type=Path, help="redacted engineering-delivery review projection JSON"
    )
    parser.add_argument("--output", required=True, type=Path, help="redacted KEMS adjudication JSONL")
    parser.add_argument("--split", default="shadow", choices=sorted(SPLITS))
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.expanduser().resolve().read_text(encoding="utf-8"))
        rows = build_queue(payload, split=args.split)
        write_queue(rows, args.output.expanduser().resolve())
    except (OSError, json.JSONDecodeError, EngineeringDeliveryQueueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(
        json.dumps(
            {
                "status": "succeeded",
                "queue_schema": QUEUE_SCHEMA,
                "scenario_id": SCENARIO_ID,
                "sample_count": len(rows),
                "output": str(args.output.expanduser().resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
