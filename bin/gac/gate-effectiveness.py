#!/usr/bin/env python3
"""Gate effectiveness tool (ADR-0384 D3): meta-meta governance measurement.

Read `.omo/_knowledge/governance-history.jsonl` and compute per-check
fire history → emit a ranked report so we can ask "which gates are doing
real work vs which are decorative".

Data source: each event has a `checks: [{category, name, score, severity}]`
list. severity ∈ {ok, warn, error, critical}.

effectiveness_score heuristic:
  score = (warn+error+critical fires / total runs) × log(1 + distinctness × 10)
  - 0 fires → 0  (useless gate, candidate for retirement)
  - high fires but low distinctness → capped (noisy gate)
  - high fires + high distinctness → strong gate

Usage:
  python3 bin/gac/gate-effectiveness.py                # top 10 + bottom 10 table
  python3 bin/gac/gate-effectiveness.py --json        # full per-gate list
  python3 bin/gac/gate-effectiveness.py --since 30d   # window filter
  python3 bin/gac/gate-effectiveness.py --retire-threshold 5  # suggest retiring
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path


HISTORY = Path(".omo/_knowledge/governance-history.jsonl")


def load_events(history: Path, since: str | None = None) -> list[dict]:
    if not history.exists():
        return []
    cutoff = None
    if since:
        unit = since[-1]
        n = int(since[:-1])
        now = datetime.now(timezone.utc)
        cutoff = now - (timedelta(days=n) if unit == "d" else timedelta(hours=n))
    events = []
    for line in history.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = e.get("timestamp")
        if cutoff and ts:
            try:
                if datetime.fromisoformat(ts.replace("Z", "+00:00")) < cutoff:
                    continue
            except ValueError:
                pass
        events.append(e)
    return events


def build_check_stats(events: list[dict]) -> list[dict]:
    """Build per-check aggregates from event list."""
    by_check: dict[str, dict] = {}
    for e in events:
        ts = e.get("timestamp", "")
        for c in (e.get("checks") or []):
            name = c.get("name", "?")
            sev = c.get("severity", "ok")
            stats = by_check.setdefault(
                name,
                {
                    "name": name,
                    "category": c.get("category", ""),
                    "total": 0,
                    "fires": 0,
                    "severity_counts": Counter(),
                    "scores": [],
                    "last_fired_at": None,
                },
            )
            stats["total"] += 1
            stats["severity_counts"][sev] += 1
            stats["scores"].append(c.get("score", 0))
            if sev != "ok":
                stats["fires"] += 1
                if ts and (stats["last_fired_at"] is None or ts > stats["last_fired_at"]):
                    stats["last_fired_at"] = ts
    # finalize: score + recommendation
    out = []
    for stats in by_check.values():
        total = stats["total"]
        fires = stats["fires"]
        distinct = sum(1 for v in stats["severity_counts"].values() if v > 0)
        if total == 0:
            score = 0.0
        else:
            fire_rate = fires / total
            score = fire_rate * math.log1p(distinct * 10)
        avg_score = sum(stats["scores"]) / len(stats["scores"]) if stats["scores"] else 0
        if fires == 0 and total >= 20:
            verdict = "RETIRE"  # never fires over large sample
        elif score >= 0.5 and fires >= 10:
            verdict = "ACTIVE"
        elif score >= 0.3:
            verdict = "MODERATE"
        elif fires > 0:
            verdict = "WEAK"
        else:
            verdict = "NEW"  # < 20 samples, no verdict yet
        out.append(
            {
                **stats,
                "distinct_severities": distinct,
                "fire_rate": round(fires / total, 4) if total else 0,
                "effectiveness_score": round(score, 3),
                "avg_score": round(avg_score, 1),
                "verdict": verdict,
            }
        )
    out.sort(key=lambda x: -x["effectiveness_score"])
    return out


def print_table(stats: list[dict]) -> None:
    print(
        f"{'check':30} {'verdict':8} {'n':>5} {'fires':>5} {'rate':>6} "
        f"{'distinct':>9} {'score':>7} {'last_fired':>22}"
    )
    print("-" * 100)
    for s in stats:
        print(
            f"{s['name']:30} {s['verdict']:8} {s['total']:>5} {s['fires']:>5} "
            f"{s['fire_rate']:>6.1%} {s['distinct_severities']:>9} "
            f"{s['effectiveness_score']:>7.2f} {(s['last_fired_at'] or '-'):>22}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON instead of table")
    parser.add_argument("--since", type=str, default="", help="window: 30d/24h (default: all-time)")
    parser.add_argument(
        "--retire-threshold",
        type=int,
        default=20,
        help="min total runs before RETIRE verdict (default 20)",
    )
    args = parser.parse_args()

    events = load_events(HISTORY, since=args.since)
    stats = build_check_stats(events)

    if args.json:
        print(json.dumps({"events_loaded": len(events), "checks": stats}, ensure_ascii=False, indent=2))
        return 0

    print(f"loaded {len(events)} audit events; {len(stats)} distinct checks\n")
    print_table(stats)

    # retirement suggestions
    retire = [s for s in stats if s["verdict"] == "RETIRE"]
    weak = [s for s in stats if s["verdict"] == "WEAK"]
    if retire or weak:
        print("\n退役建议:")
        for s in retire:
            print(f"  - RETIRE {s['name']}: {s['total']} runs, 0 fires (>{args.retire_threshold} samples)")
        for s in weak:
            print(f"  - WEAK   {s['name']}: {s['fires']}/{s['total']} fires, score={s['effectiveness_score']:.2f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
