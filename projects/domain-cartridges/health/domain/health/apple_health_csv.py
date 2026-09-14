"""Apple Health manual-export CSV adapter (local parse only, no device/API calls).

Import contract — columns: startDate, type, value, unit, detail

  HKQuantityTypeIdentifierHeartRate        value=numeric bpm (daily min ≈ rest)
  HKCategoryTypeIdentifierSleepAnalysis   value=numeric hours,
                                          detail=segment label; only asleep*
                                          segments are summed
  HKQuantityTypeIdentifierBloodGlucose    value=numeric mmol/L (earliest wins)

Unknown types are skipped and counted (never abort the import).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass

from .vitals import VitalReading

HR_TYPE = "HKQuantityTypeIdentifierHeartRate"
SLEEP_TYPE = "HKCategoryTypeIdentifierSleepAnalysis"
GLUCOSE_TYPE = "HKQuantityTypeIdentifierBloodGlucose"

_ASLEEP_PREFIX = "asleep"


@dataclass
class ImportReport:
    readings: list[VitalReading]
    rows_seen: int
    rows_skipped_unknown_type: int
    rows_skipped_bad_value: int


def _to_float(raw: str | None) -> float | None:
    try:
        return float((raw or "").strip())
    except (TypeError, ValueError):
        return None


def import_apple_health_csv(path: str) -> ImportReport:
    hr_min: dict[str, float] = {}
    sleep_sum: dict[str, float] = {}
    glucose_first: dict[str, tuple[str, float]] = {}
    seen = skipped_type = skipped_bad = 0

    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            seen += 1
            rtype = (row.get("type") or "").strip()
            start = (row.get("startDate") or "").strip()
            day = start[:10]
            if len(day) != 10:
                skipped_bad += 1
                continue
            val = _to_float(row.get("value"))
            if rtype == HR_TYPE:
                if val is None:
                    skipped_bad += 1
                else:
                    hr_min[day] = val if day not in hr_min else min(hr_min[day], val)
            elif rtype == SLEEP_TYPE:
                label = (row.get("detail") or "").strip().lower()
                if val is None:
                    skipped_bad += 1
                elif label.startswith(_ASLEEP_PREFIX):
                    sleep_sum[day] = sleep_sum.get(day, 0.0) + val
                # in-bed/awake segments: recognized, intentionally ignored
            elif rtype == GLUCOSE_TYPE:
                if val is None:
                    skipped_bad += 1
                else:
                    prev = glucose_first.get(day)
                    if prev is None or start < prev[0]:
                        glucose_first[day] = (start, val)
            else:
                skipped_type += 1

    readings: list[VitalReading] = []
    for day, val in sorted(hr_min.items()):
        readings.append(VitalReading(day, "hr_rest", val, "apple_health_csv"))
    for day, val in sorted(sleep_sum.items()):
        readings.append(VitalReading(day, "sleep_hours", round(val, 2), "apple_health_csv"))
    for day, (_, val) in sorted(glucose_first.items()):
        readings.append(VitalReading(day, "fasting_glucose", val, "apple_health_csv"))
    return ImportReport(readings, seen, skipped_type, skipped_bad)
