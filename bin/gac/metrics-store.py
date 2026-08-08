#!/usr/bin/env python3
"""Governance Metrics Store — append-only time series for GaC check results.

Persists check execution metrics to a JSONL file for later adaptive analysis.
Default path: .omo/state/metrics-store.jsonl

Usage:
    python3 bin/gac/metrics-store.py append --check check-name --ok true --duration-ms 123
    python3 bin/gac/metrics-store.py query --check check-name --window 50
    python3 bin/gac/metrics-store.py stats --check check-name --window 50
    python3 bin/gac/metrics-store.py tail --n 20
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
DEFAULT_METRICS_FILE = WORKSPACE / ".omo" / "state" / "metrics-store.jsonl"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_metric(
    metrics_file: Path,
    check: str,
    ok: bool,
    duration_ms: int = 0,
    reason: str = "",
    metadata: dict | None = None,
) -> None:
    entry = {
        "timestamp": now_iso(),
        "check": check,
        "ok": ok,
        "duration_ms": duration_ms,
    }
    if reason:
        entry["reason"] = reason
    if metadata:
        entry["metadata"] = metadata
    with metrics_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def query_metrics(
    metrics_file: Path,
    check: str | None = None,
    window: int = 50,
    since: str | None = None,
) -> list[dict]:
    entries: list[dict] = []
    if not metrics_file.is_file():
        return entries
    lines = metrics_file.read_text(encoding="utf-8").splitlines()
    if since:
        filtered = [line for line in lines if line.strip()]
        entries = [json.loads(line) for line in filtered]
        entries = [e for e in entries if e.get("timestamp", "") >= since]
    else:
        entries = [json.loads(line) for line in lines if line.strip()]
    if check:
        entries = [e for e in entries if e.get("check") == check]
    if window > 0:
        entries = entries[-window:]
    return entries


def compute_stats(entries: list[dict]) -> dict:
    if not entries:
        return {"count": 0}
    durations = [e.get("duration_ms", 0) for e in entries if isinstance(e.get("duration_ms"), (int, float))]
    ok_count = sum(1 for e in entries if e.get("ok") is True)
    fail_count = sum(1 for e in entries if e.get("ok") is False)
    reasons: dict[str, int] = {}
    for e in entries:
        r = e.get("reason")
        if r:
            reasons[r] = reasons.get(r, 0) + 1
    stats: dict = {
        "count": len(entries),
        "ok_count": ok_count,
        "fail_count": fail_count,
        "pass_rate": ok_count / len(entries) if entries else 0.0,
        "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
        "max_duration_ms": max(durations) if durations else 0,
        "min_duration_ms": min(durations) if durations else 0,
        "reasons": reasons,
    }
    return stats


def tail_metrics(metrics_file: Path, n: int = 20) -> list[dict]:
    if not metrics_file.is_file():
        return []
    lines = metrics_file.read_text(encoding="utf-8").splitlines()
    entries = [json.loads(line) for line in lines if line.strip()]
    return entries[-n:]


def main() -> int:
    parser = argparse.ArgumentParser(description="Governance Metrics Store")
    sub = parser.add_subparsers(dest="command", required=True)

    # append
    ap = sub.add_parser("append")
    ap.add_argument("--file", default=str(DEFAULT_METRICS_FILE), help="Metrics JSONL path")
    ap.add_argument("--check", required=True)
    ap.add_argument("--ok", required=True, choices=["true", "false"])
    ap.add_argument("--duration-ms", type=int, default=0)
    ap.add_argument("--reason", default="")
    ap.add_argument("--metadata", default="")

    # query
    qp = sub.add_parser("query")
    qp.add_argument("--file", default=str(DEFAULT_METRICS_FILE), help="Metrics JSONL path")
    qp.add_argument("--check", default=None)
    qp.add_argument("--window", type=int, default=50)
    qp.add_argument("--since", default=None)

    # stats
    sp = sub.add_parser("stats")
    sp.add_argument("--file", default=str(DEFAULT_METRICS_FILE), help="Metrics JSONL path")
    sp.add_argument("--check", required=True)
    sp.add_argument("--window", type=int, default=50)

    # tail
    tp = sub.add_parser("tail")
    tp.add_argument("--file", default=str(DEFAULT_METRICS_FILE), help="Metrics JSONL path")
    tp.add_argument("--n", type=int, default=20)

    args = parser.parse_args()
    metrics_file = Path(args.file)

    if args.command == "append":
        meta = {}
        if args.metadata:
            try:
                meta = json.loads(args.metadata)
            except json.JSONDecodeError:
                meta = {"raw": args.metadata}
        append_metric(
            metrics_file,
            check=args.check,
            ok=args.ok == "true",
            duration_ms=args.duration_ms,
            reason=args.reason,
            metadata=meta or None,
        )
        print(f"appended to {metrics_file}")
        return 0

    if args.command == "query":
        entries = query_metrics(metrics_file, check=args.check, window=args.window, since=args.since)
        print(json.dumps(entries, ensure_ascii=False, indent=2))
        return 0

    if args.command == "stats":
        entries = query_metrics(metrics_file, check=args.check, window=args.window)
        stats = compute_stats(entries)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return 0

    if args.command == "tail":
        entries = tail_metrics(metrics_file, n=args.n)
        print(json.dumps(entries, ensure_ascii=False, indent=2))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
