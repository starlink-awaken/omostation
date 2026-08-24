#!/usr/bin/env python3
"""North Star Weekly Report — 价值度量周报."""

import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STATE_FILE = REPO / ".omo/state/north-star-weekly.jsonl"


def get_north_star_status() -> dict:
    try:
        result = subprocess.run(
            ["python3", str(REPO / "bin/bc-os/north_star_meter_v2.py"), "--json", "--principal-id", "xiamingxing"],
            cwd=REPO, capture_output=True, text=True, timeout=60,
        )
        return json.loads(result.stdout)
    except Exception as e:
        return {"error": str(e)}


def generate_report() -> dict:
    now = datetime.now(timezone.utc)
    status = get_north_star_status()
    metrics = status.get("metrics", {})
    report = {
        "timestamp": now.isoformat(),
        "week": now.isocalendar()[1],
        "year": now.isocalendar()[0],
        "principal_id": "xiamingxing",
        "readiness": status.get("readiness", "unknown"),
        "four_week_value_gate": metrics.get("four_week_value_gate", "unknown"),
        "total_episodes": metrics.get("total_episodes", 0),
        "qualifying_episodes_this_week": metrics.get("current_week_qualifying_outcomes", 0),
        "gate_gaps": metrics.get("gate_gaps", []),
    }
    target_total = 12
    report["target_total_episodes"] = target_total
    report["progress_pct"] = round(min(100, metrics.get("total_episodes", 0) / target_total * 100), 1)
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "a") as f:
        f.write(json.dumps(report, ensure_ascii=False) + "\n")
    return report


def get_trend(weeks: int = 4) -> list[dict]:
    if not STATE_FILE.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(weeks=weeks)
    records = []
    with open(STATE_FILE) as f:
        for line in f:
            try:
                record = json.loads(line.strip())
                ts = datetime.fromisoformat(record["timestamp"])
                if ts >= cutoff:
                    records.append(record)
            except Exception:
                continue
    return records


def main():
    import argparse
    parser = argparse.ArgumentParser(description="North Star Weekly Report")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--trend", action="store_true")
    args = parser.parse_args()

    if args.trend:
        records = get_trend()
        if args.json:
            print(json.dumps(records, ensure_ascii=False, indent=2))
        else:
            print("=" * 56)
            print("  North Star Trend (Last 4 weeks)")
            print("=" * 56)
            for r in records:
                print(f"  W{r.get('week', '?')}: {r.get('total_episodes', 0)} episodes, readiness={r.get('readiness', '?')}")
        return

    report = generate_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    print("=" * 56)
    print("  North Star Weekly Report")
    print("=" * 56)
    print(f"  Week: {report.get('year', '?')}-W{report.get('week', '?')}")
    print(f"  Readiness: {report.get('readiness', '?')}")
    print(f"  4-Week Gate: {report.get('four_week_value_gate', '?')}")
    print(f"  Total Episodes: {report.get('total_episodes', 0)}")
    print(f"  This Week Qualifying: {report.get('qualifying_episodes_this_week', 0)}")
    print(f"  Progress: {report.get('progress_pct', 0)}%")
    if report.get("gate_gaps"):
        print("  Gate Gaps:")
        for gap in report["gate_gaps"]:
            print(f"    - {gap}")


if __name__ == "__main__":
    sys.exit(main())
