#!/usr/bin/env python3
"""Debt Predictor — time-series trend analysis for governance debt.

Reads .omo/debt/items/*.yaml and metrics-store.jsonl to produce:
- current debt snapshot
- trend prediction (linear extrapolation)
- threshold breach warnings

Usage:
    python3 bin/gac/debt-predictor.py
    python3 bin/gac/debt-predictor.py --threshold 20 --window 30
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

WORKSPACE = Path(__file__).resolve().parents[2]
DEBT_DIR = WORKSPACE / ".omo" / "debt" / "items"
METRICS_FILE = WORKSPACE / ".omo" / "state" / "metrics-store.jsonl"
PREDICTIONS_FILE = WORKSPACE / ".omo" / "state" / "governance-predictions.yaml"


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def load_debt_items_from_dir(debt_dir: Path) -> list[dict]:
    items: list[dict] = []
    if not debt_dir.is_dir() or yaml is None:
        return items
    for path in sorted(debt_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(data, dict):
                items.append(data)
        except Exception:
            continue
    return items


def debt_snapshot(items: list[dict]) -> dict:
    total = len(items)
    by_status: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for item in items:
        status = str(item.get("status", "unknown"))
        severity = str(item.get("severity", "unknown"))
        by_status[status] = by_status.get(status, 0) + 1
        by_severity[severity] = by_severity.get(severity, 0) + 1
    return {
        "total": total,
        "by_status": by_status,
        "by_severity": by_severity,
    }


def predict_trend(metrics_file: Path, threshold: int, window: int = 30) -> dict:
    if not metrics_file.is_file():
        return {"error": "metrics-store.jsonl not found"}
    lines = metrics_file.read_text(encoding="utf-8").splitlines()
    entries = [json.loads(line) for line in lines if line.strip()]
    daily_counts: dict[str, int] = {}
    for entry in entries:
        ts = entry.get("timestamp", "")
        if len(ts) < 10:
            continue
        day = ts[:10]
        daily_counts[day] = daily_counts.get(day, 0) + 1
    if len(daily_counts) < 2:
        return {"error": "insufficient history for prediction"}
    days = sorted(daily_counts.keys())
    counts = [daily_counts[d] for d in days]
    n = len(counts)
    x_mean = sum(range(n)) / n
    y_mean = sum(counts) / n
    numerator = sum((i - x_mean) * (counts[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    if denominator == 0:
        return {"error": "no variance in daily counts"}
    slope = numerator / denominator
    intercept = y_mean - slope * x_mean
    last_idx = n - 1
    current = counts[last_idx]
    if slope <= 0:
        return {
            "current": current,
            "slope": round(slope, 4),
            "prediction": "stable_or_decreasing",
            "days_to_threshold": None,
        }
    remaining = threshold - current
    if remaining <= 0:
        days_to_threshold = 0
    else:
        days_to_threshold = remaining / slope
    predicted = intercept + slope * (last_idx + max(0, int(days_to_threshold)))
    return {
        "current": current,
        "slope": round(slope, 4),
        "intercept": round(intercept, 4),
        "threshold": threshold,
        "days_to_threshold": round(days_to_threshold, 1),
        "predicted_at_threshold": round(predicted, 1),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Debt Predictor")
    parser.add_argument("--threshold", type=int, default=20, help="Debt threshold for prediction")
    parser.add_argument("--window", type=int, default=30, help="Prediction window (days)")
    parser.add_argument("--debt-dir", default=str(DEBT_DIR), help="Debt items directory")
    parser.add_argument("--metrics-file", default=str(METRICS_FILE), help="Metrics JSONL path")
    args = parser.parse_args()

    debt_dir = Path(args.debt_dir)
    metrics_file = Path(args.metrics_file)
    items = load_debt_items_from_dir(debt_dir)
    snapshot = debt_snapshot(items)
    prediction = predict_trend(metrics_file, args.threshold, window=args.window)

    output = {
        "snapshot": snapshot,
        "prediction": prediction,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
