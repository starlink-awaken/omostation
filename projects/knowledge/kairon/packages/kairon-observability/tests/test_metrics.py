# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false
"""Tests for kairon_observability.metrics — Prometheus-style 收集器.

补 metrics 零测试债 (功能 P1, 场景审计标的)."""

from kairon_observability.metrics import MetricsCollector


def test_counter_creates():
    mc = MetricsCollector()
    mc.counter("requests_total")
    out = mc.to_prometheus()
    assert "requests_total" in out
    assert "# TYPE requests_total counter" in out


def test_counter_increments():
    mc = MetricsCollector()
    mc.counter("req")
    mc.counter("req")
    out = mc.to_prometheus()
    assert "req 2" in out


def test_counter_with_labels():
    mc = MetricsCollector()
    mc.counter("req", {"method": "GET"})
    mc.counter("req", {"method": "POST"})
    out = mc.to_prometheus()
    assert 'method="GET"' in out
    assert 'method="POST"' in out


def test_counter_same_labelset_increments():
    mc = MetricsCollector()
    mc.counter("req", {"m": "GET"})
    mc.counter("req", {"m": "GET"})
    out = mc.to_prometheus()
    assert 'req{m="GET"} 2' in out


def test_gauge_sets_value():
    mc = MetricsCollector()
    mc.gauge("memory", 1024)
    out = mc.to_prometheus()
    assert "memory 1024" in out
    assert "# TYPE memory gauge" in out


def test_gauge_overwrites_previous():
    mc = MetricsCollector()
    mc.gauge("mem", 100)
    mc.gauge("mem", 200)
    out = mc.to_prometheus()
    assert "mem 200" in out


def test_histogram_records_observations():
    mc = MetricsCollector()
    mc.histogram("latency", 12.5)
    mc.histogram("latency", 45.0)
    out = mc.to_prometheus()
    assert "latency_count 2" in out
    assert "latency_sum" in out
    assert "# TYPE latency histogram" in out


def test_to_prometheus_has_help_and_type():
    mc = MetricsCollector()
    mc.counter("x", help_text="my counter")
    out = mc.to_prometheus()
    assert "# HELP x my counter" in out
    assert "# TYPE x counter" in out


def test_to_prometheus_empty_returns_str():
    mc = MetricsCollector()
    out = mc.to_prometheus()
    assert isinstance(out, str)


def test_mixed_metrics_types():
    mc = MetricsCollector()
    mc.counter("req")
    mc.gauge("mem", 100)
    mc.histogram("lat", 5.0)
    out = mc.to_prometheus()
    assert "# TYPE req counter" in out
    assert "# TYPE mem gauge" in out
    assert "# TYPE lat histogram" in out
