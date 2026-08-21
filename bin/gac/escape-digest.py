#!/usr/bin/env python3
"""Cluster swarm-escape records. Dry-run: never mutates the allowlist (ADR-0422)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import swarm_discipline as sd  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Do not mutate allowlist (always true in Wave 1)",
    )
    parser.add_argument("--dir", default="", help="Escape record directory")
    parser.add_argument("--json", action="store_true", default=True)
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[2]
    if args.dir:
        records: list = []
        for path in sorted(Path(args.dir).glob("*.json")):
            try:
                rec = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(rec, dict):
                records.append(rec)
        digest = sd.digest_escape_records(records)
    else:
        digest = sd.digest_escape_records(sd.load_escape_records(root))
    digest["dry_run"] = True
    digest["mutated_allowlist"] = False
    print(json.dumps(digest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
