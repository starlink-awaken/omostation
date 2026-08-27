#!/usr/bin/env python3
"""Build a redacted handoff packet for human KEMS annotation and adjudication."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from kos.kems import AdjudicationStore
from kos.kems.annotation_schema import annotation_schema

FORBIDDEN_KEYS = {"body", "content", "ocr_text", "raw_text", "text"}
SCENARIO_ID = "private-source-review-v1"


def _contains_forbidden(value: object) -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                return str(key)
            found = _contains_forbidden(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _contains_forbidden(child)
            if found:
                return found
    return None


def _next_action(item: dict[str, Any]) -> str:
    status = str(item.get("annotation_status", "pending"))
    if status == "pending":
        return "claim_and_submit_independent_annotation"
    if status in {"reviewed", "conflict"}:
        return "independent_adjudicator_submit_final_decision"
    return "no_action"


def build_handoff(database_path: Path, *, scenario_id: str = SCENARIO_ID) -> dict[str, Any]:
    """Return public metadata and the next human action for every unfinished sample."""
    items = AdjudicationStore(database_path).list_items(limit=10000)
    samples = []
    for item in items:
        if item.get("annotation_status") == "adjudicated":
            continue
        samples.append(
            {
                "sample_id": item["sample_id"],
                "source_ref": item["source_ref"],
                "source_sha256": item["source_sha256"],
                "scenario_id": item["scenario_id"],
                "split": item["split"],
                "annotation_status": item["annotation_status"],
                "annotation_version": item.get("annotation_version", ""),
                "annotation_count": item.get("annotation_count", 0),
                "annotation_annotators": item.get("annotation_annotators", []),
                "claimed_annotators": item.get("claimed_annotators", []),
                "annotation_conflict": item.get("annotation_conflict", False),
                "next_action": _next_action(item),
            }
        )
    packet: dict[str, Any] = {
        "schema": "kems.annotation-handoff.v1",
        "scenario": annotation_schema(scenario_id),
        "database": {
            "source": "persistent-adjudication-store",
            "sample_count": len(samples),
        },
        "operating_rules": [
            "Only use the redacted source_ref and never copy private source material into labels.",
            "Two annotators must submit independent labels before adjudication.",
            "An independent adjudicator must record the final decision for conflicts.",
            "Use annotation_version private-source-review-v1.0 for this scenario.",
        ],
        "samples": samples,
    }
    forbidden = _contains_forbidden(packet)
    if forbidden:
        raise ValueError(f"handoff packet contains forbidden field: {forbidden}")
    return packet


def write_packet(packet: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.tmp")
    try:
        temporary.write_text(json.dumps(packet, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(output_path)
        output_path.chmod(0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(os.environ.get("KEMS_ADJUDICATION_DB", str(Path.home() / ".kems" / "adjudication.sqlite"))),
    )
    parser.add_argument("--output", required=True, type=Path, help="redacted handoff packet JSON")
    parser.add_argument("--scenario-id", default=SCENARIO_ID)
    args = parser.parse_args(argv)
    try:
        packet = build_handoff(args.database.expanduser().resolve(), scenario_id=args.scenario_id)
        write_packet(packet, args.output.expanduser().resolve())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": "succeeded",
                "schema": packet["schema"],
                "sample_count": packet["database"]["sample_count"],
                "output": str(args.output.expanduser().resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
