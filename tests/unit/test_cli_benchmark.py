"""
Unit tests for omlxc benchmark CLI commands and renderers.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from typer.testing import CliRunner

from omlxc.cli import app
from omlxc.client.models import DaemonEnvelope


def test_cli_benchmark_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["benchmark", "--help"])
    assert result.exit_code == 0
    assert "Benchmark local model latency and generation throughput." in result.output
    assert "run" in result.output
    assert "report" in result.output


def test_cli_benchmark_report_mock(monkeypatch: Any) -> None:
    runner = CliRunner()
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.benchmark_report.return_value = DaemonEnvelope(
        schema_version=1,
        request_id="req-bench",
        data=[
            {
                "run_id": "run-1",
                "model_id": "qwen-3.8-27b",
                "placement_id": "p-mbp",
                "node_id": "mbp-m5-max-128g",
                "ttft_ms": 24.5,
                "tps": 52.8,
                "tested_at": "2026-08-16T12:00:00Z",
            }
        ],
    )
    monkeypatch.setattr("omlxc.cli._client_factory", lambda _socket: mock_client)

    result = runner.invoke(app, ["benchmark", "report"])
    assert result.exit_code == 0
    assert "Benchmark Leaderboard" in result.output
    assert "qwen" in result.output
    assert "52.8" in result.output


def test_cli_benchmark_run_mock(monkeypatch: Any) -> None:
    runner = CliRunner()
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.benchmark_model.return_value = DaemonEnvelope(
        schema_version=1,
        request_id="req-bench-run",
        data={
            "run_id": "run-2",
            "model_id": "coding",
            "placement_id": "coding-local",
            "node_id": "mbp-m5-max-128g",
            "ttft_ms": 18.2,
            "tps": 65.4,
            "cold_load_ms": 110.0,
            "warm_load_ms": 20.0,
            "tested_at": "2026-08-16T12:05:00Z",
        },
    )
    monkeypatch.setattr("omlxc.cli._client_factory", lambda _socket: mock_client)

    result = runner.invoke(app, ["benchmark", "run", "coding"])
    assert result.exit_code == 0
    assert "Benchmark Result" in result.output
    assert "coding" in result.output
    assert "65.4 tok/s" in result.output
