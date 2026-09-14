"""Vitals ledger: readings, personal baselines, unmeasured semantics.

All computation is deterministic and local.  A missing reading is recorded as
`unmeasured` — the pipeline never interpolates or fabricates values
(circuit breaker for BET-Y2Q2-T7-03).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean, pstdev

# metric -> (unit, healthy reference interval, general adult, NON-individual
# advice; shown on cards as "参考区间，非个体医嘱").
METRICS: dict[str, dict[str, object]] = {
    "hr_rest": {"unit": "bpm", "ref_lo": 60.0, "ref_hi": 100.0},
    "sleep_hours": {"unit": "h", "ref_lo": 7.0, "ref_hi": 9.0},
    "fasting_glucose": {"unit": "mmol/L", "ref_lo": 3.9, "ref_hi": 6.1},
    "steps": {"unit": "count", "ref_lo": 0.0, "ref_hi": float("inf")},
}

SCORED_METRICS = ("hr_rest", "sleep_hours", "fasting_glucose")

BASELINE_WINDOW = 14  # rolling days
BASELINE_MIN_POINTS = 7  # below this the personal baseline is `insufficient`


@dataclass(frozen=True)
class VitalReading:
    date: str  # YYYY-MM-DD
    metric: str
    value: float
    source: str = "manual"  # manual | apple_health_csv


@dataclass
class Ledger:
    """date -> metric -> VitalReading.  Absent key == unmeasured."""

    days: dict[str, dict[str, VitalReading]] = field(default_factory=dict)

    def add(self, reading: VitalReading) -> None:
        self.days.setdefault(reading.date, {})[reading.metric] = reading

    def get(self, date: str, metric: str) -> VitalReading | None:
        return self.days.get(date, {}).get(metric)

    def sorted_dates(self) -> list[str]:
        return sorted(self.days)


def build_ledger(readings: list[VitalReading]) -> Ledger:
    ledger = Ledger()
    for r in readings:
        ledger.add(r)
    return ledger


@dataclass
class PersonalBaseline:
    metric: str
    mean: float
    stdev: float
    n: int
    status: str  # ok | insufficient

    def z(self, value: float) -> float:
        if self.status != "ok" or self.stdev <= 0:
            return 0.0
        return (value - self.mean) / self.stdev


def personal_baseline(
    ledger: Ledger, metric: str, before: str, exclude: tuple[str, ...] = ()
) -> PersonalBaseline:
    """Rolling baseline over the BASELINE_WINDOW days strictly before `before`.

    `exclude`: already-flagged days (robust baseline — extreme values must not
    inflate the mean/stdev used to judge their neighbours).
    """
    excluded = set(exclude)
    candidates = [d for d in ledger.sorted_dates() if d < before and d not in excluded][
        -BASELINE_WINDOW:
    ]
    values = [
        ledger.get(d, metric).value
        for d in candidates
        if ledger.get(d, metric) is not None
    ]
    if len(values) < BASELINE_MIN_POINTS:
        return PersonalBaseline(metric, 0.0, 0.0, len(values), "insufficient")
    mu = mean(values)
    sd = pstdev(values) or 0.0
    return PersonalBaseline(metric, mu, sd, len(values), "ok")


def ref_range_status(metric: str, value: float) -> str:
    """Fallback comparison against the general reference interval."""
    spec = METRICS[metric]
    lo = float(spec["ref_lo"])
    hi = float(spec["ref_hi"])
    if value < lo:
        return "below_ref"
    if value > hi:
        return "above_ref"
    return "in_ref"
