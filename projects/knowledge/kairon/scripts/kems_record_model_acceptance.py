#!/usr/bin/env python3
"""Persist a redacted KEMS model-acceptance report without authorizing promotion."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from kos.kems import ModelAcceptanceStore


def _database_argument() -> Path:
    return Path(os.environ.get("KEMS_MODEL_ACCEPTANCE_DB", str(Path.home() / ".kems" / "model-acceptance.sqlite")))


def _read_report(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to read model acceptance report: {type(exc).__name__}") from exc
    if not isinstance(payload, dict):
        raise ValueError("model acceptance report must be an object")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path, help="redacted model-acceptance report JSON")
    parser.add_argument("--run-id", required=True, help="immutable acceptance run identity")
    parser.add_argument("--database", type=Path, default=_database_argument())
    args = parser.parse_args(argv)
    try:
        inserted = ModelAcceptanceStore(args.database.expanduser().resolve()).record(
            args.run_id,
            _read_report(args.report),
        )
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(
        json.dumps(
            {
                "status": "succeeded",
                "inserted": inserted,
                "run_id": args.run_id,
                "database": str(args.database.expanduser().resolve()),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
