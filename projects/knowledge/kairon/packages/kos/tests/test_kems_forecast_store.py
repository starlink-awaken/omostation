from kos.kems import ForecastStore, build_moving_average_shadow_forecast, evaluate_shadow_forecast


def test_forecast_store_persists_idempotent_shadow_results(tmp_path):
    store = ForecastStore(tmp_path / "forecast.sqlite")
    forecast = build_moving_average_shadow_forecast(
        (10.0, 12.0, 14.0), series_id="s-1", source_run_id="run-1", horizon=2
    )
    evaluation = evaluate_shadow_forecast(
        model_id=forecast.model_id,
        predictions=forecast.predictions,
        actual=(15.0, 16.0),
        baseline_value=forecast.baseline_value,
    )
    assert store.record_forecast("forecast-1", forecast) is True
    assert store.record_forecast("forecast-1", forecast) is False
    assert store.record_evaluation("eval-1", "forecast-1", evaluation) is True
    assert store.record_evaluation("eval-1", "forecast-1", evaluation) is False
    saved = store.get_forecast("forecast-1")
    assert saved is not None
    assert saved["predictions"] == [12.0, 12.0]
