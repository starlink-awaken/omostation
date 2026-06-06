"""Engine performance tracking, metrics aggregation, and latency monitoring.

Maps to TS source: agentmesh/packages/engine/src/dsl/performance.ts

Provides:
  - PerformanceBenchmarker: generic function measurement with statistics
  - PerformanceBaseline / PerformanceRegressionDetector: regression detection
  - MetricsAggregator: real-time aggregation of operation latencies
"""

from __future__ import annotations

import math
import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class BenchmarkResult:
    """Statistics from a single benchmark run."""
    name: str
    iterations: int
    total_time_ms: float
    avg_time_ms: float
    min_time_ms: float
    max_time_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    std_dev: float
    coefficient_of_variation: float
    memory_before_mb: float = 0.0
    memory_after_mb: float = 0.0
    memory_delta_mb: float = 0.0
    timestamp: float = 0.0


@dataclass
class ComparisonResult:
    """Result of comparing two benchmark runs."""
    result1: BenchmarkResult
    result2: BenchmarkResult
    improvement_pct: float
    significant: bool
    test_method: str = "welch-t-test"


@dataclass
class PerformanceBaseline:
    """Historical baseline for regression detection."""
    name: str
    version: str
    metrics: dict[str, float]
    timestamp: float = 0.0
    environment: dict[str, str] = field(default_factory=dict)


@dataclass
class RegressionEntry:
    """A single regression or improvement finding."""
    metric: str
    baseline: float
    current: float
    change_pct: float


@dataclass
class RegressionResult:
    """Result of regression detection."""
    has_regression: bool
    regressions: list[RegressionEntry] = field(default_factory=list)
    improvements: list[RegressionEntry] = field(default_factory=list)


# ---------------------------------------------------------------------------
# MetricsAggregator
# ---------------------------------------------------------------------------


class MetricsAggregator:
    """Real-time aggregation of operation latencies and counts."""

    def __init__(self) -> None:
        self._latencies: dict[str, list[float]] = {}
        self._counts: dict[str, int] = {}
        self._errors: dict[str, int] = {}

    def record(self, operation: str, latency_ms: float, error: bool = False) -> None:
        self._latencies.setdefault(operation, []).append(latency_ms)
        self._counts[operation] = self._counts.get(operation, 0) + 1
        if error:
            self._errors[operation] = self._errors.get(operation, 0) + 1

    def stats(self, operation: str) -> dict[str, float] | None:
        samples = self._latencies.get(operation)
        if not samples:
            return None
        s = sorted(samples)
        n = len(s)
        mean = sum(s) / n
        p50 = self._percentile(s, 50)
        p95 = self._percentile(s, 95)
        p99 = self._percentile(s, 99)
        std = statistics.stdev(s) if n > 1 else 0.0
        return {
            "count": n,
            "avg_ms": mean,
            "min_ms": s[0],
            "max_ms": s[-1],
            "p50_ms": p50,
            "p95_ms": p95,
            "p99_ms": p99,
            "std_dev": std,
            "errors": self._errors.get(operation, 0),
        }

    def summary(self) -> dict[str, dict[str, float] | None]:
        return {op: self.stats(op) for op in self._latencies}

    def reset(self) -> None:
        self._latencies.clear()
        self._counts.clear()
        self._errors.clear()

    @staticmethod
    def _percentile(sorted_values: list[float], p: int) -> float:
        if not sorted_values:
            return 0.0
        idx = max(0, min(math.ceil(p / 100 * len(sorted_values)) - 1, len(sorted_values) - 1))
        return sorted_values[idx]


# ---------------------------------------------------------------------------
# PerformanceBenchmarker
# ---------------------------------------------------------------------------


