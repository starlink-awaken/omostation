"""Tests for bin/gac/health-trend-chart.py

Covers:
  - empty / missing file → no data
  - JSONL parsing tolerates malformed lines
  - day-bucketing keeps LAST value of day
  - window filtering (--days) drops older records
  - sparkline output contains block chars when data present
  - --json output shape
  - --field selection
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "gac" / "health-trend-chart.py"
_MODULE = "_health_trend_chart_test"


def _load_module():
    spec = importlib.util.spec_from_file_location(_MODULE, SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def chart():
    return _load_module()


def _write_history(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8",
    )


def test_load_records_empty_file(chart, tmp_path: Path):
    """Missing path → empty list (no raise)."""
    records = chart._load_records(tmp_path / "nope.jsonl")
    assert records == []


def test_load_records_skips_garbage(chart, tmp_path: Path):
    """Malformed lines are silently dropped."""
    p = tmp_path / "h.jsonl"
    p.write_text(
        '{"ts": "2026-01-01T00:00:00Z", "health_score": 50}\n'
        "this is not json\n"
        '{"ts": "2026-01-02T00:00:00Z", "health_score": 60}\n',
        encoding="utf-8",
    )
    records = chart._load_records(p)
    assert len(records) == 2


def test_load_records_sorted_by_ts(chart, tmp_path: Path):
    """Records come out ascending by ts regardless of input order."""
    p = tmp_path / "h.jsonl"
    p.write_text(
        '{"ts": "2026-01-03T00:00:00Z", "health_score": 30}\n'
        '{"ts": "2026-01-01T00:00:00Z", "health_score": 50}\n'
        '{"ts": "2026-01-02T00:00:00Z", "health_score": 40}\n',
        encoding="utf-8",
    )
    records = chart._load_records(p)
    assert [r["health_score"] for r in records] == [50, 40, 30]


def test_filter_window_drops_old(chart):
    now = datetime(2026, 8, 23, 12, 0, 0)
    records = [
        {"ts": "2026-08-22T00:00:00Z"},  # 1.5 days ago — outside 1d window
        {"ts": "2026-08-22T20:00:00Z"},  # 16h ago — inside 1d
        {"ts": "2026-08-23T11:00:00Z"},  # 1h ago — inside 1d
    ]
    out = chart._filter_window(records, days=1, now=now)
    assert len(out) == 2
    assert out[0]["ts"] == "2026-08-22T20:00:00Z"


def test_bucket_by_day_keeps_last(chart):
    """When multiple records on the same day, only the LAST value counts."""
    records = [
        {"ts": "2026-08-23T01:00:00Z", "health_score": 50},
        {"ts": "2026-08-23T12:00:00Z", "health_score": 80},
        {"ts": "2026-08-23T18:00:00Z", "health_score": 60},
    ]
    buckets = chart._bucket_by_day(records, "health_score")
    assert len(buckets) == 1
    assert buckets[0] == ("2026-08-23", 60.0, 3)


def test_bucket_by_day_orders_chronologically(chart):
    records = [
        {"ts": "2026-08-22T12:00:00Z", "health_score": 50},
        {"ts": "2026-08-24T12:00:00Z", "health_score": 70},
        {"ts": "2026-08-23T12:00:00Z", "health_score": 60},
    ]
    buckets = chart._bucket_by_day(records, "health_score")
    assert [b[0] for b in buckets] == ["2026-08-22", "2026-08-23", "2026-08-24"]
    assert [b[1] for b in buckets] == [50.0, 60.0, 70.0]


def test_sparkline_block_chars_for_known_range(chart):
    """Sparkline renders 0..100 as 8 chars; values at extremes use min/max chars."""
    line = chart._sparkline([0, 100, 0, 100, 0, 100, 0, 100], width=8)
    # Should contain both min char (space) and max char (█)
    assert " " in line
    assert "█" in line
    assert len(line) == 8


def test_sparkline_empty(chart):
    """Empty input → empty string (no raise)."""
    assert chart._sparkline([]) == ""
    assert chart._sparkline([], width=10) == ""


def test_format_table_empty(chart):
    """Empty buckets → friendly placeholder."""
    out = chart._format_table("health_score", [])
    assert "no data" in out


def test_format_table_with_buckets(chart):
    buckets = [
        ("2026-08-22", 50.0, 1),
        ("2026-08-23", 75.0, 2),
    ]
    out = chart._format_table("health_score", buckets)
    assert "2026-08-22" in out
    assert "2026-08-23" in out
    assert "health_score" not in out  # field name not in table (just the header)


def test_cli_json_mode(tmp_path: Path, monkeypatch, capsys):
    """--json emits machine-readable summary."""
    p = tmp_path / "h.jsonl"
    _write_history(
        p,
        [
            {"ts": "2026-08-22T00:00:00Z", "health_score": 50, "governance_anomaly_score": 10},
            {"ts": "2026-08-23T00:00:00Z", "health_score": 75, "governance_anomaly_score": 5},
        ],
    )
    rc = _load_module().main(
        ["--path", str(p), "--field", "health_score", "--json", "--days", "30"]
    )
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["field"] == "health_score"
    assert data["days"] == 30
    assert len(data["buckets"]) == 2
    assert data["min"] == 50.0
    assert data["max"] == 75.0
    assert data["latest"] == 75.0
    # delta between first and last bucket
    assert data["delta"] == 25.0


def test_cli_human_mode_runs(tmp_path: Path, capsys):
    """Default (no --json) emits a human-readable report."""
    p = tmp_path / "h.jsonl"
    _write_history(
        p,
        [
            {"ts": "2026-08-23T01:00:00Z", "health_score": 50},
            {"ts": "2026-08-23T12:00:00Z", "health_score": 75},
        ],
    )
    rc = _load_module().main(["--path", str(p)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "health_score trend" in out
    assert "2026-08-23" in out
    assert "sparkline" in out


def test_cli_invalid_field(tmp_path: Path):
    """--field with unknown value exits non-zero (argparse error)."""
    p = tmp_path / "h.jsonl"
    _write_history(p, [{"ts": "2026-08-23T00:00:00Z", "health_score": 50}])
    with pytest.raises(SystemExit):
        _load_module().main(["--path", str(p), "--field", "bogus"])


def test_cli_no_data_message(tmp_path: Path, capsys):
    """Empty file → friendly '(no data)' output, exit 0."""
    p = tmp_path / "empty.jsonl"
    p.write_text("", encoding="utf-8")
    rc = _load_module().main(["--path", str(p)])
    assert rc == 0
    assert "no data" in capsys.readouterr().out