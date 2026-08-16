"""Unit tests for PerformanceDriftDetector."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from omlxc.benchmark import PerformanceDriftDetector
from omlxc.storage.models import BenchmarkRunRecord


def _make_record(model_id: str, tps: float, days_ago: int) -> BenchmarkRunRecord:
    return BenchmarkRunRecord(
        run_id=f"run-{model_id}-{days_ago}",
        model_id=model_id,
        placement_id=f"placement-{model_id}",
        node_id="node-1",
        cold_load_ms=100.0,
        warm_load_ms=20.0,
        ttft_ms=25.0,
        tps=tps,
        vram_used_mb=None,
        tested_at=datetime.now(UTC) - timedelta(days=days_ago),
    )


def test_drift_detector_detects_regression() -> None:
    detector = PerformanceDriftDetector(drift_threshold=0.25)

    # 3 historical records with ~50 TPS, latest drops to 30 TPS (-40%)
    records = [
        _make_record("qwen-27b", 52.0, days_ago=3),
        _make_record("qwen-27b", 50.0, days_ago=2),
        _make_record("qwen-27b", 48.0, days_ago=1),
        _make_record("qwen-27b", 30.0, days_ago=0),
    ]

    reports = detector.detect(records)
    assert len(reports) == 1
    rep = reports[0]
    assert rep.model_id == "qwen-27b"
    assert rep.is_drifted is True
    assert rep.drift_ratio >= 0.35


def test_drift_detector_normal_performance() -> None:
    detector = PerformanceDriftDetector(drift_threshold=0.25)

    # Stable records (~50 TPS, latest 48 TPS)
    records = [
        _make_record("qwen-27b", 50.0, days_ago=2),
        _make_record("qwen-27b", 48.0, days_ago=0),
    ]

    reports = detector.detect(records)
    assert len(reports) == 1
    assert reports[0].is_drifted is False
