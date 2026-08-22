"""Tests for the observability event dedup logic in compass_radar.

The radar accumulates "anomaly_count" from critical/degraded observability
events in the 24h window. Without dedup, a flaky check that fails 20 times
in 1h inflates anomaly_count and floors governance_anomaly_score at 25
(熔断). With dedup (1h window per (type, check) key), each unique failure
counts as 1.

Tests use synthetic events.jsonl in tmp_path, no real workspace touch.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

RADAR = Path(__file__).resolve().parents[1] / "bin" / "compass_radar.py"
_MODULE = "_compass_radar_dedup_test"


def _load_module() -> object:
    spec = importlib.util.spec_from_file_location(_MODULE, RADAR)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def radar():
    return _load_module()


def _write_events(ws_root: Path, events: list[dict]) -> None:
    p = ws_root / ".omo" / "_delivery" / "observability"
    p.mkdir(parents=True, exist_ok=True)
    (p / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
    )


def test_dedup_collapses_repeated_same_check(radar, tmp_path: Path):
    """5 events of the same (type, check) within 1h count as 1."""
    base_ts = "2026-08-22T12:00:00"
    events = []
    for i in range(5):
        events.append({
            "ts": f"2026-08-22T12:{i:02d}:00Z",
            "severity": "critical",
            "type": "governance:gate_failed",
            "payload": {"check": "doc-governance"},
        })
    _write_events(tmp_path, events)

    count, detail = radar._observability_event_anomalies(tmp_path)
    assert count == 1, f"expected 1 unique, got {count}"
    assert detail["by_type"]["governance:gate_failed"] == 1
    assert detail["dedup_window_hours"] == 1


def test_dedup_keeps_different_checks_separate(radar, tmp_path: Path):
    """2 different (type, check) in same hour = 2 events."""
    events = [
        {
            "ts": "2026-08-22T12:00:00Z",
            "severity": "critical",
            "type": "governance:gate_failed",
            "payload": {"check": "doc-governance"},
        },
        {
            "ts": "2026-08-22T12:05:00Z",
            "severity": "critical",
            "type": "governance:gate_failed",
            "payload": {"check": "gac-validate"},
        },
    ]
    _write_events(tmp_path, events)

    count, detail = radar._observability_event_anomalies(tmp_path)
    assert count == 2
    assert detail["by_type"]["governance:gate_failed"] == 2


def test_dedup_resets_after_window(radar, tmp_path: Path):
    """Same (type, check) 2h apart = 2 events (window expired)."""
    events = [
        {
            "ts": "2026-08-22T10:00:00Z",
            "severity": "critical",
            "type": "governance:gate_failed",
            "payload": {"check": "doc-governance"},
        },
        {
            "ts": "2026-08-22T12:00:00Z",  # 2h later
            "severity": "critical",
            "type": "governance:gate_failed",
            "payload": {"check": "doc-governance"},
        },
    ]
    _write_events(tmp_path, events)

    count, _ = radar._observability_event_anomalies(tmp_path)
    assert count == 2


def test_dedup_excludes_old_events(radar, tmp_path: Path):
    """Events older than 24h are dropped (not counted even if unique)."""
    events = [
        {
            "ts": "2026-08-20T10:00:00Z",  # > 24h before now
            "severity": "critical",
            "type": "governance:gate_failed",
            "payload": {"check": "doc-governance"},
        },
        {
            "ts": "2026-08-22T12:00:00Z",
            "severity": "critical",
            "type": "governance:gate_failed",
            "payload": {"check": "doc-governance"},
        },
    ]
    _write_events(tmp_path, events)

    count, _ = radar._observability_event_anomalies(tmp_path)
    assert count == 1  # only the recent one


def test_dedup_handles_missing_file(radar, tmp_path: Path):
    """Missing events.jsonl returns 0 (no penalty)."""
    count, detail = radar._observability_event_anomalies(tmp_path)
    assert count == 0
    assert detail == {}


def test_dedup_handles_unparseable_timestamp(radar, tmp_path: Path):
    """An event with unparseable ts is counted (don't silently drop)."""
    events = [
        {"severity": "critical", "type": "x", "payload": {"check": "y"}},
        {
            "ts": "2026-08-22T12:00:00Z",
            "severity": "critical",
            "type": "x",
            "payload": {"check": "y"},
        },
    ]
    _write_events(tmp_path, events)

    count, _ = radar._observability_event_anomalies(tmp_path)
    # First: unparseable ts → counted unconditionally (1)
    # Second: same (x, y) within 1h → deduped (0 added)
    # Total: 1
    assert count == 1


def test_dedup_includes_degraded_severity(radar, tmp_path: Path):
    """Both 'critical' and 'degraded' severities are counted."""
    events = [
        {
            "ts": "2026-08-22T12:00:00Z",
            "severity": "critical",
            "type": "a",
            "payload": {"check": "x"},
        },
        {
            "ts": "2026-08-22T12:01:00Z",
            "severity": "degraded",
            "type": "b",
            "payload": {"check": "y"},
        },
    ]
    _write_events(tmp_path, events)

    count, _ = radar._observability_event_anomalies(tmp_path)
    assert count == 2