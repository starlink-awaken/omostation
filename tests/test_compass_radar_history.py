"""Tests for compass_radar._append_health_history.

The history append gives operators a time-series JSONL of health scores
so they can answer "what was health last Tuesday?" without parsing
git log of health.yaml.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

RADAR = Path(__file__).resolve().parents[1] / "bin" / "compass_radar.py"
_MODULE = "_compass_radar_history_test"


def _load():
    spec = importlib.util.spec_from_file_location(_MODULE, RADAR)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def radar():
    return _load()


def _report(score: int = 50, anomaly_count: int = 0, **kw) -> dict:
    base = {
        "health_score": score,
        "governance_anomaly_score": 50,
        "anomaly_count": anomaly_count,
        "service_online_ratio": 1.0,
        "freshness_score": 100,
        "total_tasks": 6,
        "source": "c2g.strategy (real audit, no mock)",
    }
    base.update(kw)
    return base


def test_append_creates_history_dir_and_file(radar, tmp_path: Path):
    health_yaml = tmp_path / "state/health.yaml"
    health_yaml.parent.mkdir(parents=True)
    health_yaml.write_text("generated_at: now\n")

    radar._append_health_history(health_yaml, _report(score=80))

    history_file = tmp_path / "state/history/health.jsonl"
    assert history_file.exists()
    lines = history_file.read_text().strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["health_score"] == 80
    assert record["anomaly_count"] == 0


def test_append_includes_required_fields(radar, tmp_path: Path):
    health_yaml = tmp_path / "state/health.yaml"
    health_yaml.parent.mkdir(parents=True)
    health_yaml.write_text("generated_at: now\n")

    radar._append_health_history(health_yaml, _report(score=42, anomaly_count=7))

    history_file = tmp_path / "state/history/health.jsonl"
    record = json.loads(history_file.read_text().strip())
    for key in (
        "ts",
        "health_score",
        "governance_anomaly_score",
        "anomaly_count",
        "service_online_ratio",
        "freshness_score",
        "total_tasks",
        "source",
    ):
        assert key in record, f"missing field: {key}"
    assert record["health_score"] == 42
    assert record["anomaly_count"] == 7


def test_multiple_appends_accumulate(radar, tmp_path: Path):
    health_yaml = tmp_path / "state/health.yaml"
    health_yaml.parent.mkdir(parents=True)
    health_yaml.write_text("generated_at: now\n")

    for i in range(5):
        radar._append_health_history(health_yaml, _report(score=i * 10))

    history_file = tmp_path / "state/history/health.jsonl"
    lines = history_file.read_text().strip().splitlines()
    assert len(lines) == 5
    scores = [json.loads(line)["health_score"] for line in lines]
    assert scores == [0, 10, 20, 30, 40]


def test_append_isolines_silent_on_failure(radar, tmp_path: Path):
    """If write fails, the function returns None (no raise)."""
    # Point health.yaml at a path whose history dir can't be created
    health_yaml = tmp_path / "no/such/dir/health.yaml"
    health_yaml.parent.mkdir(parents=True)  # creates up to no/such/dir/

    # Should not raise
    radar._append_health_history(health_yaml, _report(score=99))
    # No history file created (write silently failed)
    history_file = tmp_path / "no/such/dir/state/history/health.jsonl"
    assert not history_file.exists()


def test_history_path_derived_from_health_yaml(radar, tmp_path: Path):
    """history.jsonl sits at {health_yaml.parent.parent}/state/history/."""
    layout = tmp_path / ".omo/state/health.yaml"
    layout.parent.mkdir(parents=True)
    layout.write_text("generated_at: now\n")

    radar._append_health_history(layout, _report(score=88))

    expected = tmp_path / ".omo/state/history/health.jsonl"
    assert expected.exists()


def test_append_handles_missing_report_keys(radar, tmp_path: Path):
    """Missing report keys become None in the snapshot (graceful)."""
    health_yaml = tmp_path / "state/health.yaml"
    health_yaml.parent.mkdir(parents=True)
    health_yaml.write_text("generated_at: now\n")

    partial = {"health_score": 50}
    radar._append_health_history(health_yaml, partial)

    history_file = tmp_path / "state/history/health.jsonl"
    record = json.loads(history_file.read_text().strip())
    assert record["health_score"] == 50
    assert record["governance_anomaly_score"] is None
    assert record["source"] is None