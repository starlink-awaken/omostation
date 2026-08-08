#!/usr/bin/env python3
"""check-evidence-freshness: verify evidence-smoke report is recent.

Checks that the latest evidence-smoke report is within 7 days and
the score is >= 90. If no report exists, generates one.

Output:
  - exit 0 = evidence fresh and healthy
  - exit 1 = report too old, score too low, or generation failed
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = WORKSPACE / ".omo" / "_delivery" / "evidence-smoke"
MAX_AGE = timedelta(days=7)
MIN_SCORE = 90.0


def _latest_report() -> Path | None:
    """Return the path to the latest evidence-smoke JSON report."""
    if not EVIDENCE_DIR.exists():
        return None
    files = sorted(EVIDENCE_DIR.glob("*.json"), reverse=True)
    return files[0] if files else None


def _run_evidence_smoke() -> dict:
    """Run evidence-smoke and return the parsed report."""
    result = subprocess.run(
        [sys.executable, str(WORKSPACE / "bin" / "gac" / "evidence-smoke.py"), "--json"],
        cwd=str(WORKSPACE),
        capture_output=True, text=True, timeout=60,
    )
    # Parse JSON from stdout (may have non-JSON prefix)
    raw = result.stdout
    start = raw.find("{")
    if start < 0:
        return {"ok": False, "error": "no JSON in output"}
    return json.loads(raw[start:])


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report_path = _latest_report()
    now = datetime.now(timezone.utc)
    violations: list[dict] = []
    score = 0.0
    age_days = -1

    if report_path:
        mtime = datetime.fromtimestamp(report_path.stat().st_mtime, tz=timezone.utc)
        age_days = (now - mtime).days
        try:
            with open(report_path) as f:
                report = json.load(f)
            score = report.get("evidence_health_score", 0)
        except (json.JSONDecodeError, OSError):
            score = 0

        if age_days > MAX_AGE.days:
            violations.append({
                "type": "stale_report",
                "detail": f"report age {age_days}d > {MAX_AGE.days}d max",
            })
        if score < MIN_SCORE:
            violations.append({
                "type": "low_score",
                "detail": f"score {score} < {MIN_SCORE} min",
            })
    else:
        # No report exists — generate one
        report = _run_evidence_smoke()
        score = report.get("evidence_health_score", 0)
        age_days = 0
        if report.get("error"):
            violations.append({"type": "generation_failed", "detail": report["error"]})

    ok = len(violations) == 0

    if args.json:
        print(json.dumps({
            "ok": ok,
            "score": score,
            "age_days": age_days,
            "max_age_days": MAX_AGE.days,
            "violations": violations,
        }, indent=2))
    else:
        status = "PASS" if ok else "FAIL"
        print(f"check-evidence-freshness: {status} (score={score}, age={age_days}d)")
        for v in violations:
            print(f"  VIOLATION: {v['type']} — {v['detail']}")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
