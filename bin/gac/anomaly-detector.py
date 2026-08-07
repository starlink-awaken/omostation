#!/usr/bin/env python3
"""Anomaly Detector — scan metrics-store.jsonl and emit anomaly events.

Usage:
    python3 bin/gac/anomaly-detector.py
    python3 bin/gac/anomaly-detector.py --window 50 --z-threshold 2.0
    python3 bin/gac/anomaly-detector.py --check check-submodule-rewind --window 50
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
DEFAULT_METRICS_FILE = WORKSPACE / ".omo" / "state" / "metrics-store.jsonl"
DEFAULT_ANOMALY_FILE = WORKSPACE / ".omo" / "state" / "anomaly-events.jsonl"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_metrics(metrics_file: Path, check: str | None = None, window: int = 50) -> list[dict]:
    if not metrics_file.is_file():
        return []
    lines = metrics_file.read_text(encoding="utf-8").splitlines()
    entries = [json.loads(line) for line in lines if line.strip()]
    if check:
        entries = [e for e in entries if e.get("check") == check]
    if window > 0:
        entries = entries[-window:]
    return entries


def _compute_ewma(values: list[float], alpha: float = 0.3) -> list[float]:
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
    ewma = _compute_ewma(durations)
    for idx, e in enumerate(entries):
        dur = float(e.get("duration_ms") or 0)
        z = (dur - mean) / std
        ewma_z = (ewma[idx] - mean) / std if idx < len(ewma) else z
        if abs(z) >= z_threshold or abs(ewma_z) >= z_threshold:
            anomalies.append({
                "index": idx,
                "timestamp": e.get("timestamp"),
                "check": e.get("check"),
                "duration_ms": dur,
                "z": round(z, 3),
                "ewma_z": round(ewma_z, 3),
                "reason": e.get("reason") or "",
                "ok": e.get("ok"),
            })
    return anomalies


def append_anomaly_events(anomaly_file: Path, anomalies: list[dict]) -> None:
    anomaly_file.parent.mkdir(parents=True, exist_ok=True)
    with anomaly_file.open("a", encoding="utf-8") as f:
        for a in anomalies:
            event = {
                "timestamp": now_iso(),
                "type": "anomaly",
                "check": a.get("check"),
                "duration_ms": a.get("duration_ms"),
                "z": a.get("z"),
                "ewma_z": a.get("ewma_z"),
                "reason": a.get("reason") or "",
                "ok": a.get("ok"),
            }
            f.write(json.dumps(event, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Anomaly Detector")
    parser.add_argument("--metrics-file", default=str(DEFAULT_METRICS_FILE), help="Metrics JSONL path")
    parser.add_argument("--anomaly-file", default=str(DEFAULT_ANOMALY_FILE), help="Anomaly events JSONL path")
    parser.add_argument("--window", type=int, default=50, help="Sliding window size")
    parser.add_argument("--z-threshold", type=float, default=2.0, help="Z-score threshold for anomaly")
    parser.add_argument("--check", help="Filter by check name")
    args = parser.parse_args()

    metrics_file = Path(args.metrics_file)
    anomaly_file = Path(args.anomaly_file)
    entries = _load_metrics(metrics_file, check=args.check, window=args.window)
    anomalies = detect_anomalies(entries, z_threshold=args.z_threshold)
    append_anomaly_events(anomaly_file, anomalies)

    output = {
        "metrics_entries": len(entries),
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
