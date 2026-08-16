"""Durable storage for shadow forecasts and their out-of-sample evaluations."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .forecast import ShadowForecast, ShadowForecastEvaluation


class ForecastStore:
    """Persist model output without granting it an execution side effect."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS forecasts (
                    forecast_id TEXT PRIMARY KEY,
                    series_id TEXT NOT NULL,
                    source_run_id TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    horizon INTEGER NOT NULL,
                    predictions_json TEXT NOT NULL,
                    lower_bounds_json TEXT NOT NULL,
                    upper_bounds_json TEXT NOT NULL,
                    baseline_value REAL NOT NULL,
                    mode TEXT NOT NULL CHECK (mode = 'shadow')
                );
                CREATE TABLE IF NOT EXISTS forecast_evaluations (
                    evaluation_id TEXT PRIMARY KEY,
                    forecast_id TEXT NOT NULL REFERENCES forecasts(forecast_id),
                    model_id TEXT NOT NULL,
                    baseline_mae REAL NOT NULL,
                    model_mae REAL NOT NULL,
                    beats_baseline INTEGER NOT NULL,
                    mode TEXT NOT NULL CHECK (mode = 'shadow')
                );
                """
            )

    def record_forecast(self, forecast_id: str, forecast: ShadowForecast) -> bool:
        if not forecast_id.strip():
            raise ValueError("forecast_id is required")
        self.initialize()
        with self._connect() as connection:
            existing = connection.execute("SELECT * FROM forecasts WHERE forecast_id=?", (forecast_id,)).fetchone()
            payload = (
                forecast_id,
                forecast.series_id,
                forecast.source_run_id,
                forecast.model_id,
                forecast.horizon,
                json.dumps(forecast.predictions),
                json.dumps(forecast.lower_bounds),
                json.dumps(forecast.upper_bounds),
                forecast.baseline_value,
                forecast.mode,
            )
            if existing:
                if tuple(existing) != payload:
                    raise ValueError("forecast_id already exists with different output")
                return False
            connection.execute("INSERT INTO forecasts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", payload)
        return True

    def record_evaluation(self, evaluation_id: str, forecast_id: str, evaluation: ShadowForecastEvaluation) -> bool:
        self.initialize()
        with self._connect() as connection:
            if not connection.execute("SELECT 1 FROM forecasts WHERE forecast_id=?", (forecast_id,)).fetchone():
                raise KeyError(f"unknown forecast: {forecast_id}")
            existing = connection.execute(
                "SELECT * FROM forecast_evaluations WHERE evaluation_id=?", (evaluation_id,)
            ).fetchone()
            payload = (
                evaluation_id,
                forecast_id,
                evaluation.model_id,
                evaluation.baseline_mae,
                evaluation.model_mae,
                int(evaluation.beats_baseline),
                evaluation.mode,
            )
            if existing:
                if tuple(existing) != payload:
                    raise ValueError("evaluation_id already exists with different output")
                return False
            connection.execute("INSERT INTO forecast_evaluations VALUES (?, ?, ?, ?, ?, ?, ?)", payload)
        return True

    def get_forecast(self, forecast_id: str) -> dict[str, object] | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM forecasts WHERE forecast_id=?", (forecast_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        for key in ("predictions_json", "lower_bounds_json", "upper_bounds_json"):
            result[key.removesuffix("_json")] = json.loads(str(result.pop(key)))
        return result
