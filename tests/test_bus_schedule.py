"""Test schedule() decorator — 3 cases."""
from agora.bus import schedule


class TestSchedule:
    def test_schedule_returns_decorator(self):
        @schedule("every 5m")
        def fn() -> None:
            pass

        assert callable(fn)

    def test_schedule_registers_job(self):
        @schedule("every 1h")
        def fn() -> None:
            pass

        # Job should be registered in croniter backend
        from agora.bus import _croniter
        assert len(_croniter._jobs) >= 1
        # Find our job
        found = any(
            cron_expr == "every 1h" for cron_expr, _, _ in _croniter._jobs.values()
        )
        assert found

    def test_schedule_invalid_expr_type_raises(self):
        try:
            schedule(123)  # type: ignore
            assert False, "should have raised"
        except TypeError:
            pass
