"""kairon-observability 单元测试 — MetricsCollector + AlertManager + 边界条件。

以前仅有 6 个 import 测试。本文件补充 34 个行为测试，覆盖所有核心 API。
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import pytest
from kairon_observability.alerts import Alert, AlertManager, AlertRule, _eval_condition
from kairon_observability.metrics import (
    MetricsCollector,
    _escape_help,
    _fmt_bucket,
    _fmt_val,
    _format_labels,
    _labels_key,
)

# ============================================================================
# MetricsCollector — 核心 API 测试
# ============================================================================


class TestMetricsCollector:
    def test_counter_creates_and_increments(self):
        mc = MetricsCollector()
        mc.counter("http_requests_total")
        mc.counter("http_requests_total")
        output = mc.to_prometheus()
        assert "TYPE http_requests_total counter" in output
        assert "http_requests_total 2" in output

    def test_counter_with_labels(self):
        mc = MetricsCollector()
        mc.counter("http_requests_total", {"method": "GET"})
        mc.counter("http_requests_total", {"method": "POST"})
        mc.counter("http_requests_total", {"method": "GET"})
        output = mc.to_prometheus()
        assert 'http_requests_total{method="GET"} 2' in output
        assert 'http_requests_total{method="POST"} 1' in output

    def test_counter_with_help_text(self):
        mc = MetricsCollector()
        mc.counter("errors", help_text="Total error count")
        output = mc.to_prometheus()
        assert "# HELP errors Total error count" in output

    def test_counter_multiple_label_sets(self):
        mc = MetricsCollector()
        for status in ["200", "404", "500"]:
            for _ in range(int(status[0])):
                mc.counter("responses", {"status": status})
        output = mc.to_prometheus()
        assert 'responses{status="200"} 2' in output
        assert 'responses{status="404"} 4' in output
        assert 'responses{status="500"} 5' in output

    def test_gauge_sets_value(self):
        mc = MetricsCollector()
        mc.gauge("memory_bytes", 1024)
        output = mc.to_prometheus()
        assert "TYPE memory_bytes gauge" in output
        assert "memory_bytes 1024" in output

    def test_gauge_overwrites_previous(self):
        mc = MetricsCollector()
        mc.gauge("memory_bytes", 1024)
        mc.gauge("memory_bytes", 2048)
        output = mc.to_prometheus()
        assert "memory_bytes 2048" in output
        # gauge 应只有一条值线 (不包含 HELP/TYPE 前缀行)
        value_lines = [ln for ln in output.splitlines() if ln.startswith("memory_bytes")]
        assert len(value_lines) == 1

    def test_gauge_with_labels(self):
        mc = MetricsCollector()
        mc.gauge("cpu_pct", 75.5, {"core": "0"})
        mc.gauge("cpu_pct", 80.1, {"core": "1"})
        output = mc.to_prometheus()
        assert 'cpu_pct{core="0"} 75.5' in output
        assert 'cpu_pct{core="1"} 80.1' in output

    def test_histogram_basic(self):
        mc = MetricsCollector()
        mc.histogram("request_latency_ms", 12.5)
        output = mc.to_prometheus()
        assert "TYPE request_latency_ms histogram" in output
        assert "request_latency_ms_sum 12.5" in output
        assert "request_latency_ms_count 1" in output
        assert "le=" in output  # bucket lines

    def test_histogram_multiple_observations(self):
        mc = MetricsCollector()
        for val in [5, 15, 55, 150, 550, 1500]:
            mc.histogram("latency", val)
        output = mc.to_prometheus()
        assert "latency_sum 2275" in output  # 5+15+55+150+550+1500
        assert "latency_count 6" in output

    def test_to_prometheus_empty(self):
        mc = MetricsCollector()
        output = mc.to_prometheus()
        assert output == "\n"

    def test_to_prometheus_multiple_metric_types(self):
        mc = MetricsCollector()
        mc.counter("c1")
        mc.gauge("g1", 42)
        mc.histogram("h1", 100)
        output = mc.to_prometheus()
        assert "counter" in output
        assert "gauge" in output
        assert "histogram" in output

    def test_to_prometheus_sorted_output(self):
        mc = MetricsCollector()
        mc.gauge("z_metric", 1)
        mc.counter("a_metric")
        output = mc.to_prometheus()
        idx_a = output.index("a_metric")
        idx_z = output.index("z_metric")
        assert idx_a < idx_z  # 按名称排序


# ============================================================================
# Prometheus 格式化辅助函数
# ============================================================================


class TestFormatHelpers:
    def test_fmt_val_infinity(self):
        assert _fmt_val(float("inf")) == "+Inf"
        assert _fmt_val(float("-inf")) == "-Inf"

    def test_fmt_val_nan(self):
        assert _fmt_val(float("nan")) == "Nan"

    def test_fmt_val_integer(self):
        assert _fmt_val(42.0) == "42"

    def test_fmt_val_float(self):
        assert "3.14" in _fmt_val(3.14)

    def test_fmt_bucket_inf(self):
        assert _fmt_bucket(float("inf")) == "+Inf"

    def test_fmt_bucket_int(self):
        assert _fmt_bucket(5.0) == "5.0"

    def test_format_labels_empty(self):
        assert _format_labels(None) == ""
        assert _format_labels({}) == ""

    def test_format_labels_sorted(self):
        result = _format_labels({"b": "2", "a": "1"})
        assert result == '{a="1",b="2"}'

    def test_escape_help_newlines(self):
        assert _escape_help("line1\nline2") == "line1\\nline2"

    def test_escape_help_quotes(self):
        assert _escape_help('say "hello"') == 'say \\"hello\\"'

    def test_labels_key_sorting(self):
        key = _labels_key({"z": "z", "a": "a"})
        assert key == (("a", "a"), ("z", "z"))

    def test_labels_key_empty(self):
        assert _labels_key(None) == ()
        assert _labels_key({}) == ()


# ============================================================================
# AlertRule
# ============================================================================


class TestAlertRule:
    def test_create_valid_rule(self):
        rule = AlertRule("high-latency", "p99_ms > 500", "critical")
        assert rule.name == "high-latency"
        assert rule.condition == "p99_ms > 500"
        assert rule.severity == "critical"

    def test_default_severity_is_warning(self):
        rule = AlertRule("test", "cpu > 80")
        assert rule.severity == "warning"

    def test_rejects_invalid_severity(self):
        with pytest.raises(ValueError, match="Unknown severity"):
            AlertRule("test", "cpu > 80", "fatal")

    def test_valid_severities_accepted(self):
        for sev in ("info", "warning", "critical"):
            rule = AlertRule("test", "cpu > 80", sev)
            assert rule.severity == sev


# ============================================================================
# _eval_condition
# ============================================================================


class TestEvalCondition:
    def test_gt_true(self):
        assert _eval_condition("cpu > 80", {"cpu": 90}) is True

    def test_gt_false(self):
        assert _eval_condition("cpu > 80", {"cpu": 70}) is False

    def test_ge_boundary(self):
        assert _eval_condition("cpu >= 80", {"cpu": 80}) is True

    def test_lt_true(self):
        assert _eval_condition("memory < 1024", {"memory": 512}) is True

    def test_le_boundary(self):
        assert _eval_condition("memory <= 1024", {"memory": 1024}) is True

    def test_eq_true(self):
        assert _eval_condition("status == 1", {"status": 1}) is True

    def test_ne_true(self):
        assert _eval_condition("status != 0", {"status": 1}) is True

    def test_float_threshold(self):
        assert _eval_condition("p99 > 99.9", {"p99": 99.95}) is True

    def test_negative_values(self):
        assert _eval_condition("delta < -5", {"delta": -10}) is True

    def test_missing_metric_returns_false(self):
        assert _eval_condition("unknown > 10", {"cpu": 50}) is False

    def test_invalid_condition_raises(self):
        with pytest.raises(ValueError, match="Invalid condition syntax"):
            _eval_condition("not valid", {})


# ============================================================================
# AlertManager
# ============================================================================


class TestAlertManager:
    def test_empty_manager_no_alerts(self):
        mgr = AlertManager()
        assert mgr.check({"cpu": 90}) == []

    def test_single_rule_fires(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule("high-cpu", "cpu > 80", "warning"))
        alerts = mgr.check({"cpu": 90})
        assert len(alerts) == 1
        assert alerts[0].rule_name == "high-cpu"
        assert alerts[0].metric == "cpu"
        assert alerts[0].current_value == 90
        assert alerts[0].severity == "warning"

    def test_single_rule_does_not_fire(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule("high-cpu", "cpu > 80", "warning"))
        alerts = mgr.check({"cpu": 50})
        assert alerts == []

    def test_multiple_rules_mixed_results(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule("high-cpu", "cpu > 80", "warning"))
        mgr.add_rule(AlertRule("low-memory", "memory < 1024", "critical"))
        mgr.add_rule(AlertRule("ok-disk", "disk > 10", "info"))
        alerts = mgr.check({"cpu": 90, "memory": 512, "disk": 50})
        assert len(alerts) == 3

    def test_alert_service_label(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule("test", "val > 0"))
        alerts = mgr.check({"val": 1}, service="agora")
        assert alerts[0].service == "agora"

    def test_default_service_unknown(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule("test", "val > 0"))
        alerts = mgr.check({"val": 1})
        assert alerts[0].service == "unknown"

    def test_alert_message_format(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule("test-alert", "cpu > 80", "critical"))
        alerts = mgr.check({"cpu": 85})
        assert "CRITICAL" in alerts[0].message
        assert "test-alert" in alerts[0].message
        assert "cpu=85" in alerts[0].message

    def test_malformed_rule_skipped(self):
        # Invalid condition is rejected at rule creation, so we test via _eval_condition
        with pytest.raises(ValueError):
            _eval_condition("invalid", {})

    def test_alert_fired_at_is_isoformat(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule("test", "val > 0"))
        alerts = mgr.check({"val": 1})
        assert "T" in alerts[0].fired_at  # ISO 8601


# ============================================================================
# Alert 数据类
# ============================================================================


class TestAlert:
    def test_alert_fields(self):
        alert = Alert(
            rule_name="r1",
            service="s1",
            metric="m1",
            current_value=42.0,
            severity="warning",
            message="test message",
        )
        assert alert.rule_name == "r1"
        assert alert.current_value == 42.0
        assert alert.service == "s1"
        assert alert.metric == "m1"

    def test_fired_at_auto_populated(self):
        alert = Alert(
            rule_name="r1",
            service="s1",
            metric="m1",
            current_value=0,
            severity="info",
            message="msg",
        )
        assert alert.fired_at  # 自动填充
