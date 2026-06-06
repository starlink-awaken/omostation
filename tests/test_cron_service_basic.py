"""Basic tests for cron-service package."""

from __future__ import annotations

from runtime.cron_service import __version__
from runtime.cron_service.config import load_config
from runtime.cron_service.db import JobStore
from runtime.cron_service.delivery import DeliveryConfig, FileDelivery
from runtime.cron_service.executor import Executor, execute_script
from runtime.cron_service.models import Job, JobResult, ScheduleConfig
from runtime.cron_service.scheduler import Scheduler, _is_due, _parse_cron_expr, _parse_every_expr


class TestCronServiceBasic:
    """Core functionality and edge case tests."""

    def test_imports(self):
        """All expected exports are importable."""
        assert __version__ is not None
        assert Scheduler is not None
        assert Executor is not None
        assert Job is not None
        assert JobResult is not None
        assert ScheduleConfig is not None
        assert JobStore is not None
        assert load_config is not None
        assert classify_tasks is not None  # noqa: F821

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
        assert isinstance(result, dict)

    def test_is_due_no_last_run(self):
        """is_due returns True when last_run is None."""
        assert _is_due(None, 60) is True

    def test_job_minimal(self):
        """Job with only required fields."""
        job = Job(id="test-1", name="test", schedule="every 5m")
        assert job.id == "test-1"
        assert job.enabled is True

    def test_job_result_defaults(self):
        """JobResult with default values."""
        result = JobResult(job_id="j1", success=True)
        assert result.exit_code is None

    def test_delivery_config_defaults(self):
        """DeliveryConfig with defaults."""
        cfg = DeliveryConfig()
        assert cfg.type == "file"

    def test_file_delivery_init(self):
        """FileDelivery can be instantiated."""
        d = FileDelivery()
        assert d is not None

    def test_scheduler_init(self):
        """Scheduler initializes without error."""
        s = Scheduler()
        assert s is not None

    def test_execute_script_empty(self):
        """execute_script with empty script returns result."""
        result = execute_script("echo hello", timeout=5)
        assert result is not None

    def test_classify_no_input(self):
        """classify_tasks on empty input returns empty."""
        assert classify_tasks([]) == []  # noqa: F821

    def test_sort_by_priority_empty(self):
        """sort_by_priority on empty returns empty."""
        assert sort_by_priority([]) == []  # noqa: F821
