#!/usr/bin/env python3
"""Weekly Value Report — 自动化周度价值证明报告.

生成 weekly-review.json:
  - A 轴时间节省 (north_star v3)
  - B 轴决策吞吐
  - C 轴项目推进力 (BET done rate)
  - 趋势分析 (vs 上周)
  - 改进建议

输出: .omo/state/weekly-review-{YYYY-WNN}.json
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
