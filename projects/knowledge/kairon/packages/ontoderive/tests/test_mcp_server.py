"""MCP服务器测试"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from ontoderive.mcp_server import TOOL_DEFS, handle_mcp_request


def test_tools_list():
    resp = handle_mcp_request({"id": 1, "method": "tools/list"})
    tools = resp["result"]["tools"]
    assert len(tools) == 5
    names = [t["name"] for t in tools]
    assert names == ["derive", "trace", "validate", "list_entities", "pipeline_status"]


def test_initialize():
    resp = handle_mcp_request({"id": 2, "method": "initialize"})
    assert resp["result"]["serverInfo"]["name"] == "ontoderive"
    assert resp["result"]["serverInfo"]["version"] == "3.6.4"
    assert "tools" in resp["result"]["capabilities"]


def test_unknown_method():
    resp = handle_mcp_request({"id": 3, "method": "unknown"})
    assert "error" in resp
    assert resp["error"]["code"] == -32601


def test_pipeline_status():
    resp = handle_mcp_request({"id": 4, "method": "tools/call", "params": {"name": "pipeline_status", "arguments": {}}})
    assert "result" in resp
    assert resp["result"]["server"] == "ontoderive-mcp"


def test_validate():
    resp = handle_mcp_request(
        {
            "id": 5,
            "method": "tools/call",
            "params": {"name": "validate", "arguments": {"schema": "DATA", "data": "| D-F1 | fact |"}},
        }
    )
    assert "result" in resp
    assert "results" in resp["result"]


def test_list_entities():
    resp = handle_mcp_request(
        {"id": 6, "method": "tools/call", "params": {"name": "list_entities", "arguments": {"meta_type": "FACT"}}}
    )
    assert "result" in resp
    assert any(entry["meta_type"] == "FACT" for entry in resp["result"])


def test_trace():
    resp = handle_mcp_request(
        {"id": 7, "method": "tools/call", "params": {"name": "trace", "arguments": {"entity_id": "D-F1"}}}
    )
    assert "result" in resp
    assert resp["result"]["entity_id"] == "D-F1"


def test_unknown_tool():
    resp = handle_mcp_request(
        {"id": 8, "method": "tools/call", "params": {"name": "nonexistent_tool", "arguments": {}}}
    )
    assert "error" in resp


def test_tool_defs_schemas():
    for t in TOOL_DEFS:
        assert "name" in t
        assert "description" in t
        assert "inputSchema" in t
        assert "type" in t["inputSchema"]
