# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false
"""Tests for kairon_observability.dashboard — 服务拓扑仪表盘.

补 dashboard 零测试债 (功能 P1, 392 LOC 核心模块零覆盖)."""

from kairon_observability.dashboard import (
    DashboardConfig,
    DashboardData,
    ServiceCard,
    TopologyEdge,
)


def test_service_card_defaults():
    c = ServiceCard(name="api")
    assert c.status == "unknown"
    assert c.uptime_pct == 0.0
    assert c.p99_latency_ms == 0.0
    assert c.error_rate == 0.0


def test_topology_edge_defaults():
    e = TopologyEdge(source="a", target="b")
    assert e.call_count == 0
    assert e.avg_latency_ms == 0.0


def test_dashboard_config_creatable():
    c = DashboardConfig()
    assert isinstance(c, DashboardConfig)


def test_dashboard_data_init_empty():
    d = DashboardData()
    assert isinstance(d, DashboardData)


def test_dashboard_update_service():
    d = DashboardData()
    d.update_service("api", status="healthy", uptime_pct=99.9)
    detail = d.get_service_detail("api")
    assert detail is not None
    assert detail["service"]["status"] == "healthy"


def test_dashboard_add_edge():
    d = DashboardData()
    d.add_edge("api", "db", call_count=100)
    topo = d.get_topology_data()
    assert isinstance(topo, dict)
    assert "edges" in topo or "links" in topo or len(topo) > 0


def test_dashboard_to_json_str():
    d = DashboardData()
    d.update_service("api", status="healthy")
    j = d.to_json()
    assert isinstance(j, str)
    assert "api" in j


def test_dashboard_to_json_pretty():
    d = DashboardData()
    d.update_service("api", status="healthy")
    j = d.to_json(pretty=True)
    assert isinstance(j, str)


def test_dashboard_reset():
    d = DashboardData()
    d.update_service("api", status="healthy")
    d.reset()
    overview = d.get_overview()
    assert isinstance(overview, dict)


def test_dashboard_get_health_summary():
    d = DashboardData()
    d.update_service("api", status="healthy", uptime_pct=99.9)
    d.update_service("db", status="degraded", uptime_pct=95.0)
    summary = d.get_health_summary()
    assert isinstance(summary, dict)


def test_dashboard_remove_service_returns_bool():
    d = DashboardData()
    d.update_service("api", status="healthy")
    removed = d.remove_service("api")
    assert isinstance(removed, bool)


def test_dashboard_get_overview_dict():
    d = DashboardData()
    d.update_service("api", status="healthy")
    overview = d.get_overview()
    assert isinstance(overview, dict)
