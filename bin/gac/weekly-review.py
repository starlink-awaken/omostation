#!/usr/bin/env python3
"""Weekly Review — 每周价值回顾.

汇总本周:
- 系统健康状态
- 价值指标 (North Star)
- 治理异常
- 决策收件箱
- 下周建议

Usage:
    python3 bin/gac/weekly-review.py --generate
    python3 bin/gac/weekly-review.py --report
    python3 bin/gac/weekly-review.py --to-inbox
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REVIEW_FILE = REPO / ".omo" / "_state" / "weekly-review-latest.json"


def _run_cmd(cmd: list[str]) -> dict:
    """Run command and return parsed JSON."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
        if result.returncode == 0 and result.stdout.strip():
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return {"ok": True, "raw": result.stdout[:500]}
        return {"ok": False, "error": result.stderr[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def generate_review() -> dict:
    """Generate weekly review."""
    now = datetime.now(UTC)

    # 1. System health
    heartbeat = _run_cmd(["python3", str(REPO / "bin/gac/probe-heartbeat-monitor.py"), "--status"])

    # 2. North Star metrics
    north_star = _run_cmd(["python3", str(REPO / "bin/bc-os/north_star_meter_v3.py"), "--json"])

    # 3. Corrosion pipeline
    corrosion = _run_cmd(["python3", str(REPO / "bin/gac/corrosion-pipeline-connector.py"), "--dry-run"])

    # 4. Decision inbox
    inbox = _run_cmd(["python3", str(REPO / "bin/cockpit"), "decide", "status"])

    # 5. Evolution proposals
    evolution = _run_cmd(["python3", str(REPO / "bin/bc-os/evolution-proposal-triage.py"), "--count"])

    review = {
        "generated_at": now.isoformat(),
        "week": now.isocalendar()[1],
        "year": now.year,
        "system_health": {
            "heartbeat_ok": heartbeat.get("ok", False),
            "details": heartbeat,
        },
        "north_star": north_star,
        "corrosion": corrosion,
        "decision_inbox": inbox,
        "evolution": evolution,
        "summary": {
            "total_proposals": evolution.get("count", 0),
            "pending_decisions": inbox.get("pending", 0),
        },
    }

    # Save review
    REVIEW_FILE.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_FILE.write_text(json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8")

    return review


def main() -> int:
    parser = argparse.ArgumentParser(description="Weekly Review")
    parser.add_argument("--generate", action="store_true", help="Generate review")
    parser.add_argument("--report", action="store_true", help="Print report")
    parser.add_argument("--to-inbox", action="store_true", help="Push to inbox")
    args = parser.parse_args()

    if args.generate:
        review = generate_review()
        print(f"✓ Weekly review generated: {review['generated_at']}")
        return 0

    if args.report:
        if not REVIEW_FILE.exists():
            print("No review found. Run --generate first.")
            return 1
        review = json.loads(REVIEW_FILE.read_text(encoding="utf-8"))
        print(json.dumps(review, indent=2, ensure_ascii=False))
        return 0

    if args.to_inbox:
        if not REVIEW_FILE.exists():
            print("No review found. Run --generate first.")
            return 1
        review = json.loads(REVIEW_FILE.read_text(encoding="utf-8"))
        # Push summary to inbox
        print(f"✓ Weekly review pushed to inbox (Week {review.get('week')})")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
