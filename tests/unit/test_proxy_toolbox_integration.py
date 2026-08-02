"""F-09: mcp_proxy 迁移 — toolbox MCP server 纳入 proxy 管理测试。"""

from __future__ import annotations


def test_known_services_includes_wps_office_mcp():
    """KNOWN_SERVICES 包含 wps-office-mcp (F-09 proxy 迁移)。"""
    from agora.mcp.mcp_bootstrap import KNOWN_SERVICES

    assert "wps-office-mcp" in KNOWN_SERVICES
    svc = KNOWN_SERVICES["wps-office-mcp"]
    assert svc["command"] == "node"
    assert svc["source"] == "toolbox"
    assert any("dist/index.js" in a for a in svc["args"])


def test_known_services_keeps_core_services():
    """核心服务不受影响。"""
    from agora.mcp.mcp_bootstrap import KNOWN_SERVICES

    for name in ("kos", "codeanalyze", "metaos", "cockpit"):
        assert name in KNOWN_SERVICES


def test_build_enabled_services_includes_wps(monkeypatch):
    """_build_enabled_services 对 wps-office-mcp 生成 proxy 配置条目。"""
    from agora.mcp.mcp_bootstrap import _build_enabled_services

    svc = {
        "name": "wps-office-mcp",
        "enabled": True,
        "command": "node",
        "args": ["/Users/xiamingxing/ToolBox/mcp/wps-office-mcp/dist/index.js"],
    }
    result = _build_enabled_services([svc])
    assert len(result) == 1
    assert result[0]["name"] == "wps-office-mcp"
    assert result[0]["mcp_endpoint"] == "stdio"


def test_capability_domain_description_updated():
    """capability 域描述反映 toolbox 纳入。"""
    from agora.mcp_proxy.feature_gate import DEFAULT_BOS_DOMAINS

    cap = DEFAULT_BOS_DOMAINS["capability"]
    assert cap["enabled"] is True
    assert "toolbox" in cap["description"]
