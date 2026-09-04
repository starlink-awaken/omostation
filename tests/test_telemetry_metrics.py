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
