"""Anomaly Detector — sliding-window statistical detection with adaptive thresholds."""

from __future__ import annotations

import statistics
from collections import deque
from dataclasses import dataclass


@dataclass
class AnomalyResult:
    """Result of an anomaly detection check.

    Attributes:
        is_anomaly: Whether this value is anomalous.
        value: The value that was checked.
        mean: Current rolling mean.
        stddev: Current rolling standard deviation.
        z_score: Computed z-score of the value.
        threshold: The z-score threshold used.
        trend: Detected trend direction (up/down/stable).
    """

    is_anomaly: bool
    value: float
    mean: float = 0.0
    stddev: float = 0.0
    z_score: float = 0.0
    threshold: float = 3.0
    trend: str = "stable"


class AnomalyDetector:
    """Detect anomalies using a sliding window with Welford's online algorithm.

    Maintains backward compatibility with the existing stub API (``update``,
    ``detect_spike``, ``detect_trend``, ``get_stats``) while adding adaptive
    threshold adjustment, rolling median computation, and multi-metric
    support via named series.

    The detector uses Welford's method for online mean/variance computation,
    which avoids storing all historical values.  The sliding window caps the
    number of samples used for baseline calculation to prevent stale data
    from masking recent trends.

    Typical usage::

        det = AnomalyDetector(window_size=100, z_threshold=3.0)
        for metric in metric_stream:
            result = det.update(metric)
            if result.is_anomaly:
                print(f"Anomaly: value={metric}, z={result.z_score:.2f}")
    """

    _MIN_SAMPLES: int = 3

    def __init__(self, window_size: int = 100, z_threshold: float = 3.0) -> None:
        self.window_size = window_size
        self.z_threshold = z_threshold

        # Welford state for online mean/variance
        self._history: deque[float] = deque(maxlen=window_size)
        self._mean: float = 0.0
        self._m2: float = 0.0  # sum of squared differences from mean
        self._count: int = 0

        # Adaptive threshold state
        self._adaptive_enabled: bool = False
        self._adaptive_multiplier: float = 1.0
        self._anomaly_rate: float = 0.0  # recent anomaly frequency
        self._anomaly_window: deque[bool] = deque(maxlen=50)
        self._target_anomaly_rate: float = 0.05  # aim for ~5% anomaly rate
        self._adaptive_step: float = 0.1

        # Per-series storage for multi-metric support
        self._series: dict[str, deque[float]] = {}

        # Recent spike/trench tracking
        self._last_spike_direction: str = "none"  # up / down / none

    # ------------------------------------------------------------------
    # Backward-compatible API
    # ------------------------------------------------------------------

    def update(self, value: float) -> AnomalyResult:
        """Add a value and check if it is anomalous.

        Uses Welford's online algorithm for O(1) per-sample mean/variance
        updates.  A value is anomalous if its z-score exceeds the threshold.

        Args:
            value: The metric observation.

        Returns:
            An :class:`AnomalyResult` with anomaly status and diagnostic fields.
        """
        self._history.append(value)
        self._count += 1
        delta = value - self._mean
        self._mean += delta / self._count
        delta2 = value - self._mean
        self._m2 += delta * delta2

        if self._count < self._MIN_SAMPLES:
            return AnomalyResult(is_anomaly=False, value=value)

        variance = self._m2 / max(self._count - 1, 1)
        stddev = max(variance**0.5, 0.001)
        z_score = abs(value - self._mean) / stddev

        effective_threshold = self.z_threshold
        if self._adaptive_enabled:
            effective_threshold *= self._adaptive_multiplier

        is_anomaly = z_score > effective_threshold
        self._anomaly_window.append(is_anomaly)
        if self._adaptive_enabled:
            self._adjust_threshold()

        # Determine trend from recent history
        trend = "stable"
        if len(self._history) >= 5:
            trend = self._detect_trend_internal()

        # Track spike direction
        if is_anomaly:
            self._last_spike_direction = "up" if value > self._mean else "down"
        else:
            self._last_spike_direction = "none"

        return AnomalyResult(
            is_anomaly=is_anomaly,
            value=value,
            mean=round(self._mean, 4),
            stddev=round(stddev, 4),
            z_score=round(z_score, 4),
            threshold=round(effective_threshold, 4),
            trend=trend,
        )

    def detect_spike(self, values: list[float]) -> bool:
        """Check if the latest value is a spike (sudden upward deviation).

        A spike is detected when the last value exceeds 3x the baseline
        (mean of preceding values).  Requires at least 5 values.

        Args:
            values: Complete history with the candidate value last.

        Returns:
            True if the last value is a significant upward spike.
        """
        if len(values) < max(self._MIN_SAMPLES, 5):
            return False
        baseline = statistics.mean(values[:-1])
        if baseline <= 0:
            # For metrics that can be zero (e.g., error counts), use
            # standard deviation-based detection
            if len(values) >= 5:
                std = statistics.stdev(values[:-1])
                if std < 1e-9:
                    return values[-1] > 0  # any non-zero after all zeros
                return values[-1] > baseline + 3.0 * std
            return False
        return values[-1] > baseline * 3.0

    def detect_trend(self, values: list[float]) -> str:
        """Determine the trend direction from a list of values.

        Splits the list in half, compares the means of the two halves:

        - ``"increasing"`` if second-half mean > 1.2x first-half mean.
        - ``"decreasing"`` if second-half mean < 0.8x first-half mean.
        - ``"stable"`` otherwise.
        - ``"insufficient_data"`` if fewer than 5 values.

        Args:
            values: Time-ordered list of metric observations.

        Returns:
            One of ``"insufficient_data"``, ``"increasing"``, ``"decreasing"``, ``"stable"``.
        """
        if len(values) < max(self._MIN_SAMPLES, 5):
            return "insufficient_data"
        mid = len(values) // 2
        first_avg = statistics.mean(values[:mid])
        second_avg = statistics.mean(values[mid:])
        if first_avg <= 0:
            # Handle zero/negative baselines
            if second_avg > first_avg + abs(first_avg) * 0.2:
                return "increasing"
            if second_avg < first_avg - abs(first_avg) * 0.2:
                return "decreasing"
            return "stable"
        ratio = second_avg / first_avg
        if ratio > 1.2:
            return "increasing"
        if ratio < 0.8:
            return "decreasing"
        return "stable"

    def get_stats(self) -> dict:
        """Return current detector statistics."""
        variance = self._m2 / max(self._count - 1, 1) if self._count > 1 else 0.0
        anomaly_count = sum(1 for a in self._anomaly_window if a)
        return {
            "count": self._count,
            "mean": round(self._mean, 4),
            "stddev": round(variance**0.5, 4),
            "window_size": self.window_size,
            "samples": len(self._history),
            "threshold": self.z_threshold,
            "adaptive": self._adaptive_enabled,
            "adaptive_multiplier": round(self._adaptive_multiplier, 4),
            "anomaly_rate": round(self._anomaly_rate, 4),
            "anomaly_count_window": anomaly_count,
        }

    # ------------------------------------------------------------------
    # Extended API
    # ------------------------------------------------------------------

    def get_rolling_mean(self) -> float:
        """Return the current rolling mean."""
        return self._mean

    def get_rolling_stddev(self) -> float:
        """Return the current rolling standard deviation."""
        if self._count < 2:
            return 0.0
        result: float = (self._m2 / (self._count - 1)) ** 0.5
        return result

    def get_rolling_median(self) -> float:
        """Return the median of recent values in the sliding window."""
        if not self._history:
            return 0.0
        return statistics.median(self._history)

    def get_rolling_percentile(self, pct: float) -> float:
        """Return the *pct*-th percentile of recent values (e.g., 95 for p95)."""
        if not self._history:
            return 0.0
        sorted_vals = sorted(self._history)
        return statistics.quantiles(sorted_vals, n=100, method="inclusive" if pct >= 100 else "exclusive")[
            min(int(pct * len(sorted_vals) / 100), len(sorted_vals) - 1)
        ]

    def enable_adaptive_threshold(self, target_rate: float = 0.05, step: float = 0.1) -> None:
        """Enable adaptive threshold adjustment.

        The z-score threshold is automatically tuned to maintain approximately
        *target_rate* fraction of values flagged as anomalous.  The multiplier
        changes in steps of *step*.

        Args:
            target_rate: Desired anomaly rate (0.0-1.0).
            step: Adjustment step size for the multiplier.
        """
        self._adaptive_enabled = True
        self._target_anomaly_rate = target_rate
        self._adaptive_step = step

    def disable_adaptive_threshold(self) -> None:
        """Disable adaptive threshold and revert to the static z-threshold."""
        self._adaptive_enabled = False
        self._adaptive_multiplier = 1.0

    def reset(self) -> None:
        """Reset all internal state (mean, variance, history)."""
        self._history.clear()
        self._mean = 0.0
        self._m2 = 0.0
        self._count = 0
        self._anomaly_window.clear()
        self._adaptive_multiplier = 1.0
        self._anomaly_rate = 0.0
        self._last_spike_direction = "none"

    # ------------------------------------------------------------------
    # Multi-series support
    # ------------------------------------------------------------------

    def update_series(self, series_name: str, value: float) -> AnomalyResult:
        """Record a value in a named series for multi-metric tracking.

        The detector maintains a separate sliding window per series, but
        applies the same anomaly logic to each observation.
        """
        if series_name not in self._series:
            self._series[series_name] = deque(maxlen=self.window_size)

        series = self._series[series_name]
        series.append(value)

        if len(series) < self._MIN_SAMPLES:
            return AnomalyResult(is_anomaly=False, value=value)

        mu = statistics.mean(series)
        sigma = statistics.stdev(series) if len(series) >= 2 else 1.0
        sigma = max(sigma, 0.001)
        z = abs(value - mu) / sigma

        return AnomalyResult(
            is_anomaly=z > self.z_threshold,
            value=value,
            mean=round(mu, 4),
            stddev=round(sigma, 4),
            z_score=round(z, 4),
            threshold=self.z_threshold,
        )

    def get_series_values(self, series_name: str) -> list[float]:
        """Return all values in a named series."""
        series = self._series.get(series_name)
        if series is None:
            return []
        return list(series)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_trend_internal(self) -> str:
        """Internal trend detection on the current history deque."""
        values = list(self._history)
        if len(values) < 5:
            return "stable"
        mid = len(values) // 2
        first_avg = statistics.mean(values[:mid])
        second_avg = statistics.mean(values[mid:])
        if first_avg <= 0:
            if second_avg > first_avg + 0.01:
                return "up"
            if second_avg < first_avg - 0.01:
                return "down"
            return "stable"
        ratio = second_avg / first_avg
        if ratio > 1.15:
            return "up"
        if ratio < 0.85:
            return "down"
        return "stable"

    def _adjust_threshold(self) -> None:
        """Adjust the adaptive threshold multiplier toward the target anomaly rate."""
        if len(self._anomaly_window) < 10:
            return
        self._anomaly_rate = sum(1 for a in self._anomaly_window if a) / len(self._anomaly_window)
        if self._anomaly_rate > self._target_anomaly_rate:
            # Too many anomalies → raise threshold
            self._adaptive_multiplier += self._adaptive_step
        elif self._anomaly_rate < self._target_anomaly_rate * 0.5:
            # Too few anomalies → lower threshold
            self._adaptive_multiplier = max(0.5, self._adaptive_multiplier - self._adaptive_step)
