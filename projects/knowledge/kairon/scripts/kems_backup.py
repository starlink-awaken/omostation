#!/usr/bin/env python3
"""Create or restore a verified private KEMS SQLite backup."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kos.kems import KemsPersistenceError, backup_sqlite_database, restore_sqlite_database


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--restore", action="store_true", help="restore source backup into destination")
    parser.add_argument("--force", action="store_true", help="replace an existing destination")
    args = parser.parse_args(argv)
    try:
        if args.restore:
            health = restore_sqlite_database(args.source, args.destination, force=args.force)
        else:
            health = backup_sqlite_database(args.source, args.destination, force=args.force)
    except (OSError, ValueError, KemsPersistenceError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(
        json.dumps(
            {"status": "succeeded", "operation": "restore" if args.restore else "backup", **health.to_dict()},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
