"""Basic tests for cron-service package."""

from __future__ import annotations

from runtime.cron_service import __version__
from runtime.cron_service.scheduler import CronScheduler, _is_due, _parse_cron_expr, _parse_every_expr


class TestCronServiceBasic:
    """Core functionality and edge case tests."""

    def test_imports(self):
        """All expected exports are importable."""
        assert __version__ is not None
        assert CronScheduler is not None

    def test_parse_every_5m(self):
        assert _parse_every_expr("every 5m") == 300

    def test_parse_every_30m(self):
        assert _parse_every_expr("every 30m") == 1800

    def test_parse_every_2h(self):
        assert _parse_every_expr("every 2h") == 7200

    def test_parse_every_1h(self):
        assert _parse_every_expr("every 1h") == 3600

    def test_parse_cron_minute(self):
        """Cron expression with only minute field."""
        result = _parse_cron_expr("* * * * *")
        assert result is not None

    def test_is_due_with_valid_schedule(self):
        """_is_due with valid schedule and no last run."""
        result = _is_due("test", "* * * * *", None)
        assert isinstance(result, bool)

    def test_scheduler_init(self):
        """CronScheduler initializes without error."""
        s = CronScheduler()
        assert s is not None
