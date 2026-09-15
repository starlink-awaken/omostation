#!/usr/bin/env python3
"""Import a redacted adjudication JSONL queue into the persistent KEMS store."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from kos.kems import AdjudicationStore


def read_queue(path: Path) -> list[object]:
    rows: list[object] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_number}: invalid JSON") from exc
    if not rows:
        raise ValueError("queue is empty")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(os.environ.get("KEMS_ADJUDICATION_DB", str(Path.home() / ".kems" / "adjudication.sqlite"))),
    )
    args = parser.parse_args()
    try:
        inserted = AdjudicationStore(args.database.expanduser().resolve()).ingest_queue(
            read_queue(args.input.resolve())
        )
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": "succeeded", "inserted": inserted, "database": str(args.database.resolve())}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
