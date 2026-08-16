"""
Performance drift detection for local models benchmark runs.

Detects silent throughput or latency regressions (>25% drop) against
historical baseline benchmarks.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from omlxc.storage.models import BenchmarkRunRecord


@dataclass(frozen=True, slots=True)
class DriftReport:
    """Benchmark performance drift evaluation report."""

    model_id: str
    baseline_tps: float
    current_tps: float
    drift_ratio: float
    is_drifted: bool
    last_tested_at: datetime


class PerformanceDriftDetector:
    """Evaluates benchmark records against historical baselines."""

    def __init__(self, drift_threshold: float = 0.25, min_samples: int = 2) -> None:
        self._drift_threshold = drift_threshold
        self._min_samples = min_samples

    def detect(self, records: Sequence[BenchmarkRunRecord]) -> list[DriftReport]:
        """Group records by model_id and compute drift between baseline and latest run."""
        by_model: dict[str, list[BenchmarkRunRecord]] = defaultdict(list)
        for r in sorted(records, key=lambda item: item.tested_at):
            by_model[r.model_id].append(r)

        reports: list[DriftReport] = []
        for model_id, model_records in by_model.items():
            if len(model_records) < self._min_samples:
                continue

            latest = model_records[-1]
            historical = model_records[:-1]

            # Baseline is the historical average TPS
            baseline_tps = sum(r.tps for r in historical) / len(historical)
            if baseline_tps <= 0.0:
                continue

            current_tps = latest.tps
            drift_ratio = max((baseline_tps - current_tps) / baseline_tps, 0.0)
            is_drifted = drift_ratio >= self._drift_threshold

            reports.append(
                DriftReport(
                    model_id=model_id,
                    baseline_tps=round(baseline_tps, 2),
                    current_tps=round(current_tps, 2),
                    drift_ratio=round(drift_ratio, 4),
                    is_drifted=is_drifted,
                    last_tested_at=latest.tested_at or datetime.now(UTC),
                )
            )

        return reports
