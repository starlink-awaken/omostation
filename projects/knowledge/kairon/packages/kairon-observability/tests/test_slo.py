# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false
"""Tests for kairon_observability.slo — SLO 追踪 (P99/可用性).

补 slo 零测试债 (功能 P1, 471 LOC 核心模块零覆盖)."""

from kairon_observability.slo import SLODefinition, SLOStatus, SLOTracker


def test_slo_definition_defaults_threshold_to_target():
    d = SLODefinition(
        name="s",
        service="api",
        metric="latency_ms",
        target_p99_ms=500,
        target_availability=99.9,
        window_hours=1.0,
    )
    assert d.threshold_ms == 500  # defaults to target_p99_ms


def test_slo_definition_custom_threshold():
    d = SLODefinition(
        name="s",
        service="api",
        metric="latency_ms",
        target_p99_ms=500,
        target_availability=99.9,
        window_hours=1.0,
        threshold_ms=300,
    )
    assert d.threshold_ms == 300


def test_tracker_record_latency_returns_status():
    t = SLOTracker()
    t.record_latency("api", 12.5)
    t.record_latency("api", 45.0)
    status = t.get_slo("api", "latency_ms")
    assert isinstance(status, SLOStatus)
    assert status.window_hours > 0


def test_tracker_record_error_success():
    t = SLOTracker()
    t.record_success("api")
    t.record_error("api")
    t.record_success("api")
    status = t.get_slo("api", "latency_ms")
    assert isinstance(status, SLOStatus)


def test_tracker_track_returns_status():
    t = SLOTracker()
    t.track("api", "latency_ms", 100.0)
    status = t.get_slo("api", "latency_ms")
    assert isinstance(status, SLOStatus)


def test_tracker_clear_returns_int():
    t = SLOTracker()
    t.track("api", "latency_ms", 100.0)
    cleared = t.clear(service="api")
    assert isinstance(cleared, int)


def test_tracker_get_compliance():
    t = SLOTracker()
    slo = SLODefinition(
        name="s1",
        service="api",
        metric="latency_ms",
        target_p99_ms=500,
        target_availability=99.0,
        window_hours=1.0,
    )
    t.record_latency("api", 100.0)
    t.record_latency("api", 200.0)
    comp = t.get_compliance(slo)
    assert comp.slo_name == "s1"
    assert isinstance(comp.overall_compliant, bool)
    assert isinstance(comp.p99_ms, float)


def test_tracker_check_breaches_empty_slos():
    t = SLOTracker()
    breaches = t.check_breaches([])
    assert breaches == []


def test_tracker_window_constants():
    assert SLOTracker.WINDOW_1H == 1.0
    assert SLOTracker.WINDOW_24H == 24.0
    assert SLOTracker.WINDOW_7D == 168.0
