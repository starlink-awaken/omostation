#!/usr/bin/env python3
"""
health-trend-predictor.py — Predict health trends from governance history.

Usage:
  uv run python3 bin/gac/health-trend-predictor.py
  uv run python3 bin/gac/health-trend-predictor.py --json
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HISTORY_FILE = REPO_ROOT / ".omo" / "_log" / "governance-history.jsonl"


def load_history() -> list:
    if not HISTORY_FILE.exists():
        return []
    entries = []
    for line in HISTORY_FILE.read_text(errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            continue
    return entries


def predict(entries: list) -> dict:
    if not entries:
        return {"status": "no_data", "message": "No history entries found"}

    # Extract health scores from entries
    health_scores = []
    for e in entries:
        if isinstance(e, dict) and "health_score" in e:
            health_scores.append(e["health_score"])

    if not health_scores:
        return {"status": "no_health_data", "message": "No health_score entries found"}

    current = health_scores[-1]
    avg_7d = sum(health_scores[-7:]) / min(len(health_scores), 7)
    avg_30d = sum(health_scores[-30:]) / min(len(health_scores), 30)

    # Simple prediction: if trend is declining, predict continued decline
    if len(health_scores) >= 3:
        recent_trend = health_scores[-1] - health_scores[-3]
        if recent_trend < -5:
            prediction_7d = max(0, current + recent_trend)
            prediction_30d = max(0, current + recent_trend * 3)
        elif recent_trend > 5:
            prediction_7d = min(100, current + recent_trend)
            prediction_30d = min(100, current + recent_trend * 3)
        else:
            prediction_7d = current
            prediction_30d = current
    else:
        prediction_7d = current
        prediction_30d = current

    return {
        "status": "ok",
        "current": current,
        "avg_7d": round(avg_7d, 1),
        "avg_30d": round(avg_30d, 1),
        "prediction_7d": round(prediction_7d, 1),
        "prediction_30d": round(prediction_30d, 1),
        "trend": "declining" if prediction_7d < current - 5 else "improving" if prediction_7d > current + 5 else "stable",
        "samples": len(health_scores),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Health trend predictor")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    entries = load_history()
    result = predict(entries)

    if args.json:
        print(json.dumps(result, indent=2))
        sys.exit(0)

    if result.get("status") != "ok":
        print(f"Prediction unavailable: {result.get('message', 'unknown')}")
        sys.exit(0)

    print("Health Trend Prediction")
    print("=" * 50)
    print(f"Current:     {result['current']}")
    print(f"7-day avg:   {result['avg_7d']}")
    print(f"30-day avg:  {result['avg_30d']}")
    print(f"Predicted 7d: {result['prediction_7d']}")
    print(f"Predicted 30d: {result['prediction_30d']}")
    print(f"Trend:       {result['trend']}")
    print(f"Samples:     {result['samples']}")
    print("=" * 50)

    if result["prediction_7d"] < 60:
        print("WARNING: Health predicted to drop below 60 in 7 days")
        print("Recommended action: Run `make state-sync` and check for stale locks")
    elif result["prediction_7d"] > 85:
        print("Health trend is positive")
    else:
        print("Health trend is stable")


if __name__ == "__main__":
    main()
