"""Tests for telemetry metrics collection and Prometheus export (BET-Y1Q4-T8-14)."""

import json
from pathlib import Path

from cockpit.cli import main
from cockpit.domain.exit_codes import ExitCode
from cockpit.telemetry.metrics import MetricsCollector


def test_metrics_collector_record_and_summary(tmp_path: Path):
    store = tmp_path / "test_metrics.json"
    collector = MetricsCollector(storage_path=store, max_records=10)

    collector.record_command("dashboard", "system", 0, 0.05)
    collector.record_command("dashboard", "system", 0, 0.03)
    collector.record_command("quickstart", "user", 1, 0.12, error="check failed")

    summary = collector.get_summary()
    assert summary["total_invocations"] == 3
    assert summary["total_errors"] == 1
    assert summary["domain_distribution"] == {"system": 2, "user": 1}
    assert summary["latency_seconds"]["p50"] > 0

    prom_text = collector.export_prometheus_text()
    assert "# HELP cockpit_command_total" in prom_text
    assert 'cockpit_command_total{command="dashboard",domain="system",exit_code="0"} 2' in prom_text
    assert 'cockpit_command_errors_total{command="quickstart",domain="user",exit_code="1"} 1' in prom_text
    assert "cockpit_command_duration_seconds" in prom_text


def test_cli_telemetry_status_json(capsys):
    rc = main(["telemetry", "--dry-run", "--json"])
    assert rc == ExitCode.SUCCESS
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "ok"
    assert "telemetry" in data
    assert data.get("dry_run") is True


def test_cli_telemetry_export(capsys):
    rc = main(["telemetry", "export"])
    assert rc == ExitCode.SUCCESS
    captured = capsys.readouterr()
    assert "# HELP cockpit_command_total" in captured.out
    assert "# TYPE cockpit_command_total counter" in captured.out


def test_cli_telemetry_reset(capsys):
    rc = main(["telemetry", "reset", "--dry-run", "--json"])
    assert rc == ExitCode.SUCCESS
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data.get("dry_run") is True


# --- T8-14: diagnostics ring (auto-capture WARNING/ERROR, bounded eviction) ---

import logging

from cockpit.telemetry.metrics import (
    DiagnosticsLoggingHandler,
    DiagnosticsRing,
)


def test_diagnostics_ring_record_and_snapshot():
    ring = DiagnosticsRing(capacity=8)
    ring.record("warning", "first warning", {"logger": "a"})
    ring.record("error", "first error")
    events = ring.snapshot()
    assert len(events) == 2
    assert events[0]["level"] == "WARNING"
    assert events[1]["level"] == "ERROR"
    assert events[0]["context"]["logger"] == "a"
    assert ring.snapshot(limit=1)[-1]["event"] == "first error"


def test_diagnostics_ring_capacity_eviction():
    ring = DiagnosticsRing(capacity=4)
    for i in range(10):
        ring.record("error", f"err-{i}")
    events = ring.snapshot()
    assert len(events) == 4
    assert events[0]["event"] == "err-6"
    assert events[-1]["event"] == "err-9"


def test_diagnostics_ring_clear():
    ring = DiagnosticsRing()
    ring.record("error", "x")
    ring.clear()
    assert ring.snapshot() == []


def test_logging_handler_auto_captures_warning_and_error(caplog):
    ring = DiagnosticsRing(capacity=16)
    logger = logging.getLogger("cockpit.test.diag")
    handler = ring.attach_logging_handler(logger)
    try:
        logger.setLevel(logging.INFO)
        logger.info("info should not be captured")
        logger.warning("warn captured")
        logger.error("error captured")
    finally:
        logger.removeHandler(handler)

    events = ring.snapshot()
    levels = [e["level"] for e in events]
    assert "WARNING" in levels and "ERROR" in levels
    assert all("info should not be captured" != e["event"] for e in events)
    assert isinstance(handler, DiagnosticsLoggingHandler)
    ctx = next(e for e in events if e["level"] == "ERROR")
    assert ctx["context"]["logger"] == "cockpit.test.diag"


def test_cli_telemetry_diagnostics_json(capsys):
    from cockpit.telemetry.metrics import get_diagnostics_ring

    ring = get_diagnostics_ring()
    ring.clear()
    ring.record("error", "cli-visible diagnostic")
    rc = main(["telemetry", "diagnostics", "--json"])
    assert rc == ExitCode.SUCCESS
    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "ok"
    assert data["total_events"] >= 1
    assert any(e["event"] == "cli-visible diagnostic" for e in data["diagnostics"])
