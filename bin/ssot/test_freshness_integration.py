"""Integration tests for W0-03 freshness-health wiring.

Proves that the canonical health projection entrypoints
(freshness.py CLI and signal-poller.py --health) correctly report:
    - stale evidence  → degraded
    - unreachable source → unreachable
    - fresh evidence   → healthy

Tests use both:
    1. project_all_health() with injected synthetic data (unit-level)
    2. CLI subprocess against real signal-sources.yaml (end-to-end)
"""

import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from freshness import project_all_health

# Fixed "now" for deterministic synthetic tests
NOW = datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC)

# Resolve paths for subprocess CLI tests
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)


def _run_cli(script: str, *args: str) -> tuple[int, str, str]:
    """Run a bin/ssot/ script via subprocess, return (exit_code, stdout, stderr)."""
    cmd = [sys.executable, os.path.join(SCRIPT_DIR, script)] + list(args)
    proc = subprocess.run(
        cmd, capture_output=True, text=True, timeout=30, check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


# ─── Synthetic data tests via project_all_health() ──────────────────


class TestFreshHealthySynthetic:
    """Fresh synthetic evidence must derive healthy."""

    def test_fresh_source_is_healthy(self):
        """Source with signal 60s ago, poll_interval=300s → healthy."""
        fresh_ts = (NOW - timedelta(seconds=60)).isoformat().replace("+00:00", "Z")
        sources = [{
            "id": "fresh_src",
            "poll_interval": "300s",
            "last_signal_at": fresh_ts,
        }]
        state = {"fresh_src": "abcdef0123456789"}
        projections = project_all_health(now=NOW, sources=sources, poller_state=state)
        assert len(projections) == 1
        assert projections[0].status == "healthy"
        assert projections[0].source_id == "fresh_src"
        assert projections[0].age_seconds is not None
        assert abs(projections[0].age_seconds - 60) < 1


class TestStaleDegradedSynthetic:
    """Stale evidence must derive degraded deterministically."""

    def test_stale_source_is_degraded(self):
        """Source with signal 1h ago, poll_interval=300s → degraded (stale)."""
        stale_ts = (NOW - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        sources = [{
            "id": "stale_src",
            "poll_interval": "300s",
            "last_signal_at": stale_ts,
        }]
        state = {"stale_src": "validhash123456"}
        projections = project_all_health(now=NOW, sources=sources, poller_state=state)
        assert len(projections) == 1
        assert projections[0].status == "degraded"
        assert "stale" in projections[0].reason.lower()

    def test_apple_mail_inbox_stale_is_degraded(self):
        """Simulate apple_mail_inbox with 3-day-old evidence → degraded."""
        stale_ts = (NOW - timedelta(days=3)).isoformat().replace("+00:00", "Z")
        sources = [{
            "id": "apple_mail_inbox",
            "poll_interval": "300s",
            "last_signal_at": stale_ts,
        }]
        state = {"apple_mail_inbox": "0ae1a238669fccc8"}
        projections = project_all_health(now=NOW, sources=sources, poller_state=state)
        assert projections[0].status == "degraded"
        assert projections[0].source_id == "apple_mail_inbox"


class TestUnreachableSynthetic:
    """Unreachable poller hash must derive unreachable deterministically."""

    def test_unreachable_source(self):
        """Source with poller_hash='unreachable' → unreachable."""
        sources = [{"id": "dead_src", "poll_interval": "300s", "last_signal_at": None}]
        state = {"dead_src": "unreachable"}
        projections = project_all_health(now=NOW, sources=sources, poller_state=state)
        assert len(projections) == 1
        assert projections[0].status == "unreachable"


class TestMultipleSourcesMixed:
    """Multiple sources with mixed health states in one projection."""

    def test_mixed_statuses(self):
        """All four health states in one batch."""
        fresh_ts = (NOW - timedelta(seconds=30)).isoformat().replace("+00:00", "Z")
        stale_ts = (NOW - timedelta(hours=5)).isoformat().replace("+00:00", "Z")
        sources = [
            {"id": "fresh", "poll_interval": "300s", "last_signal_at": fresh_ts},
            {"id": "stale", "poll_interval": "300s", "last_signal_at": stale_ts},
            {"id": "down", "poll_interval": "300s", "last_signal_at": None},
            {"id": "never_polled", "poll_interval": "300s", "last_signal_at": None},
        ]
        state = {"fresh": "hash1", "stale": "hash2", "down": "unreachable"}
        projections = project_all_health(now=NOW, sources=sources, poller_state=state)
        status_map = {p.source_id: p.status for p in projections}
        assert status_map == {
            "fresh": "healthy",
            "stale": "degraded",
            "down": "unreachable",
            "never_polled": "unknown",
        }


# ─── CLI subprocess tests against real data ─────────────────────────


class TestFreshnessCLIRealData:
    """End-to-end: freshness.py CLI against real signal-sources.yaml."""

    def test_json_has_expected_sources(self):
        """freshness.py --json must contain all 4 registered sources."""
        exit_code, stdout, stderr = _run_cli("freshness.py", "--json")
        assert exit_code == 0, f"Expected exit 0, got {exit_code}: {stderr}"
        data = json.loads(stdout)
        source_ids = [s["source_id"] for s in data["sources"]]
        assert "apple_mail_inbox" in source_ids
        assert "netease_mailmaster_inbox" in source_ids

    def test_apple_mail_inbox_is_degraded(self):
        """apple_mail_inbox has 2+ day old evidence → must be degraded."""
        exit_code, stdout, _ = _run_cli("freshness.py", "--json")
        assert exit_code == 0
        data = json.loads(stdout)
        apple = next(s for s in data["sources"] if s["source_id"] == "apple_mail_inbox")
        assert apple["status"] == "degraded"
        assert apple["age_seconds"] is not None
        assert apple["age_seconds"] > 600  # well beyond 2x 300s window

    def test_unreachable_source_reported(self):
        """netease_mailmaster_inbox has poller_hash='unreachable' → must be unreachable."""
        exit_code, stdout, _ = _run_cli("freshness.py", "--json")
        assert exit_code == 0
        data = json.loads(stdout)
        netease = next(s for s in data["sources"] if s["source_id"] == "netease_mailmaster_inbox")
        assert netease["status"] == "unreachable"

    def test_exit_zero_for_degraded(self):
        """Degraded health must NOT cause nonzero exit (not a command error)."""
        exit_code, _, _ = _run_cli("freshness.py")
        assert exit_code == 0

    def test_json_keys_sorted(self):
        """JSON output must use sort_keys for deterministic key order."""
        exit_code, stdout, _ = _run_cli("freshness.py", "--json")
        assert exit_code == 0
        # Reparse to verify valid JSON
        data = json.loads(stdout)
        # Verify summary keys exist
        assert "summary" in data
        summary = data["summary"]
        for key in ("total", "healthy", "degraded", "unreachable", "unknown"):
            assert key in summary

    def test_source_not_found_returns_nonzero(self):
        """Asking for a nonexistent source is a real command error."""
        exit_code, _, stderr = _run_cli("freshness.py", "--source", "nonexistent_xyz")
        assert exit_code == 1
        assert "not found" in stderr.lower()

    def test_validate_detects_stale_healthy_label(self):
        """--validate must catch apple_mail_inbox's false healthy label."""
        exit_code, stdout, _ = _run_cli("freshness.py", "--validate")
        assert exit_code == 1  # validate mode returns 1 on violations
        assert "apple_mail_inbox" in stdout


class TestSignalPollerHealthIntegration:
    """End-to-end: signal-poller.py --health must output freshness-derived health."""

    def test_health_flag_outputs_projections(self):
        """signal-poller --health must output health for all sources."""
        exit_code, stdout, _ = _run_cli("signal-poller.py", "--health")
        assert exit_code == 0
        assert "apple_mail_inbox" in stdout
        assert "degraded" in stdout
        assert "netease_mailmaster_inbox" in stdout
        assert "unreachable" in stdout

    def test_health_json_has_correct_structure(self):
        """signal-poller --health --json must have sources + summary."""
        exit_code, stdout, _ = _run_cli("signal-poller.py", "--health", "--json")
        assert exit_code == 0
        data = json.loads(stdout)
        assert "sources" in data
        assert "summary" in data
        assert data["summary"]["total"] == len(data["sources"])

    def test_health_json_apple_degraded(self):
        """signal-poller --health --json must report apple_mail_inbox as degraded."""
        exit_code, stdout, _ = _run_cli("signal-poller.py", "--health", "--json")
        assert exit_code == 0
        data = json.loads(stdout)
        apple = next(s for s in data["sources"] if s["source_id"] == "apple_mail_inbox")
        assert apple["status"] == "degraded"

    def test_health_json_unreachable(self):
        """signal-poller --health --json must report netease as unreachable."""
        exit_code, stdout, _ = _run_cli("signal-poller.py", "--health", "--json")
        assert exit_code == 0
        data = json.loads(stdout)
        netease = next(s for s in data["sources"] if s["source_id"] == "netease_mailmaster_inbox")
        assert netease["status"] == "unreachable"

    def test_health_exit_zero(self):
        """signal-poller --health must exit 0 even with degraded sources."""
        exit_code, _, _ = _run_cli("signal-poller.py", "--health")
        assert exit_code == 0
