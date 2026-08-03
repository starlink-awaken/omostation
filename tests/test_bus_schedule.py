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

        # Job should be registered in bus-foundation's croniter backend
        # _jobs values are 4-tuples: (timestamp, callback, interval_seconds, last_run)
        import bus_foundation

        croniter = bus_foundation._backends["croniter"]
        assert len(croniter._jobs) >= 1  # type: ignore[reportAttributeAccessIssue]
        # Find our job by interval (every 1h = 3600 seconds)
        found = any(interval == 3600 for _, _, interval, _ in croniter._jobs.values())  # type: ignore[reportAttributeAccessIssue]
        assert found

    def test_schedule_invalid_expr_type_raises(self):
        try:
            schedule(123)  # type: ignore
            assert False, "should have raised"
        except TypeError:
            pass
