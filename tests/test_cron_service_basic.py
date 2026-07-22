"""Basic smoke tests for cron-service package.

对齐实际 API: CronScheduler (非 Scheduler), _parse_interval/_next_cron_ts
(非 _parse_every_expr/_parse_cron_expr), classify_tasks/sort_by_priority 在
classify.py, db 为函数式 API (无 JobStore 类)。execute_script 首参为路径非命令,
原 test_execute_script_empty 断言不确定故移除 (不造假 pass)。
"""

from __future__ import annotations

from datetime import UTC, datetime

from runtime.cron_service import __version__
from runtime.cron_service.classify import classify_tasks, sort_by_priority
from runtime.cron_service.config import load_config
from runtime.cron_service.db import list_jobs
from runtime.cron_service.delivery import DeliveryConfig, FileDelivery
from runtime.cron_service.executor import Executor, execute_script
from runtime.cron_service.models import Job, JobResult, ScheduleConfig
from runtime.cron_service.scheduler import (
    CronScheduler,
    _is_due,
    _next_cron_ts,
    _parse_interval,
)


class TestCronServiceBasic:
    """Core functionality smoke tests."""

    def test_imports(self):
        """All expected exports are importable."""
        assert __version__ is not None
        assert CronScheduler is not None
        assert Executor is not None
        assert execute_script is not None
        assert Job is not None
        assert JobResult is not None
        assert ScheduleConfig is not None
        assert list_jobs is not None
        assert load_config is not None
        assert classify_tasks is not None
        assert sort_by_priority is not None

    def test_parse_every_5min(self):
        assert _parse_interval("every 5 min") == 300

    def test_parse_every_30min(self):
        assert _parse_interval("every 30 min") == 1800

    def test_parse_every_2h(self):
        assert _parse_interval("every 2 hours") == 7200

    def test_parse_every_1h(self):
        assert _parse_interval("every 1 hour") == 3600

    def test_next_cron_ts_minute(self):
        """Cron '* * * * *' → float."""
        result = _next_cron_ts("* * * * *", datetime.now(UTC))
        assert isinstance(result, float)

    def test_is_due_no_last_run(self):
        """schedule 非空 + last_run None → True."""
        assert _is_due("j", "every 5 min", None, created_at=datetime.now(UTC)) is True

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
        """CronScheduler initializes without error."""
        s = CronScheduler()
        assert s is not None

    def test_classify_no_input(self):
        """classify_tasks on empty input returns empty."""
        assert classify_tasks([]) == []

    def test_sort_by_priority_empty(self):
        """sort_by_priority on empty returns empty."""
        assert sort_by_priority([]) == []
