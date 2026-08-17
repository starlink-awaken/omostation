#!/usr/bin/env python3
"""Persist a redacted engineering-delivery review projection into KEMS adjudication storage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kems_build_engineering_delivery_queue import build_queue, write_queue
from kos.kems import AdjudicationStore


def sync_queue(
    input_path: Path, database_path: Path, evidence_output: Path, *, split: str = "shadow"
) -> dict[str, object]:
    payload = json.loads(input_path.expanduser().resolve().read_text(encoding="utf-8"))
    rows = build_queue(payload, split=split)
    store = AdjudicationStore(database_path.expanduser().resolve())
    inserted = store.ingest_queue(rows)
    write_queue(rows, evidence_output.expanduser().resolve())
    return {
        "status": "succeeded",
        "queue_schema": "kems.adjudication-queue.v1",
        "scenario_id": "engineering-delivery-review-v1",
        "sample_count": len(rows),
        "inserted_count": inserted,
        "database": str(database_path.expanduser().resolve()),
        "evidence_output": str(evidence_output.expanduser().resolve()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", required=True, type=Path, help="redacted engineering-delivery review projection JSON"
    )
    parser.add_argument("--database", required=True, type=Path, help="persistent KEMS adjudication SQLite")
    parser.add_argument("--evidence-output", required=True, type=Path, help="redacted queue evidence JSONL")
    parser.add_argument("--split", default="shadow", choices=("shadow", "train", "validation", "test"))
    args = parser.parse_args()
    try:
        result = sync_queue(args.input, args.database, args.evidence_output, split=args.split)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
