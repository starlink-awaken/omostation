"""Engine metrics collection — counters, gauges, timers, histograms.

Port of agentmesh engine packages/engine/src/metrics.ts (MetricsCollector).
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum


class MetricType(StrEnum):
    COUNTER = "counter"
    GAUGE = "gauge"
    TIMER = "timer"
    HISTOGRAM = "histogram"


@dataclass
class MetricEntry:
    name: str
    type: MetricType
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: float = 0.0


@dataclass
class TimerHandle:
    stop: Callable[[], float]


@dataclass
class TimerStats:
    count: int = 0
    total_ms: float = 0.0
    avg_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0


@dataclass
class HistogramStats:
    count: int = 0
    sum: float = 0.0
    avg: float = 0.0
    min: float = 0.0
    max: float = 0.0
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0


@dataclass
class MetricsSnapshot:
    counters: dict[str, float] = field(default_factory=dict)
    gauges: dict[str, float] = field(default_factory=dict)
    timers: dict[str, TimerStats] = field(default_factory=dict)
    histograms: dict[str, HistogramStats] = field(default_factory=dict)
    timestamp: float = 0.0


class MetricsCollector:
    """In-memory metrics collector with counters, gauges, timers, and histograms.

    Maintains a FIFO history of all metric entries (max ``max_history``).
    Supports labelled metrics via ``{key{label=val}}`` format.
    """

    def __init__(self, max_history: int = 5000) -> None:
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._timers: dict[str, list[float]] = {}
        self._histograms: dict[str, list[float]] = {}
        self._history: list[MetricEntry] = []
        self._max_history = max_history

    # ------------------------------------------------------------------
    # internal key format: name{label1=val1,label2=val2}
    # ------------------------------------------------------------------

    @staticmethod
    def _fmt_key(name: str, labels: dict[str, str] | None = None) -> str:
        if not labels:
            return name
        pairs = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{pairs}}}"

    def _push_entry(
        self,
        name: str,
        typ: MetricType,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        entry = MetricEntry(
            name=name,
            type=typ,
            value=value,
            labels=labels or {},
            timestamp=time.time(),
        )
        self._history.append(entry)
        if len(self._history) > self._max_history:
            self._history.pop(0)

    # ------------------------------------------------------------------
    # counter
    # ------------------------------------------------------------------

    def increment(
        self,
        name: str,
        labels: dict[str, str] | None = None,
        amount: float = 1.0,
    ) -> None:
        key = self._fmt_key(name, labels)
        self._counters[key] = self._counters.get(key, 0.0) + amount
        self._push_entry(name, MetricType.COUNTER, self._counters[key], labels)

    def decrement(
        self,
        name: str,
        labels: dict[str, str] | None = None,
        amount: float = 1.0,
    ) -> None:
        key = self._fmt_key(name, labels)
        self._counters[key] = self._counters.get(key, 0.0) - amount
        self._push_entry(name, MetricType.COUNTER, self._counters[key], labels)

    def get_counter(self, name: str, labels: dict[str, str] | None = None) -> float:
        return self._counters.get(self._fmt_key(name, labels), 0.0)

    # ------------------------------------------------------------------
    # gauge
    # ------------------------------------------------------------------

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        key = self._fmt_key(name, labels)
        self._gauges[key] = value
        self._push_entry(name, MetricType.GAUGE, value, labels)

    def get_gauge(self, name: str, labels: dict[str, str] | None = None) -> float:
        return self._gauges.get(self._fmt_key(name, labels), 0.0)

    # ------------------------------------------------------------------
    # timer
    # ------------------------------------------------------------------

    def start_timer(
        self,
        name: str,
        labels: dict[str, str] | None = None,
    ) -> TimerHandle:
        start = time.perf_counter()
        collector = self

        def _stop() -> float:
            elapsed = (time.perf_counter() - start) * 1000.0
            collector.record_time(name, elapsed, labels)
            return elapsed

        return TimerHandle(stop=_stop)

    def record_time(
        self,
        name: str,
        duration_ms: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        key = self._fmt_key(name, labels)
        if key not in self._timers:
            self._timers[key] = []
        self._timers[key].append(duration_ms)
        self._push_entry(name, MetricType.TIMER, duration_ms, labels)

    # ------------------------------------------------------------------
    # histogram
    # ------------------------------------------------------------------

    def observe(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        key = self._fmt_key(name, labels)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)
        self._push_entry(name, MetricType.HISTOGRAM, value, labels)

    # ------------------------------------------------------------------
    # snapshot & history
    # ------------------------------------------------------------------

    def snapshot(self) -> MetricsSnapshot:
        snap = MetricsSnapshot(timestamp=time.time())
        for k, v in self._counters.items():
            snap.counters[k] = v
        for k, v in self._gauges.items():
            snap.gauges[k] = v
        for k, obs in self._timers.items():
            snap.timers[k] = _timer_stats(obs)
        for k, obs in self._histograms.items():
            snap.histograms[k] = _histogram_stats(obs)
        return snap

    def get_history(self, limit: int | None = None) -> list[MetricEntry]:
        if limit is None:
            return list(self._history)
        start = max(0, len(self._history) - limit)
        return self._history[start:]

    def reset(self) -> None:
        self._counters.clear()
        self._gauges.clear()
        self._timers.clear()
        self._histograms.clear()
        self._history.clear()

    def __repr__(self) -> str:
        return (
            f"MetricsCollector("
            f"counters={len(self._counters)}, "
            f"gauges={len(self._gauges)}, "
            f"timers={len(self._timers)}, "
            f"histograms={len(self._histograms)}, "
            f"history={len(self._history)})"
        )


# ------------------------------------------------------------------
# stats helpers
# ------------------------------------------------------------------


def _timer_stats(obs: list[float]) -> TimerStats:
    if not obs:
        return TimerStats()
    n = len(obs)
    total = sum(obs)
    return TimerStats(
        count=n,
        total_ms=total,
        avg_ms=total / n,
        min_ms=min(obs),
        max_ms=max(obs),
    )


def _histogram_stats(obs: list[float]) -> HistogramStats:
    if not obs:
        return HistogramStats()
    n = len(obs)
    total = sum(obs)
    sorted_ = sorted(obs)

    def _perc(p: float) -> float:
        idx = (p / 100.0) * (n - 1)
        lo = int(math.floor(idx))
        hi = int(math.ceil(idx))
        if lo == hi:
            return sorted_[lo]
        w = idx - lo
        return sorted_[lo] * (1.0 - w) + sorted_[hi] * w

    return HistogramStats(
        count=n,
        sum=total,
        avg=total / n,
        min=min(obs),
        max=max(obs),
        p50=_perc(50.0),
        p95=_perc(95.0),
        p99=_perc(99.0),
    )


def create_metrics(max_history: int = 5000) -> MetricsCollector:
    """Create a new MetricsCollector instance."""
    return MetricsCollector(max_history=max_history)
