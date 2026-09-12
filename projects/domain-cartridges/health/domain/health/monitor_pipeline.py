"""Monitoring pipeline: daily health score, anomaly detection, intervention cards.

Deterministic local computation only.  No diagnosis is ever produced: findings
are structured deviations and the card carries suggested questions for a
doctor plus a rule-based `needs_doctor_visit` hint.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime

from .vitals import (
    METRICS,
    SCORED_METRICS,
    Ledger,
    VitalReading,
    build_ledger,
    personal_baseline,
    ref_range_status,
)

SCORE_WEIGHTS = {"hr_rest": 0.40, "sleep_hours": 0.35, "fasting_glucose": 0.25}

ANOMALY_Z = 2.0
ANOMALY_MIN_DAYS = 2
SPIKE_Z = 3.0

# Consecutive anomaly days (or any spike) that suggest a doctor visit.
VISIT_ANOMALY_DAYS = 3

DOCTOR_QUESTIONS: dict[str, list[str]] = {
    "hr_rest": [
        "最近静息心率持续偏离个人基线，是否需要复查心电图或动态心电（Holter）？",
        "目前用药/咖啡因/运动习惯是否有变化需要告知医生？",
    ],
    "sleep_hours": [
        "睡眠时长连续不足，是否需要评估睡眠呼吸暂停或失眠的门诊检查？",
        "是否需要记录一周睡眠日记供医生参考？",
    ],
    "fasting_glucose": [
        "空腹血糖偏离基线，是否需要复查糖化血红蛋白（HbA1c）？",
        "近期饮食/体重变化是否需要一并告知医生？",
    ],
}

REF_NOTE = "参考区间为通用成人区间，非个体医嘱；本卡不含诊断结论。"


@dataclass
class DayScore:
    date: str
    score: float  # 0-100
    status: str  # ok | partial | unmeasured
    detail: dict[str, dict[str, object]]


@dataclass
class Finding:
    metric: str
    kind: str  # anomaly | spike
    days: list[str]
    peak_z: float
    summary: str


@dataclass
class InterventionCard:
    generated_at: str
    findings: list[Finding]
    needs_doctor_visit: bool
    suggested_questions: list[str]
    disclaimer: str = REF_NOTE


def _metric_subscore(metric: str, value: float, ledger: Ledger, date: str) -> tuple[float, dict[str, object]]:
    base = personal_baseline(ledger, metric, date)
    if base.status == "ok":
        z = abs(base.z(value))
        sub = max(0.0, 100.0 - 10.0 * z * z)
        return sub, {"mode": "personal", "z": round(z, 2), "baseline_n": base.n}
    pos = ref_range_status(metric, value)
    if pos == "in_ref":
        return 100.0, {"mode": "reference", "position": pos}
    spec = METRICS[metric]
    lo = float(spec["ref_lo"])
    hi = float(spec["ref_hi"])
    span = max(hi - lo, 1e-6)
    dist = (lo - value) / span if pos == "below_ref" else (value - hi) / span
    sub = max(0.0, 100.0 - 50.0 * dist)
    return sub, {"mode": "reference", "position": pos}


def daily_health_score(date: str, ledger: Ledger) -> DayScore:
    parts: dict[str, dict[str, object]] = {}
    total = 0.0
    weight = 0.0
    for metric in SCORED_METRICS:
        reading = ledger.get(date, metric)
        if reading is None:
            parts[metric] = {"status": "unmeasured"}
            continue
        sub, info = _metric_subscore(metric, reading.value, ledger, date)
        w = SCORE_WEIGHTS[metric]
        parts[metric] = {"status": "measured", "value": reading.value, **info, "subscore": round(sub, 1)}
        total += w * sub
        weight += w
    if weight <= 0:
        return DayScore(date, 0.0, "unmeasured", parts)
    score = round(total / weight, 1)
    status = "ok" if weight >= 0.99 else "partial"
    return DayScore(date, score, status, parts)


def _day_z(metric: str, date: str, ledger: Ledger, exclude: tuple[str, ...] = ()) -> float:
    reading = ledger.get(date, metric)
    if reading is None:
        return 0.0
    base = personal_baseline(ledger, metric, date, exclude)
    return abs(base.z(reading.value))


def _detect_pass(ledger: Ledger, upto: str, exclude: tuple[str, ...]) -> list[Finding]:
    dates = [d for d in ledger.sorted_dates() if d <= upto]
    findings: list[Finding] = []
    for metric in SCORED_METRICS:
        zs = {d: _day_z(metric, d, ledger, exclude) for d in dates}
        # spike: single day extreme (also counts toward anomaly runs below)
        for d in dates:
            if zs[d] >= SPIKE_Z:
                findings.append(
                    Finding(
                        metric, "spike", [d], round(zs[d], 2),
                        f"{metric} 在 {d} 单日极端偏离 (z={zs[d]:.1f})",
                    )
                )
        # anomaly: consecutive run above ANOMALY_Z (spike days included —
        # an extreme day must not fragment its neighbours' run)
        run: list[str] = []
        for d in dates:
            if zs[d] >= ANOMALY_Z:
                run.append(d)
            else:
                if len(run) >= ANOMALY_MIN_DAYS:
                    peak = max(zs[x] for x in run)
                    findings.append(
                        Finding(
                            metric, "anomaly", list(run), round(peak, 2),
                            f"{metric} 连续 {len(run)} 天偏离基线 ({run[0]}~{run[-1]})",
                        )
                    )
                run = []
        if len(run) >= ANOMALY_MIN_DAYS:
            peak = max(zs[x] for x in run)
            findings.append(
                Finding(
                    metric, "anomaly", list(run), round(peak, 2),
                    f"{metric} 连续 {len(run)} 天偏离基线 ({run[0]}~{run[-1]})",
                )
            )
    return findings


def detect_anomalies(ledger: Ledger, upto: str) -> list[Finding]:
    """Two-pass detection: pass 1 flags extremes; pass 2 re-judges every day
    against baselines that exclude pass-1 flagged days (robust baseline)."""
    first = _detect_pass(ledger, upto, ())
    flagged: set[str] = set()
    for f in first:
        flagged.update(f.days)
    if not flagged:
        return first
    return _detect_pass(ledger, upto, tuple(sorted(flagged)))


def _consecutive_tail(days: list[str]) -> int:
    if not days:
        return 0
    ordered = sorted(days)
    tail = 1
    for a, b in zip(reversed(ordered[:-1]), reversed(ordered)):
        from datetime import date as _date

        da = _date.fromisoformat(a)
        db = _date.fromisoformat(b)
        if (db - da).days == 1:
            tail += 1
        else:
            break
    return tail


def build_intervention_card(findings: list[Finding]) -> InterventionCard | None:
    """Synchronously build the card (same execution — the 5-minute SLA)."""
    if not findings:
        return None
    any_spike = any(f.kind == "spike" for f in findings)
    anomaly_days: set[str] = set()
    for f in findings:
        if f.kind == "anomaly":
            anomaly_days.update(f.days)
    needs_visit = any_spike or _consecutive_tail(sorted(anomaly_days)) >= VISIT_ANOMALY_DAYS
    questions: list[str] = []
    for f in findings:
        for q in DOCTOR_QUESTIONS.get(f.metric, []):
            if q not in questions:
                questions.append(q)
    return InterventionCard(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        findings=findings,
        needs_doctor_visit=needs_visit,
        suggested_questions=questions,
    )


def run_daily(date: str, ledger: Ledger) -> dict[str, object]:
    score = daily_health_score(date, ledger)
    findings = detect_anomalies(ledger, date)
    card = build_intervention_card([f for f in findings if date in f.days])
    return {
        "date": date,
        "score": asdict(score),
        "active_findings": [asdict(f) for f in findings if date in f.days],
        "intervention_card": asdict(card) if card else None,
    }


def _load_ledger_jsonl(path: str) -> Ledger:
    readings: list[VitalReading] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            readings.append(
                VitalReading(obj["date"], obj["metric"], float(obj["value"]), obj.get("source", "manual"))
            )
    return build_ledger(readings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="健康监测每日汇总 (本地确定性)")
    parser.add_argument("--daily", action="store_true")
    parser.add_argument("--date", required=True)
    parser.add_argument("--ledger", required=True)
    args = parser.parse_args(argv)
    ledger = _load_ledger_jsonl(args.ledger)
    print(json.dumps(run_daily(args.date, ledger), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
