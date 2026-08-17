"""Baseline and shadow-only forecast contracts for KEMS."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any


@dataclass(frozen=True)
class ShadowForecast:
    series_id: str
    source_run_id: str
    model_id: str
    horizon: int
    predictions: tuple[float, ...]
    lower_bounds: tuple[float, ...]
    upper_bounds: tuple[float, ...]
    baseline_value: float
    mode: str = "shadow"

    def __post_init__(self) -> None:
        if self.mode != "shadow":
            raise ValueError("KEMS forecasts must remain in shadow mode")
        if not self.series_id or not self.source_run_id or not self.model_id:
            raise ValueError("forecast identity fields are required")
        if self.horizon <= 0 or len(self.predictions) != self.horizon:
            raise ValueError("forecast horizon must match predictions")
        if len(self.lower_bounds) != self.horizon or len(self.upper_bounds) != self.horizon:
            raise ValueError("forecast intervals must match horizon")
        if any(
            lower > value or value > upper
            for value, lower, upper in zip(self.predictions, self.lower_bounds, self.upper_bounds)
        ):
            raise ValueError("forecast predictions must stay within their intervals")

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["predictions"] = list(self.predictions)
        result["lower_bounds"] = list(self.lower_bounds)
        result["upper_bounds"] = list(self.upper_bounds)
        return result


@dataclass(frozen=True)
class ShadowForecastEvaluation:
    model_id: str
    baseline_mae: float
    model_mae: float
    beats_baseline: bool
    mode: str = "shadow"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_naive_shadow_forecast(
    values: tuple[float, ...],
    *,
    series_id: str,
    source_run_id: str,
    horizon: int,
    model_id: str = "naive-last-v1",
) -> ShadowForecast:
    """Build a deterministic baseline forecast without triggering actions."""
    if not values or any(not isfinite(value) for value in values):
        raise ValueError("forecast history must contain finite values")
    if horizon <= 0:
        raise ValueError("forecast horizon must be positive")
    baseline = values[-1]
    spread = max(abs(baseline) * 0.1, 1.0)
    return ShadowForecast(
        series_id,
        source_run_id,
        model_id,
        horizon,
        (baseline,) * horizon,
        (baseline - spread,) * horizon,
        (baseline + spread,) * horizon,
        baseline,
    )


def build_moving_average_shadow_forecast(
    values: tuple[float, ...],
    *,
    series_id: str,
    source_run_id: str,
    horizon: int,
    window: int = 3,
    model_id: str = "moving-average-v1",
) -> ShadowForecast:
    """Build a deterministic moving-average candidate for shadow evaluation."""
    if not values or any(not isfinite(value) for value in values):
        raise ValueError("forecast history must contain finite values")
    if horizon <= 0 or window <= 0:
        raise ValueError("forecast horizon and window must be positive")
    history = values[-window:]
    baseline = sum(history) / len(history)
    deviations = tuple(abs(value - baseline) for value in history)
    spread = max(sum(deviations) / len(deviations), 1.0)
    return ShadowForecast(
        series_id,
        source_run_id,
        model_id,
        horizon,
        (baseline,) * horizon,
        (baseline - spread,) * horizon,
        (baseline + spread,) * horizon,
        values[-1],
    )


def evaluate_shadow_forecast(
    *,
    model_id: str,
    predictions: tuple[float, ...],
    actual: tuple[float, ...],
    baseline_value: float,
) -> ShadowForecastEvaluation:
    if not predictions or len(predictions) != len(actual):
        raise ValueError("predictions and actual values must have the same non-empty length")
    model_mae = sum(abs(predicted - observed) for predicted, observed in zip(predictions, actual)) / len(actual)
    baseline_mae = sum(abs(baseline_value - observed) for observed in actual) / len(actual)
    return ShadowForecastEvaluation(model_id, baseline_mae, model_mae, model_mae < baseline_mae)
