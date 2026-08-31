#!/usr/bin/env python3
"""推荐追踪器 — 记录能力推荐→采纳→反馈闭环。

用法:
    python3 bin/gac/recommendation-tracker.py --record <capability_id> --task <task_id>
    python3 bin/gac/recommendation-tracker.py --feedback <rec_id> --outcome useful
    python3 bin/gac/recommendation-tracker.py --report
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TRACK_FILE = REPO / ".omo" / "state" / "recommendation-tracker.jsonl"


def record_recommendation(capability_id: str, task_id: str = "", context: str = "") -> dict:
    """Record a recommendation made to an agent."""
    rec = {
        "id": f"rec-{int(time.time())}",
        "timestamp": datetime.now(UTC).isoformat(),
        "capability_id": capability_id,
        "task_id": task_id,
        "context": context,
        "outcome": "pending",
    }
    TRACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TRACK_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def record_feedback(rec_id: str, outcome: str) -> dict | None:
    """Record feedback for a recommendation."""
    if not TRACK_FILE.exists():
        return None

    # Read all records
    records = []
    with open(TRACK_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    # Update matching record
    updated = None
    for r in records:
        if r.get("id") == rec_id:
            r["outcome"] = outcome
            r["feedback_at"] = datetime.now(UTC).isoformat()
            updated = r
            break

    if updated:
        # Write back
        with open(TRACK_FILE, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    return updated


def generate_report() -> dict:
    """Generate recommendation effectiveness report."""
    if not TRACK_FILE.exists():
        return {"total": 0, "pending": 0, "useful": 0, "not_useful": 0, "adoption_rate": 0.0}

    records = []
    with open(TRACK_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    total = len(records)
    pending = sum(1 for r in records if r.get("outcome") == "pending")
    useful = sum(1 for r in records if r.get("outcome") == "useful")
    not_useful = sum(1 for r in records if r.get("outcome") == "not_useful")

    rated = useful + not_useful
    adoption_rate = (useful / rated * 100) if rated > 0 else 0.0

    return {
        "total": total,
        "pending": pending,
        "useful": useful,
        "not_useful": not_useful,
        "adoption_rate": round(adoption_rate, 1),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="推荐追踪器")
    parser.add_argument("--record", help="Record a recommendation (capability_id)")
    parser.add_argument("--task", default="", help="Associated task ID")
    parser.add_argument("--context", default="", help="Recommendation context")
    parser.add_argument("--feedback", help="Record feedback for rec_id")
    parser.add_argument("--outcome", choices=["useful", "not_useful"], help="Feedback outcome")
    parser.add_argument("--report", action="store_true", help="Generate report")
    args = parser.parse_args()

    if args.record:
        rec = record_recommendation(args.record, args.task, args.context)
        print(json.dumps(rec, ensure_ascii=False, indent=2))
        return 0

    if args.feedback and args.outcome:
        updated = record_feedback(args.feedback, args.outcome)
        if updated:
            print(json.dumps(updated, ensure_ascii=False, indent=2))
        else:
            print(f"Recommendation {args.feedback} not found")
            return 1
        return 0

    if args.report:
        report = generate_report()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
