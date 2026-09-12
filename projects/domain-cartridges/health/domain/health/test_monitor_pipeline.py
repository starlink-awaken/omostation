"""Self-test for the health monitoring pipeline (verify entry).

Run: `uv run python -m domain.health.test_monitor_pipeline` from
`projects/domain-cartridges/health/` (exit 0 = pass; CWD-independent).

Covers: seeded 30-day evaluation window (+12-day baseline run-in, 6 injected
anomaly ground-truth days), F1 calibration gate (>= 0.6, assisted 门),
daily score bounds, unmeasured semantics, synchronous intervention cards
(5-minute SLA), doctor-visit hint contrast, Apple Health CSV mapping,
and the --daily CLI entry.
"""

from __future__ import annotations

import csv
import io
import json
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

# Ensure the cartridge package is importable when invoked as a module
# (uv run python -m domain.health.test_monitor_pipeline), CWD-independent.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from .apple_health_csv import import_apple_health_csv
from .monitor_pipeline import build_intervention_card, daily_health_score, detect_anomalies, main, run_daily
from .vitals import VitalReading, build_ledger

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"PASS  {name}")
    else:
        msg = f"FAIL  {name}" + (f" — {detail}" if detail else "")
        print(msg)
        FAILURES.append(msg)


def _d(base: date, offset: int) -> str:
    return (base + timedelta(days=offset)).isoformat()


def seed_ledger() -> tuple:
    """42 days: 12-day baseline run-in + 30-day eval window (2026-08-01..30).

    Ground-truth anomaly days: 08-05/06 (sleep), 08-10/11/12 (hr), 08-20
    (glucose spike).  08-15 fully missing, 08-16 steps-only.
    """
    base = date(2026, 7, 20)
    readings: list[VitalReading] = []
    gt: set[str] = set()

    def add(day: str, metric: str, value: float) -> None:
        readings.append(VitalReading(day, metric, value, "seed"))

    for i in range(42):
        day = _d(base, i)
        hr = 62.0 + (i % 5 - 2) * 1.2  # 59.6..64.4, realistic daily spread
        sl = 7.5 + ((i % 7) - 3) * 0.25
        gl = 5.2 + ((i % 5) - 2) * 0.12
        if day in ("2026-08-05", "2026-08-06"):
            sl = 4.3 if day.endswith("05") else 4.5
            gt.add(day)
        if day in ("2026-08-10", "2026-08-11", "2026-08-12"):
            hr = 98.0 if day.endswith("10") else (102.0 if day.endswith("11") else 99.0)
            gt.add(day)
        if day == "2026-08-20":
            gl = 9.8
            gt.add(day)
        if day == "2026-08-15":
            continue  # fully unmeasured
        add(day, "hr_rest", hr)
        add(day, "sleep_hours", round(sl, 2))
        add(day, "fasting_glucose", round(gl, 2))
        add(day, "steps", 7000.0 + (i % 7) * 100)
        if day == "2026-08-16":
            # steps-only: drop scored metrics to simulate partial capture
            readings[:] = [r for r in readings if not (r.date == day and r.metric != "steps")]
    return build_ledger(readings), gt


def test_calibration() -> None:
    ledger, gt = seed_ledger()
    assert len(gt) == 6, f"seed must carry 6 GT days, got {len(gt)}"
    findings = detect_anomalies(ledger, "2026-08-30")
    flagged: set[str] = set()
    for f in findings:
        flagged.update(f.days)
    window = {f"2026-08-{d:02d}" for d in range(1, 31)}
    flagged &= window
    tp = len(flagged & gt)
    fp = len(flagged - gt)
    fn = len(gt - flagged)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    print(f"INFO  calibration F1={f1:.3f} (P={precision:.3f} R={recall:.3f} tp={tp} fp={fp} fn={fn})")
    check("calibration F1 >= 0.6 (assisted 门)", f1 >= 0.6, f"F1={f1:.3f} missed={sorted(gt - flagged)}")
    check("no false positives outside GT", fp == 0, f"fp={sorted(flagged - gt)}")


def test_scores_and_unmeasured() -> None:
    ledger, _ = seed_ledger()
    bad = []
    for d in [f"2026-08-{d:02d}" for d in range(1, 31)]:
        s = daily_health_score(d, ledger)
        if not (0.0 <= s.score <= 100.0):
            bad.append((d, s.score))
    check("daily scores within [0,100]", not bad, str(bad[:3]))
    s15 = daily_health_score("2026-08-15", ledger)
    check("missing day is unmeasured (no fabrication)", s15.status == "unmeasured", s15.status)
    s16 = daily_health_score("2026-08-16", ledger)
    check("steps-only day is unmeasured", s16.status == "unmeasured", s16.status)
    s01 = daily_health_score("2026-08-01", ledger)
    check("normal day scores high", s01.score >= 80.0, f"score={s01.score}")
    s11 = daily_health_score("2026-08-11", ledger)
    check("anomaly day scores materially lower than normal day", s11.score < s01.score - 15.0, f"anomaly={s11.score} normal={s01.score}")


