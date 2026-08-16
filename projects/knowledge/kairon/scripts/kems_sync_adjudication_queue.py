#!/usr/bin/env python3
"""Sync the controlled source inventory into the persistent KEMS queue."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from kems_build_adjudication_queue import DEFAULT_SCENARIO_ID, build_queue, write_queue
from kos.kems import AdjudicationStore


def sync_queue(
    docs_root: Path,
    database_path: Path,
    evidence_output: Path,
    *,
    scenario_id: str = DEFAULT_SCENARIO_ID,
    split: str = "shadow",
) -> dict[str, object]:
    """Hash controlled sources, persist redacted rows, and write an audit queue."""
    rows = build_queue(docs_root, scenario_id=scenario_id, split=split)
    store = AdjudicationStore(database_path)
    existing_by_source = {str(item["source_ref"]): item for item in store.list_items(limit=10000)}
    for row in rows:
        existing = existing_by_source.get(str(row["source_ref"]))
        if existing and existing["source_sha256"] != row["source_sha256"]:
            raise ValueError(f"source_ref already exists with different metadata: {row['source_ref']}")
    inserted = store.ingest_queue(rows)  # type: ignore[reportArgumentType]
    write_queue(rows, evidence_output)
    return {
        "status": "succeeded",
        "queue_schema": "kems.adjudication-queue.v1",
        "sample_count": len(rows),
        "inserted_count": inserted,
        "pending_count": len(rows),
        "database": str(database_path),
        "evidence_output": str(evidence_output),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=Path(os.environ.get("BOS_DOCS_ROOT", "/Users/xiamingxing/Documents")),
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(os.environ.get("KEMS_ADJUDICATION_DB", str(Path.home() / ".kems" / "adjudication.sqlite"))),
    )
    parser.add_argument("--evidence-output", required=True, type=Path, help="redacted queue JSONL evidence")
    parser.add_argument("--scenario-id", default=DEFAULT_SCENARIO_ID)
    parser.add_argument("--split", default="shadow", choices=("shadow", "train", "validation", "test"))
    args = parser.parse_args()
    try:
        result = sync_queue(
            args.docs_root.expanduser().resolve(),
            args.database.expanduser().resolve(),
            args.evidence_output.expanduser().resolve(),
            scenario_id=args.scenario_id,
            split=args.split,
        )
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
