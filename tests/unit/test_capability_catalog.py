"""B1: capability_catalog 能力目录 + capability_status 能力粒度度量测试。"""

from __future__ import annotations

from agora.mcp.bos_metrics import BOSMetrics, MetricsStore
from agora.mcp.capability_catalog import CapabilityCatalog


def _make_metrics(tmp_path) -> BOSMetrics:
    m = BOSMetrics()
    m._store = MetricsStore(str(tmp_path / "metrics.db"))
    m._store._enabled = True
    m._stats.clear()
    return m


def _make_catalog(tmp_path, yaml_content: str) -> CapabilityCatalog:
    p = tmp_path / "bos.yaml"
    p.write_text(yaml_content, encoding="utf-8")
    return CapabilityCatalog(bos_yaml=str(p))


def test_capability_status_aggregates_by_action(monkeypatch, tmp_path):
    """capability_status 按 domain/package/action 全维度聚合。"""
    from agora.mcp import bos_metrics as bm

    m = _make_metrics(tmp_path)
    monkeypatch.setattr(bm, "bos_metrics", m)
    m.record("bos://capability/wps-office-mcp/invoke", success=True, latency_ms=50)
    m.record("bos://capability/wps-office-mcp/invoke", success=True, latency_ms=70)
    m.record("bos://capability/wps-office-mcp/invoke", success=False, latency_ms=100)

    status = m.capability_status()
    caps = status["capabilities"]
    key = "bos://capability/wps-office-mcp/invoke"
    assert key in caps, f"缺少 {key}: {list(caps)[:5]}"
    entry = caps[key]
    assert entry["calls"] == 3
    assert entry["success"] == 2
    assert entry["failure"] == 1
    assert entry["success_rate"] == round(2 / 3, 4)


def test_catalog_loads_declarations(tmp_path):
    """catalog 从 bos-services.yaml 加载声明。"""
    yaml_content = """
services:
- uri: bos://capability/foo/invoke
  domain: capability
  package: foo
  action: invoke
  description: test capability
  status: active
  transport: stdio
- uri: bos://memory/bar/search
  domain: memory
  package: bar
  action: search
  description: memory search
  status: deprecated
  transport: internal
"""
    c = _make_catalog(tmp_path, yaml_content)
    caps = c.load()
    assert len(caps) == 2
    assert caps["bos://capability/foo/invoke"]["status"] == "active"
    assert caps["bos://memory/bar/search"]["domain"] == "memory"


def test_report_identifies_stale_capabilities(monkeypatch, tmp_path):
    """active 但无调用的能力被识别为僵尸候选。"""
    from agora.mcp import bos_metrics as bm

    yaml_content = """
services:
- uri: bos://capability/foo/invoke
  domain: capability
  package: foo
  action: invoke
  description: active but unused
  status: active
- uri: bos://capability/bar/invoke
  domain: capability
  package: bar
  action: invoke
  description: used capability
  status: active
"""
    c = _make_catalog(tmp_path, yaml_content)
    c.load()

    # 替换 metrics 单例为测试实例 (只记录 bar)
    m = _make_metrics(tmp_path)
    m.record("bos://capability/bar/invoke", success=True, latency_ms=10)
    monkeypatch.setattr(bm, "bos_metrics", m)

    report = c.report(stale_days=0.0)
    uris = [x["uri"] for x in report["stale_candidates"]]
    assert "bos://capability/foo/invoke" in uris, "未调用能力应被判为僵尸"
    assert "bos://capability/bar/invoke" not in uris, "已调用能力不应被判僵尸"
