"""Prometheus 指标收集器"""

import time
from collections import defaultdict
from typing import Any


class MetricsCollector:
    """轻量级指标收集器"""

    def __init__(self):
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._start_time = time.monotonic()

    def inc_counter(self, name: str, value: int = 1) -> None:
        self._counters[name] += value

    def set_gauge(self, name: str, value: float) -> None:
        self._gauges[name] = value

    def observe_histogram(self, name: str, value: float) -> None:
        self._histograms[name].append(value)

    def get_counter(self, name: str) -> int:
        return self._counters.get(name, 0)

    def get_gauge(self, name: str) -> float:
        return self._gauges.get(name, 0.0)

    def get_histogram(self, name: str) -> dict[str, float]:
        values = self._histograms.get(name, [])
        if not values:
            return {"count": 0, "sum": 0, "avg": 0, "min": 0, "max": 0}
        return {
            "count": len(values),
            "sum": sum(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
        }

    def export(self) -> dict[str, Any]:
        return {
            "counters": dict(self._counters),
            "gauges": self._gauges,
            "histograms": {k: self.get_histogram(k) for k in self._histograms},
            "uptime_seconds": time.monotonic() - self._start_time,
        }
