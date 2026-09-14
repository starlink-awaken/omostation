"""Tests for shadow-only KEMS forecasting."""

import pytest
from kos.kems import (
    ShadowForecast,
    build_moving_average_shadow_forecast,
    build_naive_shadow_forecast,
    evaluate_shadow_forecast,
)


def test_naive_forecast_is_interval_bound_and_shadow_only():
    forecast = build_naive_shadow_forecast((10.0, 11.0), series_id="indicator-1", source_run_id="run-1", horizon=2)
    assert forecast.mode == "shadow"
    assert forecast.predictions == (11.0, 11.0)
    assert forecast.to_dict()["horizon"] == 2


def test_forecast_evaluation_compares_against_baseline():
    result = evaluate_shadow_forecast(
        model_id="candidate-v1", predictions=(10.0, 10.0), actual=(10.0, 11.0), baseline_value=12.0
    )
    assert result.model_mae == 0.5
    assert result.baseline_mae == 1.5
    assert result.beats_baseline is True


def test_forecast_rejects_non_shadow_mode_and_bad_history():
    forecast = build_naive_shadow_forecast((1.0,), series_id="s", source_run_id="r", horizon=1)
    with pytest.raises(ValueError, match="shadow"):
        ShadowForecast("s", "r", "m", 1, (1.0,), (0.0,), (2.0,), 1.0, mode="live")
    assert forecast.mode == "shadow"
    with pytest.raises(ValueError, match="finite"):
        build_naive_shadow_forecast((float("nan"),), series_id="s", source_run_id="r", horizon=1)


def test_moving_average_shadow_forecast_is_deterministic():
    forecast = build_moving_average_shadow_forecast((10.0, 12.0, 14.0), series_id="s", source_run_id="r", horizon=2)
    assert forecast.predictions == (12.0, 12.0)
    assert forecast.baseline_value == 14.0
