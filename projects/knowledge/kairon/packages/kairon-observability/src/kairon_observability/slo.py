"""SLOTracker — Service Level Objective tracking with p99 latency and availability computation.

Includes SLODefinition for declarative SLOs, record_latency/record_error for
fine-grained tracking, SLOBreach alerting, and multi-window compliance reporting
(1h, 24h, 7d).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass
class SLOStatus:
    """Result of an SLO query for a given service + metric over a time window."""

    p99_ms: float
    availability_pct: float
    window_hours: float


@dataclass
class SLODefinition:
    """Declarative SLO for a service and metric.

    Attributes:
        name: Human-readable SLO name.
        service: Target service name.
        metric: Target metric name (e.g. ``"latency_ms"``).
        target_p99_ms: P99 latency threshold in milliseconds.
        target_availability: Availability target as a percentage (0-100).
        window_hours: Evaluation window duration.
        threshold_ms: Value below which an observation is considered "available".
    """

    name: str
    service: str
    metric: str
    target_p99_ms: float
    target_availability: float
    window_hours: float
    threshold_ms: float | None = None

    def __post_init__(self) -> None:
        if self.threshold_ms is None:
            self.threshold_ms = self.target_p99_ms


@dataclass
class SLOBreach:
    """Records an SLO breach event.

    Attributes:
        slo_name: Name of the breached SLO.
        service: Affected service.
        metric: Affected metric.
        current_p99_ms: Observed P99 at time of breach.
        current_availability: Observed availability at time of breach.
        target_p99_ms: Expected P99 threshold.
        target_availability: Expected availability target.
        breach_type: ``"p99"``, ``"availability"``, or ``"both"``.
        breached_at: ISO-8601 timestamp.
    """

    slo_name: str
    service: str
    metric: str
    current_p99_ms: float
    current_availability: float
    target_p99_ms: float
    target_availability: float
    breach_type: str  # p99 / availability / both
    breached_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class SLOCompliance:
    """Compliance report for a single SLO definition.

    Attributes:
        slo_name: SLO name.
        p99_ms: Current P99.
        p99_compliant: Whether P99 meets target.
        availability_pct: Current availability.
        availability_compliant: Whether availability meets target.
        overall_compliant: True if both P99 and availability are compliant.
        observations: Number of data points considered.
        window_hours: Evaluation window.
    """

    slo_name: str
    p99_ms: float
    p99_compliant: bool
    availability_pct: float
    availability_compliant: bool
    overall_compliant: bool
    observations: int
    window_hours: float


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


@dataclass
class _MetricPoint:
    """Internal storage for a single recorded metric data-point."""

    service: str
    metric: str
    value: float
    timestamp: datetime


def _percentile(sorted_values: list[float], pct: float) -> float:
    """Compute the *pct*-th percentile from a pre-sorted list (nearest-rank method)."""
    n = len(sorted_values)
    if n == 0:
        return 0.0
    rank = math.ceil((pct / 100.0) * n)
    return sorted_values[min(rank, n) - 1]


# ---------------------------------------------------------------------------
# SLOTracker
# ---------------------------------------------------------------------------


class SLOTracker:
    """Tracks per-service metric points and computes SLO status on demand.

    Maintains backward compatibility with the existing stub API (``track``,
    ``get_slo``, ``clear``) while adding:
    - ``record_latency`` / ``record_error`` convenience methods
    - ``get_compliance`` for declarative SLO evaluation
    - ``check_breaches`` for alerting
    - Multi-window reporting (1h, 24h, 7d)

    Typical usage::

        tracker = SLOTracker()
        tracker.track("api-gateway", "latency_ms", 12.3)
        tracker.track("api-gateway", "latency_ms", 450.0)
        status = tracker.get_slo("api-gateway", "latency_ms")
        print(status.p99_ms, status.availability_pct)
    """

    # Standard evaluation windows
    WINDOW_1H = 1.0
    WINDOW_24H = 24.0
    WINDOW_7D = 168.0
    WINDOW_30D = 720.0

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], list[_MetricPoint]] = {}
        self._breach_handler: Callable[[SLOBreach], None] | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _key(service: str, metric: str) -> tuple[str, str]:
        return (service, metric)

    # ------------------------------------------------------------------
    # Backward-compatible Public API
    # ------------------------------------------------------------------

    def track(
        self,
        service: str,
        metric: str,
        value: float,
        timestamp: datetime | None = None,
    ) -> None:
        """Record a metric observation.

        Args:
            service: Name of the service (e.g. ``"api-gateway"``).
            metric: Name of the metric (e.g. ``"latency_ms"``).
            value: Observed value.
            timestamp: When the observation was made; defaults to now (UTC).
        """
        if timestamp is None:
            timestamp = datetime.now(tz=UTC)
        key = self._key(service, metric)
        point = _MetricPoint(service=service, metric=metric, value=value, timestamp=timestamp)
        self._store.setdefault(key, []).append(point)

    def get_slo(
        self,
        service: str,
        metric: str,
        window_hours: float = 24.0,
        threshold_ms: float = 500.0,
    ) -> SLOStatus:
        """Compute SLO status for *service* / *metric* over the last *window_hours*.

        *p99_ms* is computed from all values in the window.
        *availability_pct* is the fraction of values that are <= *threshold_ms* (0-100).

        Args:
            service: Service name.
            metric: Metric name.
            window_hours: Lookback window in hours.
            threshold_ms: Latency threshold for availability calculation.

        Returns:
            SLOStatus with computed p99 and availability.
        """
        key = self._key(service, metric)
        points = self._store.get(key, [])
        cutoff = datetime.now(tz=UTC) - timedelta(hours=window_hours)
        values = [p.value for p in points if p.timestamp >= cutoff]

        if not values:
            return SLOStatus(p99_ms=0.0, availability_pct=100.0, window_hours=window_hours)

        sorted_vals = sorted(values)
        p99_ms = _percentile(sorted_vals, 99.0)
        available = sum(1.0 for v in values if v <= threshold_ms)
        availability_pct = (available / len(values)) * 100.0

        return SLOStatus(
            p99_ms=round(p99_ms, 3),
            availability_pct=round(availability_pct, 4),
            window_hours=window_hours,
        )

    def clear(self, service: str | None = None, metric: str | None = None) -> int:
        """Drop stored data-points, optionally scoped to a service/metric.

        Returns the number of removed entries.
        """
        removed = 0
        if service is None and metric is None:
            removed = sum(len(v) for v in self._store.values())
            self._store.clear()
            return removed
        keys_to_drop: list[tuple[str, str]] = []
        for s, m in self._store:
            if (service is None or s == service) and (metric is None or m == metric):
                keys_to_drop.append((s, m))
        for k in keys_to_drop:
            removed += len(self._store.pop(k))
        return removed

    # ------------------------------------------------------------------
    # Extended API — Convenience recording
    # ------------------------------------------------------------------

    def record_latency(self, service: str, latency_ms: float) -> None:
        """Record a latency observation.

        Shortcut for ``track(service, "latency_ms", latency_ms)``.
        """
        self.track(service, "latency_ms", latency_ms)

    def record_error(self, service: str) -> None:
        """Record an error event.

        The error is stored as a boolean metric (1 = error, 0 = success).
        Internally this is tracked as ``"error_total"`` with value 1.0.
        """
        self.track(service, "error_total", 1.0)

    def record_success(self, service: str) -> None:
        """Record a success event (non-error).

        Tracked as ``"error_total"`` with value 0.0.
        """
        self.track(service, "error_total", 0.0)

    # ------------------------------------------------------------------
    # Extended API — SLO Definitions & Compliance
    # ------------------------------------------------------------------

    def get_compliance(self, slo: SLODefinition) -> SLOCompliance:
        """Evaluate compliance against a declarative :class:`SLODefinition`.

        Args:
            slo: The SLO definition to evaluate.

        Returns:
            :class:`SLOCompliance` with per-metric compliance flags.
        """
        status = self.get_slo(
            slo.service,
            slo.metric,
            window_hours=slo.window_hours,
            threshold_ms=slo.threshold_ms or slo.target_p99_ms,
        )

        p99_compliant = status.p99_ms <= slo.target_p99_ms
        avail_compliant = status.availability_pct >= slo.target_availability

        key = self._key(slo.service, slo.metric)
        points = self._store.get(key, [])
        cutoff = datetime.now(tz=UTC) - timedelta(hours=slo.window_hours)
        observations = sum(1 for p in points if p.timestamp >= cutoff)

        return SLOCompliance(
            slo_name=slo.name,
            p99_ms=status.p99_ms,
            p99_compliant=p99_compliant,
            availability_pct=status.availability_pct,
            availability_compliant=avail_compliant,
            overall_compliant=p99_compliant and avail_compliant,
            observations=observations,
            window_hours=slo.window_hours,
        )

    def check_breaches(self, slos: list[SLODefinition]) -> list[SLOBreach]:
        """Check a list of SLO definitions and return any breaches.

        When a breach is detected and a :attr:`breach_handler` is set,
        it is called with each :class:`SLOBreach`.

        Args:
            slos: List of SLO definitions to evaluate.

        Returns:
            List of :class:`SLOBreach` instances for non-compliant SLOs.
        """
        breaches: list[SLOBreach] = []
        for slo in slos:
            compliance = self.get_compliance(slo)
            if compliance.overall_compliant:
                continue

            # Determine breach type
            breach_types: list[str] = []
            if not compliance.p99_compliant:
                breach_types.append("p99")
            if not compliance.availability_compliant:
                breach_types.append("availability")

            breach = SLOBreach(
                slo_name=slo.name,
                service=slo.service,
                metric=slo.metric,
                current_p99_ms=compliance.p99_ms,
                current_availability=compliance.availability_pct,
                target_p99_ms=slo.target_p99_ms,
                target_availability=slo.target_availability,
                breach_type="+".join(breach_types) if breach_types else "unknown",
            )
            breaches.append(breach)

            if self._breach_handler:
                self._breach_handler(breach)

        return breaches

    def set_breach_handler(self, handler: Callable[[SLOBreach], None]) -> None:
        """Register a callback invoked for each SLO breach.

        Args:
            handler: A callable that receives an :class:`SLOBreach` instance.
        """
        self._breach_handler = handler

    # ------------------------------------------------------------------
    # Extended API — Multi-window reporting
    # ------------------------------------------------------------------

    def get_multi_window_report(
        self,
        service: str,
        metric: str,
        threshold_ms: float = 500.0,
    ) -> dict[str, SLOStatus]:
        """Return SLO status across multiple standard windows.

        Evaluates 1h, 24h, and 7d windows simultaneously.

        Args:
            service: Service name.
            metric: Metric name.
            threshold_ms: Availability threshold for all windows.

        Returns:
            Dict mapping window label to :class:`SLOStatus`.
        """
        windows = {
            "1h": self.WINDOW_1H,
            "24h": self.WINDOW_24H,
            "7d": self.WINDOW_7D,
        }
        return {
            label: self.get_slo(service, metric, window_hours=hw, threshold_ms=threshold_ms)
            for label, hw in windows.items()
        }

    def get_error_budget_remaining(
        self,
        service: str,
        window_hours: float = 720.0,  # 30 days
        target_availability: float = 99.9,
    ) -> dict:
        """Calculate the remaining error budget for a service.

        An error budget is the acceptable amount of failure derived from the
        availability target over a rolling window.

        Args:
            service: Service name.
            window_hours: Evaluation window.
            target_availability: Target availability percentage (e.g., 99.9).

        Returns:
            Dict with ``error_budget_used_pct``, ``remaining_budget_pct``,
            ``total_requests``, ``error_count``, ``window_hours``.
        """
        key = self._key(service, "error_total")
        points = self._store.get(key, [])
        cutoff = datetime.now(tz=UTC) - timedelta(hours=window_hours)
        window_points = [p for p in points if p.timestamp >= cutoff]

        total_requests = len(window_points)
        error_count = sum(1 for p in window_points if p.value > 0)

        if total_requests == 0:
            return {
                "error_budget_used_pct": 0.0,
                "remaining_budget_pct": 100.0,
                "total_requests": 0,
                "error_count": 0,
                "window_hours": window_hours,
            }

        allowable_errors = total_requests * (1.0 - target_availability / 100.0)
        if allowable_errors <= 0:
            budget_used_pct = 100.0 if error_count > 0 else 0.0
        else:
            budget_used_pct = min(100.0, (error_count / allowable_errors) * 100.0)

        return {
            "error_budget_used_pct": round(budget_used_pct, 4),
            "remaining_budget_pct": round(100.0 - budget_used_pct, 4),
            "total_requests": total_requests,
            "error_count": error_count,
            "window_hours": window_hours,
        }

    def get_snapshot(self, service: str) -> dict:
        """Return a full metric snapshot for a service across all tracked metrics.

        Includes P99 for any latency metric and error count for error metrics.
        """
        result: dict[str, Any] = {"service": service, "metrics": {}}
        for (s, m), points in self._store.items():
            if s != service:
                continue
            values = [p.value for p in points]
            sorted_vals = sorted(values)
            metric_info = {
                "count": len(values),
                "mean": round(sum(values) / len(values), 4) if values else 0.0,
                "p99": round(_percentile(sorted_vals, 99.0), 4),
                "p95": round(_percentile(sorted_vals, 95.0), 4),
                "p50": round(_percentile(sorted_vals, 50.0), 4),
            }
            result["metrics"][m] = metric_info
        return result