class PerformanceBenchmarker:
    """Generic benchmarking utility with warm-up, statistics, and comparison."""

    DEFAULT_ITERATIONS = 100
    DEFAULT_WARMUP = 10

    def measure(
        self,
        name: str,
        fn: Callable[[], Any],
        iterations: int | None = None,
        warmup: int | None = None,
    ) -> BenchmarkResult:
        iterations = iterations or self.DEFAULT_ITERATIONS
        warmup = warmup or self.DEFAULT_WARMUP

        for _ in range(warmup):
            fn()

        times: list[float] = []
        start = time.perf_counter()

        for _ in range(iterations):
            t0 = time.perf_counter()
            fn()
            times.append((time.perf_counter() - t0) * 1000)

        total = (time.perf_counter() - start) * 1000
        sorted_t = sorted(times)
        mean = total / iterations
        std = statistics.stdev(times) if len(times) > 1 else 0.0

        return BenchmarkResult(
            name=name,
            iterations=iterations,
            total_time_ms=total,
            avg_time_ms=mean,
            min_time_ms=sorted_t[0],
            max_time_ms=sorted_t[-1],
            p50_ms=self._percentile(sorted_t, 50),
            p95_ms=self._percentile(sorted_t, 95),
            p99_ms=self._percentile(sorted_t, 99),
            std_dev=std,
            coefficient_of_variation=(std / mean * 100) if mean > 0 else 0.0,
            timestamp=time.time(),
        )

    async def measure_async(
        self,
        name: str,
        fn: Callable[[], Any],
        iterations: int | None = None,
        warmup: int | None = None,
    ) -> BenchmarkResult:
        iterations = iterations or self.DEFAULT_ITERATIONS
        warmup = warmup or self.DEFAULT_WARMUP

        for _ in range(warmup):
            await fn()

        times: list[float] = []
        start = time.perf_counter()

        for _ in range(iterations):
            t0 = time.perf_counter()
            await fn()
            times.append((time.perf_counter() - t0) * 1000)

        total = (time.perf_counter() - start) * 1000
        sorted_t = sorted(times)
        mean = total / iterations
        std = statistics.stdev(times) if len(times) > 1 else 0.0

        return BenchmarkResult(
            name=name,
            iterations=iterations,
            total_time_ms=total,
            avg_time_ms=mean,
            min_time_ms=sorted_t[0],
            max_time_ms=sorted_t[-1],
            p50_ms=self._percentile(sorted_t, 50),
            p95_ms=self._percentile(sorted_t, 95),
            p99_ms=self._percentile(sorted_t, 99),
            std_dev=std,
            coefficient_of_variation=(std / mean * 100) if mean > 0 else 0.0,
            timestamp=time.time(),
        )

    def compare(
        self,
        name1: str,
        fn1: Callable[[], Any],
        name2: str,
        fn2: Callable[[], Any],
        iterations: int | None = None,
        warmup: int | None = None,
    ) -> ComparisonResult:
        r1 = self.measure(name1, fn1, iterations, warmup)
        r2 = self.measure(name2, fn2, iterations, warmup)
        improvement = ((r1.avg_time_ms - r2.avg_time_ms) / r1.avg_time_ms * 100) if r1.avg_time_ms > 0 else 0.0
        pooled = math.sqrt((r1.std_dev**2 + r2.std_dev**2) / 2) if r1.std_dev > 0 or r2.std_dev > 0 else 1.0
        significant = abs(r1.avg_time_ms - r2.avg_time_ms) > 2 * pooled
        return ComparisonResult(
            result1=r1, result2=r2, improvement_pct=improvement, significant=significant,
        )

    @staticmethod
    def _percentile(sorted_values: list[float], p: int) -> float:
        if not sorted_values:
            return 0.0
        idx = max(0, min(math.ceil(p / 100 * len(sorted_values)) - 1, len(sorted_values) - 1))
        return sorted_values[idx]


# ---------------------------------------------------------------------------
# PerformanceRegressionDetector
# ---------------------------------------------------------------------------


class PerformanceRegressionDetector:
    """Detects performance regressions against a saved baseline."""

    def __init__(self) -> None:
        self._baseline: PerformanceBaseline | None = None

    def load_baseline(self, baseline: PerformanceBaseline) -> None:
        self._baseline = baseline

    def create_baseline(self, name: str, version: str, metrics: dict[str, float]) -> PerformanceBaseline:
        return PerformanceBaseline(name=name, version=version, metrics=dict(metrics), timestamp=time.time())

    def detect_regression(self, current_metrics: dict[str, float], threshold_pct: float = 10.0) -> RegressionResult:
        if self._baseline is None:
            return RegressionResult(has_regression=False)

        regressions: list[RegressionEntry] = []
        improvements: list[RegressionEntry] = []

        for metric, current_val in current_metrics.items():
            base_val = self._baseline.metrics.get(metric)
            if base_val is None or base_val == 0:
                continue
            change = ((current_val - base_val) / base_val) * 100
            is_regression = (  # higher-is-better vs lower-is-better heuristic
                change < -threshold_pct
                if metric.endswith(("throughput", "ops_per_second"))
                else change > threshold_pct
            )
            entry = RegressionEntry(metric=metric, baseline=base_val, current=current_val, change_pct=abs(change))
            if is_regression:
                regressions.append(entry)
            elif change > threshold_pct or change < -threshold_pct:
                improvements.append(entry)

        return RegressionResult(has_regression=len(regressions) > 0, regressions=regressions, improvements=improvements)
