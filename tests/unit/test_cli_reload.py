"""
Unit tests for daemon reload API and CLI command.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from omlxc.cli import app
from omlxc.client.models import DaemonEnvelope

runner = CliRunner()


def test_cli_daemon_reload_human_output() -> None:
    mock_envelope = DaemonEnvelope(
        schema_version=1,
        request_id="req-123",
        data={
            "status": "reloaded",
            "reloaded_at": "2026-08-16T13:00:00Z",
            "nodes_count": 3,
            "models_count": 5,
        },
    )

    with patch("omlxc.client.DaemonClient.reload_daemon", new_callable=AsyncMock) as mock_reload:
        mock_reload.return_value = mock_envelope
        result = runner.invoke(app, ["daemon", "reload"])
        assert result.exit_code == 0
        assert "com.omlxc.daemon reloaded" in result.output
        assert "nodes=3" in result.output
        assert "models=5" in result.output


def test_cli_daemon_reload_json_output() -> None:
    mock_envelope = DaemonEnvelope(
        schema_version=1,
        request_id="req-123",
        data={
            "status": "reloaded",
            "reloaded_at": "2026-08-16T13:00:00Z",
            "nodes_count": 3,
            "models_count": 5,
        },
    )

    with patch("omlxc.client.DaemonClient.reload_daemon", new_callable=AsyncMock) as mock_reload:
        mock_reload.return_value = mock_envelope
        result = runner.invoke(app, ["daemon", "reload", "--json"])
        assert result.exit_code == 0
        assert '"status":"reloaded"' in result.output
        assert '"nodes_count":3' in result.output
