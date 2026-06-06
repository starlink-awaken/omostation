"""Supplementary tests for cron-service scheduler — pure logic coverage gaps.

Existing test_core.py covers the primary paths. This file fills the
remaining branches and edge cases in the scheduler module.
"""

from datetime import UTC, datetime, timedelta

from runtime.cron_service.scheduler import (
    CronScheduler,
    _is_due,
    _parse_cron_expr,
    _parse_every_expr,
)

# ── _parse_every_expr: additional edge cases ─────────────────────────


class TestParseEveryExprEdgeCases:
    """Edge cases in _parse_every_expr not covered by test_core."""

    def test_hours_plural_text(self):
        """'every 2 hours' returns 7200 seconds."""
        assert _parse_every_expr("every 2 hours") == 7200

    def test_minutes_plural_text(self):
        """'every 10 minutes' returns 600 seconds."""
        assert _parse_every_expr("every 10 minutes") == 600

    def test_minutes_abbreviation(self):
        """'every 15 min' returns 900 seconds."""
        assert _parse_every_expr("every 15 min") == 900

    def test_single_hour(self):
        """'every 1 hour' returns 3600 seconds."""
        assert _parse_every_expr("every 1 hour") == 3600

    def test_large_number_minutes(self):
        """'every 360m' returns 21600 seconds."""
        assert _parse_every_expr("every 360m") == 21600

    def test_nonexpr_returns_none(self):
        """'every' without a number returns None."""
        assert _parse_every_expr("every") is None

    def test_just_every_prefix(self):
        """'everyxyz' does not match 'every ' pattern → None."""
        assert _parse_every_expr("everyxyz") is None

    def test_non_numeric_minutes(self):
        """'every abcm' → invalid number → None."""
        assert _parse_every_expr("every abcm") is None

    def test_non_numeric_hours(self):
        """'every xh' → invalid number → None."""
        assert _parse_every_expr("every xh") is None


# ── _parse_cron_expr: additional edge cases ─────────────────────────


class TestParseCronExprEdgeCases:
    """Edge cases in _parse_cron_expr not covered by test_core."""

    def test_star_star_minimal(self):
        """'* * * * *' returns a dict-like value (legacy compat)."""
        result = _parse_cron_expr("* * * * *")
        assert isinstance(result, dict)
        assert "next_due" in result

    def test_range_interval(self):
        """'*/15 7-23 * * *' is valid."""
        result = _parse_cron_expr("*/15 7-23 * * *")
        assert result is not None
        assert isinstance(result, float)

    def test_specific_time(self):
        """'30 4 * * *' (4:30 daily) is valid."""
        result = _parse_cron_expr("30 4 * * *")
        assert result is not None
        assert isinstance(result, float)

    def test_weekday_schedule(self):
        """'0 9 * * 1-5' (weekdays at 9am) is valid."""
        result = _parse_cron_expr("0 9 * * 1-5")
        assert result is not None
        assert isinstance(result, float)

    def test_empty_string(self):
        """Empty string is invalid → None."""
        assert _parse_cron_expr("") is None

    def test_partial_expression(self):
        """'* * *' (3 fields) is invalid → None."""
        assert _parse_cron_expr("* * *") is None


# ── _is_due: additional edge cases ──────────────────────────────────


class TestIsDueEdgeCases:
    """_is_due branches not covered by test_core."""

    def test_none_schedule_is_due(self):
        """schedule_expr is None → always due."""
        assert _is_due("job-1", None) is True

    def test_none_schedule_with_last_run(self):
        """schedule_expr is None is still due even with last_run."""
        now = datetime.now(UTC)
        last_run = now - timedelta(minutes=5)
        assert _is_due("job-1", None, last_run_at=last_run) is True

    def test_legacy_int_format_no_last_run(self):
        """Legacy format: _is_due(None, 300) → True (last_run_at is None)."""
        assert _is_due("job-1", 300, last_run_at=None) is True

    def test_legacy_int_format_with_last_run(self):
        """Legacy format: _is_due(some_date, 300) → False (last_run_at not None)."""
        now = datetime.now(UTC)
        last_run = now - timedelta(minutes=5)
        assert _is_due("job-1", 300, last_run_at=last_run) is False

    def test_cron_expr_due(self):
        """Cron '*/5 * * * *' with last_run >5m ago → due."""
        now = datetime.now(UTC)
        last_run = now - timedelta(minutes=10)
        assert _is_due("job-1", "*/5 * * * *", last_run_at=last_run) is True

    def test_cron_expr_not_due(self):
        """Cron '*/5 * * * *' with last_run <5m ago → not due."""
        now = datetime.now(UTC)
        last_run = now - timedelta(minutes=1)
        result = _is_due("job-1", "*/5 * * * *", last_run_at=last_run)
        assert result is False

    def test_invalid_cron_falls_back(self):
        """Invalid cron expression → fallback to True."""
        assert _is_due("job-1", "not-a-cron", last_run_at=datetime.now(UTC)) is True

    def test_fallback_empty_schedule(self):
        """Schedule that fails both every-parser and cron-parser → True."""
        now = datetime.now(UTC)
        last_run = now - timedelta(hours=1)
        assert _is_due("job-1", "custom-unknown-format", last_run_at=last_run) is True

    def test_new_job_with_cron_waits(self):
        """Cron job created <60s ago → not due."""
        now = datetime.now(UTC)
        created_at = now - timedelta(seconds=10)
        assert _is_due("job-1", "0 2 * * *", last_run_at=None, created_at=created_at) is False

    def test_old_job_with_cron_is_due(self):
        """Cron job created >60s ago with no last_run → due."""
        now = datetime.now(UTC)
        created_at = now - timedelta(minutes=10)
        assert _is_due("job-1", "0 2 * * *", last_run_at=None, created_at=created_at) is True


# ── CronScheduler: non-async surface tests ──────────────────────────


class TestCronSchedulerSurface:
    """CronScheduler initialization and synchronous properties."""

    def test_init_defaults(self):
        """Default init sets expected internal state."""
        s = CronScheduler()
        assert s._running is False
        assert s._tick_task is None
        assert s._executor is not None
        assert s.start_time is None
        assert s.last_tick_time is None
        assert s.tick_count == 0

    def test_is_running_property_before_start(self):
        """is_running returns False before start()."""
        s = CronScheduler()
        assert s.is_running is False

    def test_multiple_instances_independent(self):
        """Two CronScheduler instances do not share state."""
        s1 = CronScheduler()
        s2 = CronScheduler()
        assert s1 is not s2
        assert s1.tick_count == s2.tick_count == 0
        s1.tick_count = 42
        assert s2.tick_count == 0
