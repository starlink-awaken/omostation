"""Supplementary tests for cron-service scheduler — pure logic coverage gaps.

对齐 scheduler.py 实际 API。原测试 import 的 _parse_every_expr / _parse_cron_expr
为未实现的设计 spec, 实际实现命名不同 (_parse_interval / _next_cron_ts);
_is_due 签名与语义也与 spec 不同 (schedule 空→False, 非 None→True)。
本文件按实现真实行为重写, 不造假 pass。
"""

from datetime import UTC, datetime, timedelta

from runtime.cron_service.scheduler import (
    CronScheduler,
    _is_due,
    _next_cron_ts,
    _parse_interval,
)

# ── _parse_interval: 'every X unit' → 秒数 ──────────────────────────


class TestParseInterval:
    """_parse_interval 解析 'every X unit' (两段格式) → 秒数."""

    def test_hours_plural_text(self):
        """'every 2 hours' → 7200."""
        assert _parse_interval("every 2 hours") == 7200

    def test_minutes_plural_text(self):
        """'every 10 minutes' → 600."""
        assert _parse_interval("every 10 minutes") == 600

    def test_minutes_abbreviation(self):
        """'every 15 min' → 900."""
        assert _parse_interval("every 15 min") == 900

    def test_single_hour(self):
        """'every 1 hour' → 3600."""
        assert _parse_interval("every 1 hour") == 3600

    def test_no_every_prefix_returns_none(self):
        """无 'every ' 前缀 → None."""
        assert _parse_interval("360m") is None

    def test_empty_rest_returns_none(self):
        """'every' (无数值) → None."""
        assert _parse_interval("every") is None

    def test_non_every_string_returns_none(self):
        """'everyxyz' 不匹配 'every ' → None."""
        assert _parse_interval("everyxyz") is None

    def test_single_token_returns_seconds(self):
        """'every 360m' (单段缩写) → 21600 (_parse_interval 单段支持)."""
        assert _parse_interval("every 360m") == 21600

    def test_invalid_number_returns_none(self):
        """'every abc min' (非数字) → ValueError → None."""
        assert _parse_interval("every abc min") is None


# ── _next_cron_ts: croniter 精确下次触发时间戳 ───────────────────────


class TestNextCronTs:
    """_next_cron_ts(schedule, after) → float | None."""

    def test_star_star_returns_float(self):
        """'* * * * *' → float."""
        result = _next_cron_ts("* * * * *", datetime.now(UTC))
        assert isinstance(result, float)

    def test_range_interval_returns_float(self):
        """'*/15 7-23 * * *' → float."""
        result = _next_cron_ts("*/15 7-23 * * *", datetime.now(UTC))
        assert isinstance(result, float)

    def test_specific_time_returns_float(self):
        """'30 4 * * *' (4:30 daily) → float."""
        result = _next_cron_ts("30 4 * * *", datetime.now(UTC))
        assert isinstance(result, float)

    def test_weekday_schedule_returns_float(self):
        """'0 9 * * 1-5' (工作日9点) → float."""
        result = _next_cron_ts("0 9 * * 1-5", datetime.now(UTC))
        assert isinstance(result, float)

    def test_empty_string_returns_none(self):
        """空串 → croniter 抛错 → None."""
        assert _next_cron_ts("", datetime.now(UTC)) is None

    def test_partial_expression_returns_none(self):
        """'* * *' (3段) → croniter 抛错 → None."""
        assert _next_cron_ts("* * *", datetime.now(UTC)) is None

    def test_invalid_expression_returns_none(self):
        """'not-a-cron' → None."""
        assert _next_cron_ts("not-a-cron", datetime.now(UTC)) is None

    def test_float_after_accepted(self):
        """after 为 float (epoch) 也接受 → float."""
        result = _next_cron_ts("* * * * *", 0.0)
        assert isinstance(result, float)


# ── _is_due: 真实分支 (schedule 空→False, last_run None→True) ─────────


class TestIsDue:
    """_is_due(job_id, schedule, last_run, *, created_at) 真实分支."""

    def test_empty_schedule_not_due(self):
        """schedule='' → not schedule → False."""
        assert _is_due("job-1", "", None, created_at=datetime.now(UTC)) is False

    def test_none_last_run_is_due(self):
        """schedule 非空 + last_run None → True."""
        assert (
            _is_due("job-1", "every 5 min", None, created_at=datetime.now(UTC)) is True
        )

    def test_every_overdue(self):
        """every 5m, last_run 10m 前 → 到期."""
        now = datetime.now(UTC)
        last_run = now - timedelta(minutes=10)
        assert _is_due("job-1", "every 5 min", last_run, created_at=now) is True

    def test_every_not_due(self):
        """every 5m, last_run 1m 前 → 未到期."""
        now = datetime.now(UTC)
        last_run = now - timedelta(minutes=1)
        assert _is_due("job-1", "every 5 min", last_run, created_at=now) is False

    def test_every_invalid_returns_false(self):
        """every 格式非法 (interval None) → False."""
        now = datetime.now(UTC)
        last_run = now - timedelta(minutes=10)
        assert _is_due("job-1", "every xyz", last_run, created_at=now) is False

    def test_cron_due(self):
        """*/5 * * * *, last_run 10m 前 → 到期."""
        now = datetime.now(UTC)
        last_run = now - timedelta(minutes=10)
        assert _is_due("job-1", "*/5 * * * *", last_run, created_at=now) is True

    def test_cron_not_due(self):
        """*/5 * * * *, last_run 1m 前 → 下次触发未到 → False."""
        now = datetime.now(UTC)
        last_run = now  # 刚跑过 → 下次触发严格在 now 之后 → 未到期
        assert _is_due("job-1", "*/5 * * * *", last_run, created_at=now) is False

    def test_invalid_cron_returns_false(self):
        """非法 cron → _next_cron_ts None → ts is None → False (非 fallback True)."""
        now = datetime.now(UTC)
        last_run = now - timedelta(hours=1)
        assert _is_due("job-1", "not-a-cron", last_run, created_at=now) is False


# ── CronScheduler: 初始化与同步属性 ──────────────────────────────────


class TestCronSchedulerSurface:
    """CronScheduler 初始化内部状态 (实际属性: _thread 非 _tick_task)."""

    def test_init_defaults(self):
        """默认 init 设置预期内部状态."""
        s = CronScheduler()
        assert s._running is False
        assert s._thread is None
        assert s._executor is not None
        assert s.start_time == 0.0
        assert s.last_tick_time == 0.0
        assert s.tick_count == 0

    def test_is_running_before_start(self):
        """start() 前 is_running → False."""
        s = CronScheduler()
        assert s.is_running is False

    def test_multiple_instances_independent(self):
        """两个 CronScheduler 实例状态独立."""
        s1 = CronScheduler()
        s2 = CronScheduler()
        assert s1 is not s2
        assert s1.tick_count == s2.tick_count == 0
        s1.tick_count = 42
        assert s2.tick_count == 0
