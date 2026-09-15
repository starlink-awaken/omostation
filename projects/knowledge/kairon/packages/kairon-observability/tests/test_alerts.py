"""Tests for kairon_observability.alerts — 规则告警引擎.

补 alerts 零测试债 (功能 P1, 场景审计标的 kairon-observability 测试薄)."""

import pytest
from kairon_observability.alerts import Alert, AlertManager, AlertRule


def test_alert_rule_defaults_warning():
    r = AlertRule(name="high-latency", condition="p99_ms > 500")
    assert r.severity == "warning"


def test_alert_rule_invalid_severity_raises():
    with pytest.raises(ValueError):
        AlertRule(name="bad", condition="x > 1", severity="invalid")


def test_alert_rule_severity_levels():
    for sev in ("info", "warning", "critical"):
        r = AlertRule(name="r", condition="x > 1", severity=sev)
        assert r.severity == sev


def test_alert_manager_check_fires():
    mgr = AlertManager()
    mgr.add_rule(AlertRule("high-latency", "p99_ms > 500", "critical"))
    alerts = mgr.check({"p99_ms": 520})
    assert len(alerts) == 1
    a = alerts[0]
    assert isinstance(a, Alert)
    assert a.rule_name == "high-latency"
    assert a.severity == "critical"
    assert a.current_value == 520
    assert "p99_ms" in a.message


def test_alert_manager_check_no_fire_below_threshold():
    mgr = AlertManager()
    mgr.add_rule(AlertRule("high-latency", "p99_ms > 500"))
    alerts = mgr.check({"p99_ms": 100})
    assert len(alerts) == 0


def test_alert_manager_missing_metric_no_fire():
    mgr = AlertManager()
    mgr.add_rule(AlertRule("rule", "missing_metric > 10"))
    alerts = mgr.check({"other": 5})
    assert len(alerts) == 0  # missing metric → no alert


def test_alert_manager_multiple_rules_partial_fire():
    mgr = AlertManager()
    mgr.add_rule(AlertRule("r1", "p99_ms > 500", "critical"))
    mgr.add_rule(AlertRule("r2", "availability_pct < 99.9", "warning"))
    alerts = mgr.check({"p99_ms": 600, "availability_pct": 99.95})
    assert len(alerts) == 1
    assert alerts[0].rule_name == "r1"


def test_alert_fired_at_populated():
    mgr = AlertManager()
    mgr.add_rule(AlertRule("r", "x > 1"))
    alerts = mgr.check({"x": 5})
    assert alerts[0].fired_at != ""


def test_alert_manager_invalid_rule_skipped_gracefully():
    mgr = AlertManager()
    mgr.add_rule(AlertRule("bad", "!!invalid syntax!!"))
    mgr.add_rule(AlertRule("good", "x > 1"))
    alerts = mgr.check({"x": 5})
    assert len(alerts) == 1  # malformed skipped, good fires
    assert alerts[0].rule_name == "good"


def test_alert_manager_service_label_attached():
    mgr = AlertManager()
    mgr.add_rule(AlertRule("r", "x > 1"))
    alerts = mgr.check({"x": 5}, service="kos")
    assert alerts[0].service == "kos"


def test_eval_condition_operators():
    """条件解析支持 > >= < <= == != 全操作符."""

    mgr = AlertManager()
    for cond, val, should_fire in [
        ("x > 5", 6, True),
        ("x > 5", 5, False),
        ("x >= 5", 5, True),
        ("x < 5", 4, True),
        ("x <= 5", 5, True),
        ("x == 5", 5, True),
        ("x != 5", 6, True),
    ]:
        mgr._rules = []  # reset
        mgr.add_rule(AlertRule("test", cond))
        alerts = mgr.check({"x": val})
        assert len(alerts) == (1 if should_fire else 0), f"Failed: {cond} with x={val}"
