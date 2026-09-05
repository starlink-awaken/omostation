#!/usr/bin/env python3
"""Value Tracker — 价值证明闭环.

记录执行产生的价值 → 更新北极星指标 → 生成价值报告.

Usage:
    python3 bin/gac/value-tracker.py --record <minutes> [--task <task_id>]
    python3 bin/gac/value-tracker.py --report
    python3 bin/gac/value-tracker.py --update-north-star
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VALUE_LOG = REPO / ".omo" / "state" / "value-executions.json"
NORTH_STAR_INPUT = REPO / ".omo" / "state" / "north-star-input.json"


def _load_json(path: Path) -> list | dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def record_value(minutes: float, task_id: str = "", description: str = "") -> dict:
    """Record execution value."""
    log = _load_json(VALUE_LOG)
    if isinstance(log, dict):
        log = log.get("executions", [])

    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "minutes_saved": minutes,
        "task_id": task_id,
        "description": description,
        "axis": "A",  # Time savings axis
    }
    log.append(entry)
    _save_json(VALUE_LOG, log)

    return {"ok": True, "recorded": entry, "total_entries": len(log)}


def generate_report() -> dict:
    """Generate value report."""
    log = _load_json(VALUE_LOG)
    if isinstance(log, dict):
        log = log.get("executions", [])

    if not log:
        return {"ok": True, "total_minutes": 0, "entries": 0}

    total_minutes = sum(e.get("minutes_saved", 0) for e in log)
    today = datetime.now(UTC).date().isoformat()
    today_minutes = sum(
        e.get("minutes_saved", 0)
        for e in log
        if e.get("timestamp", "").startswith(today)
    )

    return {
        "ok": True,
        "total_minutes": round(total_minutes, 1),
        "today_minutes": round(today_minutes, 1),
        "entries": len(log),
        "average_minutes": round(total_minutes / len(log), 1) if log else 0,
    }


def update_north_star() -> dict:
    """Update North Star with value data."""
    report = generate_report()

    north_star_data = {
        "source": "value-tracker",
        "updated_at": datetime.now(UTC).isoformat(),
        "axis_a": {
            "total_minutes_saved": report.get("total_minutes", 0),
            "today_minutes_saved": report.get("today_minutes", 0),
            "execution_count": report.get("entries", 0),
        },
    }

    _save_json(NORTH_STAR_INPUT, north_star_data)
    return {"ok": True, "north_star": north_star_data}


def record_journey_baseline(
    *, window_days: int = 7, db_path: str = "", output: str = ""
) -> dict:
    """Record journey completion baseline as value evidence (BET-Y1Q4-T4-02).

    Wraps north_star_meter_v3.measure_journey_completion() and stores
    the baseline receipt for value-tracker evidence.
    """
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location(
        "nsm3", str(REPO / "bc-os" / "north_star_meter_v3.py")
    )
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    _measure = _mod.measure_journey_completion

    kwargs: dict = {"window_days": window_days}
    if db_path:
        from pathlib import Path as _P
        kwargs["db_path"] = _P(db_path)
    result = _measure(**kwargs)

    receipt = {
        "source": "journey-baseline",
        "recorded_at": datetime.now(UTC).isoformat(),
        "baseline": result,
    }

    if output:
        _save_json(Path(output), receipt)
        receipt["output_path"] = output

    return {"ok": True, "receipt": receipt}


def record_weekly_snapshot(
    *, week_iso: str = "", append: bool = True, db_path: str = ""
) -> dict:
    """Record weekly adoption snapshot (BET-Y1Q4-T4-03).

    Wraps bin/bc-os/weekly-value-report.py --append and returns the snapshot.
    """
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location(
        "wvr", str(REPO / "bc-os" / "weekly-value-report.py")
    )
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    kwargs: dict = {"append": append}
    if week_iso:
        kwargs["week_iso"] = week_iso
    if db_path:
        from pathlib import Path as _P
        kwargs["db_path"] = _P(db_path)
    result = _mod.measure_weekly_snapshot(**kwargs)
    return {"ok": True, "snapshot": result}


def main() -> int:
    parser = argparse.ArgumentParser(description="Value Tracker")
    parser.add_argument("--record", type=float, help="Record minutes saved")
    parser.add_argument("--task", default="", help="Task ID")
    parser.add_argument("--description", default="", help="Description")
    parser.add_argument("--report", action="store_true", help="Generate report")
    parser.add_argument("--update-north-star", action="store_true", help="Update North Star")
    parser.add_argument("--journey-baseline", action="store_true", help="Record journey completion baseline (BET-Y1Q4-T4-02)")
    parser.add_argument("--journey-window", type=int, default=7, help="Journey baseline window (days)")
    parser.add_argument("--journey-db", default="", help="Event ledger path")
    parser.add_argument("--journey-output", default="", help="Output path for baseline receipt")
    parser.add_argument("--weekly-snapshot", action="store_true", help="Record weekly adoption snapshot (BET-Y1Q4-T4-03)")
    parser.add_argument("--week", default="", help="ISO week (e.g., 2026-W36)")
    parser.add_argument("--snapshot-db", default="", help="Event ledger path")
    args = parser.parse_args()

    if args.record is not None:
        result = record_value(args.record, args.task, args.description)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.report:
        result = generate_report()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.update_north_star:
        result = update_north_star()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.journey_baseline:
        result = record_journey_baseline(
            window_days=args.journey_window,
            db_path=args.journey_db,
            output=args.journey_output,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.weekly_snapshot:
        result = record_weekly_snapshot(
            week_iso=args.week or None,
            append=True,
            db_path=args.snapshot_db,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