def test_intervention_cards() -> None:
    ledger, _ = seed_ledger()
    out12 = run_daily("2026-08-12", ledger)
    card = out12["intervention_card"]
    check("card emitted on confirmed anomaly day", card is not None)
    if card:
        check("3-day run suggests doctor visit", card["needs_doctor_visit"] is True)
        check("card carries doctor questions", len(card["suggested_questions"]) >= 2)
        summaries = " | ".join(f["summary"] for f in card["findings"])
        check("findings carry no diagnosis text", "诊断" not in summaries, summaries[:120])
        check("disclaimer states no diagnosis", "不含诊断" in card["disclaimer"])
        gen = datetime.fromisoformat(card["generated_at"])
        delta = abs((datetime.now() - gen).total_seconds())
        check("card generated within 5-minute SLA", delta < 300, f"delta={delta:.1f}s")
    out06 = run_daily("2026-08-06", ledger)
    card06 = out06["intervention_card"]
    # 08-06 is itself a spike day → visit suggested per spec §3.2 (spike rule).
    check("spike day suggests visit (spike rule)", card06 is not None and card06["needs_doctor_visit"] is True)
    # Contrast: 2-day moderate run, no spike → card but no visit suggestion.
    normals = [60.0, 64.0, 61.0, 63.0, 59.0, 65.0, 62.0, 60.0, 64.0, 61.0, 63.0, 62.0, 60.0, 64.0]
    micro: list[VitalReading] = [
        VitalReading(f"2026-09-{d:02d}", "hr_rest", v, "seed")
        for d, v in zip(range(1, 15), normals)
    ] + [
        VitalReading("2026-09-15", "hr_rest", 66.5, "seed"),
        VitalReading("2026-09-16", "hr_rest", 67.0, "seed"),
    ]
    micro_ledger = build_ledger(micro)
    micro_out = run_daily("2026-09-16", micro_ledger)
    micro_card = micro_out["intervention_card"]
    check(
        "2-day moderate run: card without visit suggestion",
        micro_card is not None and micro_card["needs_doctor_visit"] is False,
        json.dumps(micro_card, ensure_ascii=False)[:200] if micro_card else "no card",
    )
    out01 = run_daily("2026-08-01", ledger)
    check("normal day emits no card", out01["intervention_card"] is None)
    check("empty findings build no card", build_intervention_card([]) is None)


def test_csv_adapter() -> None:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["startDate", "type", "value", "unit", "detail"])
    w.writerow(["2026-08-01T06:30:00", "HKQuantityTypeIdentifierHeartRate", "70", "count/min", ""])
    w.writerow(["2026-08-01T06:35:00", "HKQuantityTypeIdentifierHeartRate", "62", "count/min", ""])
    w.writerow(["2026-08-01T23:00:00", "HKCategoryTypeIdentifierSleepAnalysis", "5.5", "h", "asleepCore"])
    w.writerow(["2026-08-01T23:00:00", "HKCategoryTypeIdentifierSleepAnalysis", "2.0", "h", "inBed"])
    w.writerow(["2026-08-01T07:00:00", "HKQuantityTypeIdentifierBloodGlucose", "5.4", "mmol/L", ""])
    w.writerow(["2026-08-01T08:00:00", "HKQuantityTypeIdentifierBloodGlucose", "6.8", "mmol/L", ""])
    w.writerow(["2026-08-01T09:00:00", "HKQuantityTypeIdentifierStepCount", "100", "count", ""])
    w.writerow(["2026-08-01T10:00:00", "HKQuantityTypeIdentifierHeartRate", "bad", "count/min", ""])
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as fh:
        fh.write(buf.getvalue())
        path = fh.name
    rep = import_apple_health_csv(path)
    by_metric = {(r.date, r.metric): r.value for r in rep.readings}
    check("HR daily minimum mapped", by_metric.get(("2026-08-01", "hr_rest")) == 62.0, str(by_metric))
    check("sleep sums asleep only", by_metric.get(("2026-08-01", "sleep_hours")) == 5.5, str(by_metric))
    check("glucose earliest wins", by_metric.get(("2026-08-01", "fasting_glucose")) == 5.4, str(by_metric))
    check("unknown type skipped+counted", rep.rows_skipped_unknown_type == 1, str(rep.rows_skipped_unknown_type))
    check("bad value skipped+counted", rep.rows_skipped_bad_value == 1, str(rep.rows_skipped_bad_value))


def test_cli_daily() -> None:
    ledger, _ = seed_ledger()
    lines = [
        json.dumps({"date": d, "metric": m, "value": ledger.get(d, m).value})
        for d in ledger.sorted_dates()
        for m in ("hr_rest", "sleep_hours", "fasting_glucose")
        if ledger.get(d, m) is not None
    ]
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as fh:
        fh.write("\n".join(lines))
        path = fh.name
    rc = main(["--daily", "--date", "2026-08-12", "--ledger", path])
    check("--daily CLI exits 0", rc == 0)


def run_all() -> int:
    test_calibration()
    test_scores_and_unmeasured()
    test_intervention_cards()
    test_csv_adapter()
    test_cli_daily()
    if FAILURES:
        print(f"\n{len(FAILURES)} FAILURES")
        return 1
    print("\nALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_all())
