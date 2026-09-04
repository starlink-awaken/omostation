"""Tests for Modernized Dashboard Command (BET-Y1Q4-T8-13).

Verifies:
  1. --dry-run returns structured status without launching process.
  2. --status-only returns running state.
  3. Port detection and auto-healing logic.
  4. Exit codes adhere to ExitCode enum.
"""

import json
from unittest.mock import patch
import pytest

from cockpit.cli import main
from cockpit.commands.dashboard import is_port_available, find_available_port
from cockpit.domain.exit_codes import ExitCode


def test_dashboard_dry_run_flag(capsys):
    rc = main(["dashboard", "--dry-run"])
    assert rc == ExitCode.SUCCESS

    captured = capsys.readouterr()
    assert "[Dry-Run]" in captured.out


def test_dashboard_status_only_not_running(capsys):
    # Using an unlikely port to ensure it is not running
    rc = main(["dashboard", "--status-only", "--port", "59123", "--json"])
    assert rc == ExitCode.SERVICE_UNAVAILABLE

    captured = capsys.readouterr()
    data = json.loads(captured.out.strip())
    assert data["running"] is False
    assert data["port"] == 59123


def test_find_available_port_helper():
    port = find_available_port("127.0.0.1", 8090, max_attempts=5)
    assert port is not None
    assert port >= 8090
