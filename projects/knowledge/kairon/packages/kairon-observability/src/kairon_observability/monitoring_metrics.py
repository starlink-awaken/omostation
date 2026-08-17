from __future__ import annotations

"""
Metrics collection for D-Harvest pipeline monitoring.

Provides ``MetricsCollector`` (counter/gauge/histogram tracking) and
``HarvestMetrics`` (domain-specific convenience wrapper).
"""

import time
from collections import defaultdict


class MetricsCollector:
    """Simple in-memory metrics collector with Prometheus-format export.

    Tracks counters, gauges, and histograms for the harvest pipeline.
    """

    def __init__(self) -> None:
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)

    # ---- counters -----------------------------------------------------------

    def increment(self, name: str, value: int = 1) -> None:
        """Increment a named counter by *value*."""
        self._counters[name] += value

    def get_counter(self, name: str) -> int:
        """Return the current value of a counter."""
        return self._counters.get(name, 0)

    # ---- gauges -----------------------------------------------------------

    def set_gauge(self, name: str, value: float) -> None:
        """Set a named gauge to *value*."""
        self._gauges[name] = value

    def get_gauge(self, name: str) -> float | None:
        """Return the current value of a gauge."""
        return self._gauges.get(name)

    # ---- histograms -------------------------------------------------------

    def observe(self, name: str, value: float) -> None:
        """Record a single observation for a named histogram."""
        self._histograms[name].append(value)

    def get_histogram(self, name: str) -> list[float]:
        """Return all observations for a named histogram."""
        return list(self._histograms.get(name, []))

    # ---- export -----------------------------------------------------------

    def export_prometheus(self) -> str:
        """Export all metrics in Prometheus exposition format."""
        lines: list[str] = []

        for name, value in sorted(self._counters.items()):
            safe_name = name.replace(" ", "_").replace("-", "_")
            lines.append(f"# HELP {safe_name} Counter metric")
            lines.append(f"# TYPE {safe_name} counter")
            lines.append(f"{safe_name} {value}")

        for name, val in sorted(self._gauges.items()):
            safe_name = name.replace(" ", "_").replace("-", "_")
            lines.append(f"# HELP {safe_name} Gauge metric")
            lines.append(f"# TYPE {safe_name} gauge")
            lines.append(f"{safe_name} {val}")

        for name, observations in sorted(self._histograms.items()):
            safe_name = name.replace(" ", "_").replace("-", "_")
            lines.append(f"# HELP {safe_name} Histogram metric")
            lines.append(f"# TYPE {safe_name} histogram")
            for obs in observations:
                lines.append(f"{safe_name} {obs}")

        return "\n".join(lines) + "\n"


class HarvestMetrics:
    """Domain-specific convenience wrapper around ``MetricsCollector``.

    Provides named methods for D-Harvest lifecycle events so that callers
    (e.g. ``verification.py``) can record metrics without dealing with the
    collector internals directly.
    """

    def __init__(self, collector: MetricsCollector | None = None) -> None:
        self.collector = collector or MetricsCollector()

    def harvest_started(self, source_id: str) -> None:
        """Record that a harvest cycle has started for *source_id*."""
        self.collector.increment("d_harvest_harvests_started_total")
        self.collector.set_gauge(f"d_harvest_last_start_{source_id}", time.time())

    def harvest_completed(
        self,
        source_id: str,
        items_count: int,
        duration_ms: float,
    ) -> None:
        """Record that a harvest cycle completed for *source_id*."""
        self.collector.increment("d_harvest_harvests_completed_total")
        self.collector.increment("d_harvest_items_extracted_total", items_count)
        self.collector.observe("d_harvest_harvest_duration_ms", duration_ms)
        self.collector.set_gauge(f"d_harvest_last_completed_{source_id}", time.time())
