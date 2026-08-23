#!/usr/bin/env python3
"""rotate-history — trim old entries from health.jsonl and similar append-only logs.

Purpose:
  .omo/state/history/health.jsonl grows unbounded (one record per radar run).
  After 90 days, old records have no value. This script trims old records
  and writes back the trimmed file. Safe: atomic via tmp+rename.

Usage:
  python3 bin/gac/rotate-history.py                # default: 90 days, dry-run
  python3 bin/gac/rotate-history.py --apply        # execute
  python3 bin/gac/rotate-history.py --keep 180     # keep 180 days
  python3 bin/gac/rotate-history.py --json         # machine output

Exit codes:
  0 = success (applied or dry-run)
  1 = error
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[2]
DEFAULT_TARGETS = [
    WORKSPACE / ".omo" / "state" / "history" / "health.jsonl",
]


def _load_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _write_records(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def _trim_records(
    records: list[dict[str, Any]], keep_days: int, now: datetime
) -> list[dict[str, Any]]:
    cutoff = (now - timedelta(days=keep_days)).isoformat(timespec="seconds")
    return [r for r in records if r.get("ts", "") >= cutoff]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Execute trim")
    parser.add_argument("--keep", type=int, default=90, help="Keep last N days (default 90)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument(
        "--target",
        action="append",
        help="Additional JSONL file to trim (repeatable)",
    )
    args = parser.parse_args(argv)

    now = datetime.now(UTC)
    targets = list(DEFAULT_TARGETS)
    if args.target:
        targets.extend(Path(t) for t in args.target)

    report: list[dict[str, Any]] = []
    total_trimmed = 0

    for path in targets:
        if not path.exists():
            report.append({"path": str(path), "status": "missing"})
            continue

        records = _load_records(path)
        trimmed = _trim_records(records, args.keep, now)
        dropped = len(records) - len(trimmed)

        rec = {
            "path": str(path),
            "before_count": len(records),
            "after_count": len(trimmed),
            "dropped": dropped,
            "keep_days": args.keep,
            "cutoff": now.isoformat(timespec="seconds"),
        }
        report.append(rec)
        total_trimmed += dropped

        if args.apply and dropped > 0:
            _write_records(path, trimmed)

    summary = {
        "apply": args.apply,
        "keep_days": args.keep,
        "now": now.isoformat(timespec="seconds"),
        "targets": report,
        "total_trimmed": total_trimmed,
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        for r in report:
            if "dropped" in r:
                status = "will trim" if r["dropped"] > 0 else "ok"
                print(f"{r['path']}: {r['before_count']} → {r['after_count']} ({r['dropped']} dropped, {status})")
            else:
                print(f"{r['path']}: {r.get('status', 'unknown')}")
        print(f"\nTotal: {summary['total_trimmed']} records dropped (dry-run={not args.apply})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())