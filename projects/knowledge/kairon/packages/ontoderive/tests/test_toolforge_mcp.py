"""Tests for ToolForge MCP server — 真实工具覆盖 match / select / guide."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

from ontoderive.toolforge.mcp_server import (
    TOOL_DEFS,
    handle_request,
    toolforge_guide,
    toolforge_match,
    toolforge_select,
)


def test_can_import():
    from ontoderive.toolforge import mcp_server

    assert mcp_server is not None


def test_tool_defs_match_advertised_contracts():
    names = {tool["name"] for tool in TOOL_DEFS}
    assert names == {"toolforge_match", "toolforge_select", "toolforge_guide"}


def test_handle_request_initialize():
    resp = handle_request({"method": "initialize", "id": 1, "params": {}})
    assert resp["result"]["serverInfo"]["name"] == "ontoderive-toolforge"


def test_handle_request_tools_list():
    resp = handle_request({"method": "tools/list", "id": 1})
    names = [tool["name"] for tool in resp["result"]["tools"]]
    assert names == ["toolforge_match", "toolforge_select", "toolforge_guide"]


def test_handle_request_match():
    resp = handle_request(
        {
            "method": "tools/call",
            "id": 2,
            "params": {"name": "toolforge_match", "arguments": {"goal": "分析新能源汽车市场"}},
        }
    )
    assert "result" in resp
    assert "methodologies" in resp["result"]


def test_handle_request_select():
    resp = handle_request(
        {
            "method": "tools/call",
            "id": 3,
            "params": {"name": "toolforge_select", "arguments": {"goal": "设计数字化平台"}},
        }
    )
    assert isinstance(resp["result"], list)


def test_handle_request_guide():
    resp = handle_request(
        {
            "method": "tools/call",
            "id": 4,
            "params": {"name": "toolforge_guide", "arguments": {"goal": "产业园区规划"}},
        }
    )
    assert "推荐推导框架" in resp["result"]


def test_handle_request_unknown_tool():
    resp = handle_request({"method": "tools/call", "id": 5, "params": {"name": "does_not_exist"}})
    assert "error" in resp


def test_direct_call_wrappers_are_callable():
    assert callable(toolforge_match)
    assert callable(toolforge_select)
    assert callable(toolforge_guide)
