"""Tests for freshness.py — canonical freshness-based health projection (W0-03).

Covers four deterministic health states:
    - healthy     (reachable + fresh evidence)
    - degraded    (reachable + stale evidence or no evidence)
    - unreachable (poller reports unreachable/error)
    - unknown     (never polled)

Also tests validate_health_contract for static-label drift detection.
"""

import os
import sys
from datetime import UTC, datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from freshness import (
    FRESHNESS_MULTIPLIER,
    HealthProjection,
    _parse_duration,
    _parse_iso_timestamp,
    derive_health,
    validate_health_contract,
)

# Fixed "now" for deterministic tests: 2026-08-10T12:00:00Z
NOW = datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC)


# ─── healthy: reachable + fresh evidence ─────────────────────────────


class TestHealthyFreshEvidence:
    """healthy requires BOTH reachable AND fresh evidence (age <= 2x poll_interval)."""

    def test_healthy_within_window(self):
        """Signal 60s old, poll_interval=300s → window=600s → healthy."""
        last_signal = (NOW - timedelta(seconds=60)).isoformat().replace("+00:00", "Z")
        proj = derive_health(
            source_id="test_src",
            last_signal_at=last_signal,
            poller_hash="abc123def456",
            poll_interval_s=300,
            now=NOW,
        )
        assert proj.status == "healthy"
        assert proj.poller_hash == "abc123def456"
        assert proj.age_seconds is not None
        assert abs(proj.age_seconds - 60) < 1
        assert proj.freshness_window_s == 600

    def test_healthy_at_window_boundary(self):
        """Signal exactly at window boundary (age == 2x poll_interval) → healthy (<=)."""
        window = 300 * FRESHNESS_MULTIPLIER  # 600s
        last_signal = (NOW - timedelta(seconds=window)).isoformat().replace("+00:00", "Z")
        proj = derive_health(
            source_id="boundary_src",
            last_signal_at=last_signal,
            poller_hash="hash_boundary",
            poll_interval_s=300,
            now=NOW,
        )
        assert proj.status == "healthy"
        assert proj.age_seconds is not None
        assert abs(proj.age_seconds - window) < 1

    def test_healthy_with_1h_poll_interval(self):
        """poll_interval=3600s, signal 30 min old → healthy (window=7200s)."""
        last_signal = (NOW - timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
        proj = derive_health(
            source_id="hourly_src",
            last_signal_at=last_signal,
            poller_hash="hourly_hash",
            poll_interval_s=3600,
            now=NOW,
        )
        assert proj.status == "healthy"
        assert proj.freshness_window_s == 7200


# ─── degraded: reachable + stale evidence ────────────────────────────


class TestDegradedStaleEvidence:
    """degraded when source is reachable but evidence is beyond freshness window."""

    def test_degraded_stale_evidence(self):
        """Signal 1 hour old, poll_interval=300s → window=600s → degraded."""
        last_signal = (NOW - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        proj = derive_health(
            source_id="stale_src",
            last_signal_at=last_signal,
            poller_hash="valid_hash",
            poll_interval_s=300,
            now=NOW,
        )
        assert proj.status == "degraded"
        assert proj.age_seconds is not None
        assert proj.age_seconds > 600  # beyond window
        assert "stale" in proj.reason.lower()

    def test_degraded_massively_stale(self):
        """Signal 3 days old (simulating apple_mail_inbox real state) → degraded."""
        last_signal = (NOW - timedelta(days=3)).isoformat().replace("+00:00", "Z")
        proj = derive_health(
            source_id="apple_mail_inbox",
            last_signal_at=last_signal,
            poller_hash="0ae1a238669fccc8",
            poll_interval_s=300,
            now=NOW,
        )
        assert proj.status == "degraded"
        assert proj.age_seconds is not None
        assert proj.age_seconds > 86400  # > 1 day

    def test_degraded_no_evidence_ever(self):
        """Source reachable (has hash) but last_signal_at is null → degraded."""
        proj = derive_health(
            source_id="no_evidence_src",
            last_signal_at=None,
            poller_hash="some_hash",
            poll_interval_s=300,
            now=NOW,
        )
        assert proj.status == "degraded"
        assert proj.age_seconds is None
        assert "no signal" in proj.reason.lower()

    def test_degraded_unparseable_timestamp(self):
        """Source reachable but last_signal_at is garbage → degraded."""
        proj = derive_health(
            source_id="bad_ts_src",
            last_signal_at="not-a-timestamp",
            poller_hash="valid_hash",
            poll_interval_s=300,
            now=NOW,
        )
        assert proj.status == "degraded"
        assert proj.age_seconds is None


# ─── unreachable: poller reports source down ────────────────────────


class TestUnreachableSource:
    """unreachable when poller hash is 'unreachable' or 'error'."""

    def test_unreachable_hash(self):
        """Poller state = 'unreachable' → unreachable, regardless of last_signal_at."""
        last_signal = (NOW - timedelta(seconds=10)).isoformat().replace("+00:00", "Z")
        proj = derive_health(
            source_id="dead_src",
            last_signal_at=last_signal,  # even with recent signal!
            poller_hash="unreachable",
            poll_interval_s=300,
            now=NOW,
        )
        assert proj.status == "unreachable"
        assert proj.poller_hash == "unreachable"

    def test_error_hash(self):
        """Poller state = 'error' → unreachable."""
        proj = derive_health(
            source_id="error_src",
            last_signal_at="2026-08-09T12:00:00Z",
            poller_hash="error",
            poll_interval_s=300,
            now=NOW,
        )
        assert proj.status == "unreachable"

    def test_unreachable_with_null_last_signal(self):
        """Unreachable AND no signal → unreachable (not unknown)."""
        proj = derive_health(
            source_id="never_worked",
            last_signal_at=None,
            poller_hash="unreachable",
            poll_interval_s=300,
            now=NOW,
        )
        assert proj.status == "unreachable"

    def test_unreachable_ignores_fresh_evidence(self):
        """Even if last_signal_at is very fresh, unreachable hash wins."""
        last_signal = (NOW - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
        proj = derive_health(
            source_id="just_died",
            last_signal_at=last_signal,
            poller_hash="unreachable",
            poll_interval_s=300,
            now=NOW,
        )
        assert proj.status == "unreachable"


# ─── unknown: never polled ───────────────────────────────────────────


class TestUnknownNeverPolled:
    """unknown when source has never been polled (no poller state)."""

    def test_unknown_never_polled(self):
        """poller_hash=None → unknown (source registered but not yet polled)."""
        proj = derive_health(
            source_id="new_source",
            last_signal_at=None,
            poller_hash=None,
            poll_interval_s=300,
            now=NOW,
        )
        assert proj.status == "unknown"
        assert proj.poller_hash is None
        assert "never polled" in proj.reason.lower()

    def test_unknown_with_historical_signal(self):
        """Never polled but has a historical last_signal_at → still unknown."""
        proj = derive_health(
            source_id="ghost_src",
            last_signal_at="2026-08-01T00:00:00Z",
            poller_hash=None,
            poll_interval_s=300,
            now=NOW,
        )
        assert proj.status == "unknown"


# ─── determinism ────────────────────────────────────────────────────


class TestDeterminism:
    """Same inputs must always produce same status — no randomness."""

    def test_same_inputs_same_output(self):
        """Calling derive_health twice with same inputs produces identical status."""
        proj1 = derive_health(
            source_id="det_src",
            last_signal_at="2026-08-10T11:55:00Z",
            poller_hash="stable_hash",
            poll_interval_s=300,
            now=NOW,
        )
        proj2 = derive_health(
            source_id="det_src",
            last_signal_at="2026-08-10T11:55:00Z",
            poller_hash="stable_hash",
            poll_interval_s=300,
            now=NOW,
        )
        assert proj1.status == proj2.status
        assert proj1.reason == proj2.reason

    def test_health_ordering_total(self):
        """Unreachable beats stale evidence: rule 1 is checked before rule 5."""
        stale_signal = (NOW - timedelta(days=10)).isoformat().replace("+00:00", "Z")
        proj = derive_health(
            source_id="multi_issue_src",
            last_signal_at=stale_signal,
            poller_hash="unreachable",
            poll_interval_s=300,
            now=NOW,
        )
        # unreachable should win over degraded
        assert proj.status == "unreachable"


# ─── helper functions ───────────────────────────────────────────────


class TestParseDuration:
    def test_seconds(self):
        assert _parse_duration("300s") == 300

    def test_minutes(self):
        assert _parse_duration("5m") == 300

    def test_hours(self):
        assert _parse_duration("1h") == 3600

    def test_bare_number(self):
        assert _parse_duration("60") == 60

    def test_empty(self):
        assert _parse_duration("") == 300

    def test_garbage(self):
        assert _parse_duration("abc") == 300


class TestParseTimestamp:
    def test_z_suffix(self):
        dt = _parse_iso_timestamp("2026-08-10T12:00:00Z")
        assert dt is not None
        assert dt.year == 2026

    def test_offset(self):
        dt = _parse_iso_timestamp("2026-08-10T12:00:00+00:00")
        assert dt is not None

    def test_none(self):
        assert _parse_iso_timestamp(None) is None

    def test_garbage(self):
        assert _parse_iso_timestamp("garbage") is None


# ─── validate_health_contract ───────────────────────────────────────


class TestValidateHealthContract:
    """Detect when static health labels disagree with derived health."""

    def test_detects_false_healthy(self):
        """Static says healthy but derived says degraded → critical violation."""
        proj = HealthProjection(
            source_id="lying_src",
            status="degraded",
            last_signal_at="2026-08-01T00:00:00Z",
            age_seconds=777600,
            poll_interval_s=300,
            freshness_window_s=600,
            poller_hash="abc123",
            reason="stale evidence",
            derived_at="2026-08-10T12:00:00Z",
        )
        sources = [{"id": "lying_src", "health": "healthy"}]
        violations = validate_health_contract([proj], sources)
        assert len(violations) == 1
        assert violations[0]["severity"] == "critical"
        assert violations[0]["static_health"] == "healthy"
        assert violations[0]["derived_health"] == "degraded"

    def test_no_violation_when_matched(self):
        """Static and derived agree → no violations."""
        proj = HealthProjection(
            source_id="good_src",
            status="healthy",
            last_signal_at="2026-08-10T11:59:00Z",
            age_seconds=60,
            poll_interval_s=300,
            freshness_window_s=600,
            poller_hash="abc123",
            reason="fresh evidence",
            derived_at="2026-08-10T12:00:00Z",
        )
        sources = [{"id": "good_src", "health": "healthy"}]
        violations = validate_health_contract([proj], sources)
        assert len(violations) == 0

    def test_unknown_static_not_flagged(self):
        """Static health='unknown' should not be flagged (it's the honest default)."""
        proj = HealthProjection(
            source_id="new_src",
            status="unknown",
            last_signal_at=None,
            age_seconds=None,
            poll_interval_s=300,
            freshness_window_s=600,
            poller_hash=None,
            reason="never polled",
            derived_at="2026-08-10T12:00:00Z",
        )
        sources = [{"id": "new_src", "health": "unknown"}]
        violations = validate_health_contract([proj], sources)
        assert len(violations) == 0

    def test_warning_for_drift(self):
        """Static says degraded but derived says unreachable → warning."""
        proj = HealthProjection(
            source_id="drift_src",
            status="unreachable",
            last_signal_at=None,
            age_seconds=None,
            poll_interval_s=300,
            freshness_window_s=600,
            poller_hash="unreachable",
            reason="path unreachable",
            derived_at="2026-08-10T12:00:00Z",
        )
        sources = [{"id": "drift_src", "health": "degraded"}]
        violations = validate_health_contract([proj], sources)
        assert len(violations) == 1
        assert violations[0]["severity"] == "warning"
