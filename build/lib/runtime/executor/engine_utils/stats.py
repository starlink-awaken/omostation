"""Benchmarking and statistical utilities.

Migrated from agentmesh benchmarks/utils.ts.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class BenchmarkStats:
    """Statistical metrics computed from a sample set."""

    min: float = 0.0
    max: float = 0.0
    avg: float = 0.0
    median: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    samples: int = 0
    std_dev: float = 0.0


def calculate_stats(values: list[float]) -> BenchmarkStats:
    """Compute statistical metrics for a list of duration samples."""
    if not values:
        return BenchmarkStats()
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    avg = sum(sorted_vals) / n
    variance = sum((v - avg) ** 2 for v in sorted_vals) / n
    return BenchmarkStats(
        min=sorted_vals[0],
        max=sorted_vals[-1],
        avg=avg,
        median=_percentile(sorted_vals, 50),
        p95=_percentile(sorted_vals, 95),
        p99=_percentile(sorted_vals, 99),
        samples=n,
        std_dev=math.sqrt(variance),
    )


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = (p / 100.0) * (len(sorted_vals) - 1)
    lower = int(math.floor(idx))
    upper = int(math.ceil(idx))
    weight = idx - lower
    if upper >= len(sorted_vals):
        return sorted_vals[-1]
    return sorted_vals[lower] * (1 - weight) + sorted_vals[upper] * weight


def measure_time(fn: Callable[[], Any]) -> tuple[Any, float]:
    """Measure synchronous function execution time."""
    start = time.perf_counter()
    result = fn()
    duration_ms = (time.perf_counter() - start) * 1000
    return result, duration_ms


async def measure_time_async(fn: Callable[[], Any]) -> tuple[Any, float]:
    """Measure async function execution time."""
    start = time.perf_counter()
    result = await fn()
    duration_ms = (time.perf_counter() - start) * 1000
    return result, duration_ms


def collect_samples(fn: Callable[[], Any], n_samples: int) -> tuple[list[Any], list[float]]:
    """Collect duration samples from repeated synchronous execution."""
    warmup = min(5, max(1, n_samples // 10))
    for _ in range(warmup):
        fn()
    results: list[Any] = []
    durations: list[float] = []
    for _ in range(n_samples):
        r, d = measure_time(fn)
        results.append(r)
        durations.append(d)
    return results, durations


async def collect_samples_async(
    fn: Callable[[], Any],
    n_samples: int,
) -> tuple[list[Any], list[float]]:
    """Collect duration samples from repeated async execution."""
    warmup = min(5, max(1, n_samples // 10))
    for _ in range(warmup):
        await fn()
    results: list[Any] = []
    durations: list[float] = []
    for _ in range(n_samples):
        r, d = await measure_time_async(fn)
        results.append(r)
        durations.append(d)
    return results, durations
