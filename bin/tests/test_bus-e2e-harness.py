"""Smoke tests for bin/bus-e2e-harness.py.

Tests the harness binary's own behavior (argument parsing, process
orchestration, output shape). Real cross-process ZMQ verification is
what the harness is for — these tests just ensure the plumbing works.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "bin" / "ssot" / "bus-e2e-harness.py"


def test_help_prints_usage() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "bus-e2e-harness" in result.stdout
    assert "--count" in result.stdout
    assert "--backend" in result.stdout


def test_help_succeeds_regardless_of_zmq_availability() -> None:
    """--help must succeed even if pyzmq isn't installed in current Python."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0


def _has_zmq() -> bool:
    return subprocess.run(
        [sys.executable, "-c", "import zmq"],
        capture_output=True,
    ).returncode == 0


def test_real_harness_passes_50_messages() -> None:
    """End-to-end: harness must report PASS for 50 messages with 0 loss."""
    if not _has_zmq():
        import pytest
        pytest.skip("pyzmq not installed in this Python")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--count", "50", "--json"],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, f"harness failed: stderr={result.stderr!r}"
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["sent"] == 50
    assert data["received"] == 50
    assert data["lost"] == 0
    assert data["extra"] == 0


def test_real_harness_preserves_message_ids() -> None:
    """Every sent envelope id must be received exactly once (no dup, no loss)."""
    if not _has_zmq():
        import pytest
        pytest.skip("pyzmq not installed in this Python")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--count", "30", "--json"],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["ok"]
    assert data["lost_ids"] == []
    assert data["received"] == data["sent"]
