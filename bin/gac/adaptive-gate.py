#!/usr/bin/env python3
"""Adaptive Gate Engine — derive check-specific thresholds and anomalies from metrics history.

Reads .omo/state/metrics-store.jsonl and produces:
- recommended warn-threshold for a given check
- anomaly list for recent execution pattern changes

Usage:
    python3 bin/gac/adaptive-gate.py --check check-submodule-rewind --window 50
    python3 bin/gac/adaptive-gate.py --check check-submodule-rewind --window 50 --anomalies
    python3 bin/gac/adaptive-gate.py --summary
"""

import argparse
import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
DEFAULT_METRICS_FILE = WORKSPACE / ".omo" / "state" / "metrics-store.jsonl"


def _query_metrics(metrics_file: Path, check: str | None = None, window: int = 50) -> list[dict]:
    entries: list[dict] = []
    if not metrics_file.is_file():
        return entries
    lines = metrics_file.read_text(encoding="utf-8").splitlines()
    entries = [json.loads(line) for line in lines if line.strip()]
    if check:
        entries = [e for e in entries if e.get("check") == check]
    if window > 0:
        entries = entries[-window:]
    return entries


def compute_ewma(values: list[float], alpha: float = 0.3) -> list[float]:
    if not values:
        return []
    smoothed = [values[0]]
    for v in values[1:]:
        smoothed.append(alpha * v + (1 - alpha) * smoothed[-1])
    return smoothed


def detect_anomalies(entries: list[dict], z_threshold: float = 2.0) -> list[dict]:
    if len(entries) < 5:
        return []
    durations = [float(e.get("duration_ms") or 0) for e in entries if isinstance(e.get("duration_ms"), (int, float))]
    if not durations:
        return []
    mean = sum(durations) / len(durations)
    variance = sum((d - mean) ** 2 for d in durations) / len(durations)
    std = variance ** 0.5
    if std < 1e-9:
        return []
    anomalies = []
    ewma = compute_ewma(durations)
    for idx, e in enumerate(entries):
        dur = float(e.get("duration_ms") or 0)
        z = (dur - mean) / std
        ewma_z = (ewma[idx] - mean) / std if idx < len(ewma) else z
        if abs(z) >= z_threshold or abs(ewma_z) >= z_threshold:
            anomalies.append({
                "index": idx,
                "timestamp": e.get("timestamp"),
                "duration_ms": dur,
                "z": round(z, 3),
                "ewma_z": round(ewma_z, 3),
                "reason": e.get("reason") or "",
            })
    return anomalies


def recommend_threshold(entries: list[dict], min_threshold: int = 3) -> dict:
    ok_count = sum(1 for e in entries if e.get("ok") is True)
    fail_count = sum(1 for e in entries if e.get("ok") is False)
    pass_rate = ok_count / len(entries) if entries else 0.0
    durations = [float(e.get("duration_ms") or 0) for e in entries if isinstance(e.get("duration_ms"), (int, float))]
    mean = sum(durations) / len(durations) if durations else 0.0
    variance = sum((d - mean) ** 2 for d in durations) / len(durations) if durations else 0.0
    std = variance ** 0.5
    recommended = int(max(min_threshold, mean + 2 * std))
    return {
        "check": entries[0].get("check") if entries else "",
        "window": len(entries),
        "pass_rate": round(pass_rate, 4),
        "avg_duration_ms": round(mean, 2),
        "std_duration_ms": round(std, 2),
        "recommended_warn_threshold": recommended,
        "min_threshold": min_threshold,
    }


def summarize_all(metrics_file: Path, window: int = 50) -> list[dict]:
    if not metrics_file.is_file():
        return []
    lines = metrics_file.read_text(encoding="utf-8").splitlines()
    entries = [json.loads(line) for line in lines if line.strip()]
    by_check: dict[str, list[dict]] = {}
    for e in entries:
        by_check.setdefault(e.get("check", ""), []).append(e)
    summaries = []
    for check, items in by_check.items():
        recent = items[-window:]
        if recent:
            summaries.append(recommend_threshold(recent))
    return summaries


def main() -> int:
    parser = argparse.ArgumentParser(description="Adaptive Gate Engine")
    parser.add_argument("--file", default=str(DEFAULT_METRICS_FILE), help="Metrics JSONL path")
    parser.add_argument("--check", default="", help="Check name for single-check mode")
    parser.add_argument("--window", type=int, default=50, help="Sliding window size")
    parser.add_argument("--anomalies", action="store_true", help="Show anomalies instead of threshold recommendation")
    parser.add_argument("--summary", action="store_true", help="Summarize all checks")
    args = parser.parse_args()
    metrics_file = Path(args.file)

    if args.summary:
        data = summarize_all(metrics_file, window=args.window)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    if not args.check:
        parser.error("--check is required when --summary is not set")

    entries = _query_metrics(metrics_file, check=args.check, window=args.window)
    if not entries:
        print(json.dumps({"error": "no metrics found", "check": args.check}, ensure_ascii=False))
        return 1

    if args.anomalies:
        data = {
            "check": args.check,
            "window": len(entries),
            "anomalies": detect_anomalies(entries),
        }
    else:
        data = recommend_threshold(entries)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
