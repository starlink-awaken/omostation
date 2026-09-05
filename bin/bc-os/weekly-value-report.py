#!/usr/bin/env python3
"""Weekly Value Report — 周度价值证明报告 (BET-Y1Q4-T4-03 主入口 + 旧 weekly-review).

本 BET 在原有 weekly-review 报告基础上追加 weekly adoption-falsification snapshot:
  - signals_count: 真实外部信号数
  - accepted_by_principal: 本人采纳数
  - weekly_adoption_rate + status (red/amber/green/unmeasured)
  - falsification_risk (VISION 12-week x 3-accept 目标进度)

用法:
    python3 bin/bc-os/weekly-value-report.py --json
    python3 bin/bc-os/weekly-value-report.py --week 2026-W36 --json
    python3 bin/bc-os/weekly-value-report.py --append  # 追加到 jsonl
    python3 bin/bc-os/weekly-value-report.py           # 输出 weekly-review.json
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

WS_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_DIR = WS_ROOT / ".omo" / "state"
REPORT_FILE = STATE_DIR / "weekly-review.json"

# Weekly adoption-falsification snapshot (BET-Y1Q4-T4-03)
DEFAULT_EVENT_LEDGER = WS_ROOT / "runtime" / "omo" / "event-ledger.sqlite3"
SNAPSHOT_LOG = WS_ROOT / "docs" / "reports" / "weekly-value-snapshots.jsonl"
SNAPSHOT_SCHEMA = "weekly-value-snapshot/v1"
THRESHOLD_GREEN = 3
CONSECUTIVE_WEEKS_TARGET = 12


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _iso_week_bounds(week_key: str | None = None) -> tuple[str, str, str]:
    if week_key:
        year, week = week_key.split("-W")
        monday = datetime.strptime(f"{year}-W{week}-1", "%Y-W%W-%w").replace(tzinfo=UTC)
        week_iso = week_key
    else:
        today = datetime.now(UTC)
        monday = today - timedelta(days=today.weekday())
        year, week, _ = today.iscalender() if hasattr(today, "iscalender") else today.isocalendar()
        week_iso = f"{year}-W{week:02d}"
    end = monday + timedelta(days=7)
    return (
        week_iso,
        monday.isoformat().replace("+00:00", "Z"),
        end.isoformat().replace("+00:00", "Z"),
    )


def _query_event_ledger(
    db_path: Path,
    window_start: str,
    window_end: str,
) -> tuple[int, int, list[str]]:
    import sqlite3
    blockers: list[str] = []
    if not db_path.is_file():
        blockers.append("event-ledger-missing")
        return 0, 0, blockers
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        blockers.append(f"ledger-open-failed:{exc}")
        return 0, 0, blockers

    signals = 0
    accepted = 0
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cur.fetchall()}
        if "signal_event" in tables:
            cur.execute(
                "SELECT COUNT(*) FROM signal_event WHERE timestamp >= ? AND timestamp < ?",
                (window_start, window_end),
            )
            signals = cur.fetchone()[0] or 0
        elif "events" in tables:
            cur.execute(
                "SELECT COUNT(*) FROM events WHERE type='signal.ingested' AND timestamp >= ? AND timestamp < ?",
                (window_start, window_end),
            )
            signals = cur.fetchone()[0] or 0
        else:
            blockers.append("ledger-no-signal-table")
        if "outcome_event" in tables:
            cur.execute(
                "SELECT COUNT(*) FROM outcome_event WHERE verdict='accept' AND binding=1 AND timestamp >= ? AND timestamp < ?",
                (window_start, window_end),
            )
            accepted = cur.fetchone()[0] or 0
        elif "events" in tables:
            cur.execute(
                "SELECT COUNT(*) FROM events WHERE type='outcome.resolved' AND verdict='accept' AND binding=1 AND timestamp >= ? AND timestamp < ?",
                (window_start, window_end),
            )
            accepted = cur.fetchone()[0] or 0
        else:
            blockers.append("ledger-no-outcome-table")
        conn.close()
    except sqlite3.Error as exc:
        blockers.append(f"ledger-query-failed:{exc}")
        conn.close()
        return 0, 0, blockers
    return signals, accepted, blockers


def _derive_weekly_status(signals: int, accepted: int) -> str:
    if signals == 0:
        return "unmeasured"
    if accepted >= THRESHOLD_GREEN:
        return "green"
    if accepted >= 1:
        return "amber"
    return "red"


def _append_snapshot(snapshot: dict[str, Any], log_path: Path = SNAPSHOT_LOG) -> Path:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n")
    return log_path


def measure_weekly_snapshot(
    *,
    db_path: Path = DEFAULT_EVENT_LEDGER,
    week_iso: str | None = None,
    append: bool = False,
) -> dict[str, Any]:
    week_key, start, end = _iso_week_bounds(week_iso)
    signals, accepted, blockers = _query_event_ledger(db_path, start, end)
    status = _derive_weekly_status(signals, accepted)
    rate = (accepted / signals) if signals > 0 else 0.0
    snapshot = {
        "schema_version": SNAPSHOT_SCHEMA,
        "week_iso": week_key,
        "window": {"start": start, "end": end},
        "signals_count": signals,
        "accepted_by_principal": accepted,
        "weekly_adoption_rate": round(rate, 4),
        "status": status,
        "falsification_risk": "insufficient_data" if status == "unmeasured" else "in_progress",
        "consecutive_qualifying_weeks": 0,
        "blockers": blockers,
        "observed_at": _utc_now_iso(),
    }
    if append:
        log = _append_snapshot(snapshot)
        snapshot["snapshot_log"] = str(log)
    return snapshot


def argparse_init() -> Any:
    """Build argparser; factored for reuse."""
    import argparse
    p = argparse.ArgumentParser(description="Weekly value report + adoption falsification meter")
    p.add_argument("--week", type=str, default=None, help="ISO week (e.g., 2026-W36)")
    p.add_argument("--json", action="store_true", help="Output JSON")
    p.add_argument("--append", action="store_true", help="Append snapshot to weekly-value-snapshots.jsonl")
    p.add_argument("--db-path", type=str, default=str(DEFAULT_EVENT_LEDGER))
    return p


def _snapshot_main(parser: Any) -> int:
    args = parser.parse_args()
    snapshot = measure_weekly_snapshot(
        db_path=Path(args.db_path),
        week_iso=args.week,
        append=args.append,
    )
    if args.json:
        print(json.dumps(snapshot, indent=2, ensure_ascii=False))
    else:
        status = snapshot["status"]
        print(f"week {snapshot['week_iso']}: status={status.upper()} signals={snapshot['signals_count']} accepted={snapshot['accepted_by_principal']} rate={snapshot['weekly_adoption_rate']:.2%}")
        print(f"  falsification_risk: {snapshot['falsification_risk']}")
        if snapshot["blockers"]:
            print(f"  blockers: {', '.join(snapshot['blockers'])}")
        print(f"  window: {snapshot['window']['start'][:10]} .. {snapshot['window']['end'][:10]}")
    return 0


def _now() -> datetime:
    return datetime.now(UTC)


def _week_id(dt: datetime) -> str:
    """Generate week identifier (YYYY-WNN)."""
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def run_north_star(window_days: int = 30) -> dict:
    """Run north_star v3 and return results."""
    try:
        result = subprocess.run(
            [sys.executable, str(WS_ROOT / "bin" / "bc-os" / "north_star_meter_v3.py"),
             "--json", "--window", str(window_days)],
            capture_output=True, text=True, timeout=60, check=False,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return {}


def get_bet_status() -> dict:
    """Get BET ledger status."""
    try:
        result = subprocess.run(
            [sys.executable, str(WS_ROOT / "bin" / "plan" / "bet-ledger.py"), "status"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        if result.returncode == 0:
            output = result.stdout
            done_m = __import__('re').search(r'done\s+(\d+)', output)
            total_m = __import__('re').search(r'总 bet:\s*(\d+)', output)
            if done_m and total_m:
                return {
                    "done": int(done_m.group(1)),
                    "total": int(total_m.group(1)),
                    "pct": round(100 * int(done_m.group(1)) / int(total_m.group(1)), 1),
                }
    except (subprocess.TimeoutExpired, OSError):
        pass
    return {}


def load_previous_report() -> dict | None:
    """Load previous week's report for trend analysis."""
    if REPORT_FILE.exists():
        try:
            return json.loads(REPORT_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return None


def generate_report() -> dict:
    """Generate weekly value report."""
    now = _now()
    week_id = _week_id(now)

    # 1. Collect current data
    north_star = run_north_star(window_days=30)
    bet_status = get_bet_status()
    previous = load_previous_report()

    # 2. Build report
    report = {
        "schema": "weekly-value-report/v1",
        "week_id": week_id,
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "north_star": north_star,
        "bet_status": bet_status,
    }

    # 3. Trend analysis (if previous report exists)
    if previous:
        prev_a = previous.get("north_star", {}).get("axes", {}).get("A", {}).get("total_hours_saved", 0)
        curr_a = north_star.get("axes", {}).get("A", {}).get("total_hours_saved", 0)
        report["trends"] = {
            "hours_saved_delta": round(curr_a - prev_a, 1),
            "hours_saved_pct_change": round(100 * (curr_a - prev_a) / prev_a, 1) if prev_a > 0 else 0,
        }

    # 4. Recommendations
    recommendations = []
    a_score = north_star.get("axes", {}).get("A", {}).get("score", 0)
    b_score = north_star.get("axes", {}).get("B", {}).get("score", 0)
    e_score = north_star.get("axes", {}).get("E", {}).get("score", 0)

    if a_score < 60:
        recommendations.append("A 轴时间节省不足: 增加自动化 cron 覆盖率")
    if b_score < 50:
        recommendations.append("B 轴决策吞吐不足: 增加 cockpit decide 使用频率")
    if e_score < 70:
        recommendations.append("E 轴决策质量不足: 增加 P0/P1 决策的验证覆盖")
    if not recommendations:
        recommendations.append("各指标健康: 继续保持当前运营节奏")

    report["recommendations"] = recommendations

    # 5. Summary
    report["summary"] = {
        "status": north_star.get("status", "unknown"),
        "composite_score": north_star.get("composite", {}).get("score", 0),
        "composite_5axis": north_star.get("composite_5axis", {}).get("score", 0),
        "hours_saved_30d": north_star.get("axes", {}).get("A", {}).get("total_hours_saved", 0),
        "decisions_30d": north_star.get("axes", {}).get("B", {}).get("data", {}).get("decisions_30d", 0),
        "bet_done_pct": bet_status.get("pct", 0),
        "knowledge_events": north_star.get("axes", {}).get("D", {}).get("data", {}).get("total", 0),
        "decision_quality": north_star.get("axes", {}).get("E", {}).get("data", {}).get("adoption_ratio", 0.0),
    }

    return report


def main():
    parser_init = argparse_init()
    if "--json" in sys.argv or "--append" in sys.argv or "--week" in sys.argv:
        return _snapshot_main(parser_init)

    report = generate_report()

    # Save report
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    week_id = report["week_id"]
    report_path = STATE_DIR / f"weekly-review-{week_id}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    # Also save as latest
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    # Output
    if "--json" in sys.argv:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        s = report["summary"]
        print(f"Weekly Value Report — {report['week_id']}")
        print(f"  Status: {s['status'].upper()}")
        print(f"  Composite Score: {s['composite_score']}/100")
        print(f"  5-axis Advisory: {s.get('composite_5axis', 'N/A')}/100")
        print(f"  Hours Saved (30d): {s['hours_saved_30d']}h")
        print(f"  Decisions (30d): {s['decisions_30d']}")
        print(f"  BET Done: {s['bet_done_pct']}%")
        print(f"  Knowledge Events: {s.get('knowledge_events', 0)}")
        print(f"  Decision Quality: {s.get('decision_quality', 0):.0%}")
        if report.get("trends"):
            d = report["trends"]["hours_saved_delta"]
            sign = "+" if d >= 0 else ""
            print(f"  Trend: {sign}{d}h vs last week")
        if report.get("recommendations"):
            print("  Recommendations:")
            for r in report["recommendations"]:
                print(f"    - {r}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
