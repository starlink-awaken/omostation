#!/usr/bin/env python3
"""Inspect KEMS SQLite stores without opening source content."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kos.kems import KemsPersistenceError, inspect_databases


def _databases(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        name, separator, path = value.partition("=")
        if not separator or not name.strip() or not path.strip():
            raise ValueError("--database must use NAME=PATH")
        if name.strip() in result:
            raise ValueError(f"database name is duplicated: {name.strip()}")
        result[name.strip()] = Path(path.strip())
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", action="append", required=True, help="named SQLite store as NAME=PATH")
    args = parser.parse_args(argv)
    try:
        report = inspect_databases(_databases(args.database))
    except (OSError, ValueError, KemsPersistenceError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "healthy" else 2


if __name__ == "__main__":
    raise SystemExit(main())
