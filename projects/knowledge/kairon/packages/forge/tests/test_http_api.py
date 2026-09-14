"""Forge http_api.py 单元测试

测试覆盖:
- 模块导入与结构
- 顶层函数（query_assets, build_asset_stats, get_categories, export_assets, query_graph）
- ForgeAPIHandler HTTP handler 方法
- respond/error 辅助函数
- 错误路径
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import io
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))


SAMPLE_TOOLS = [
    {
        "id": "claude-code",
        "name": "Claude Code",
        "type": "tool",
        "status": "active",
        "category": ["MCP", "AI"],
        "capabilities": ["code", "chat"],
    },
    {
        "id": "ollama-local",
        "name": "Ollama",
        "type": "tool",
        "status": "active",
        "category": ["Local"],
        "capabilities": ["chat", "code"],
    },
    {
        "id": "vision-tool",
        "name": "Vision Analyzer",
        "type": "tool",
        "status": "active",
        "category": ["AI"],
        "capabilities": ["vision", "image"],
    },
    {
        "id": "candidate-x",
        "name": "Candidate X",
        "type": "tool",
        "status": "candidate",
        "category": ["Experimental"],
        "capabilities": ["code"],
    },
]

SAMPLE_REGISTRY = {
    "schema_version": "1.2",
    "tools": SAMPLE_TOOLS,
    "event_log": [],
}

SAMPLE_GRAPH = {
    "stats": {"total_nodes": 3, "total_edges": 2},
    "nodes": [
        {"id": "claude-code", "type": "Tool", "label": "Claude Code"},
        {"id": "cap-code", "type": "Capability", "label": "code"},
    ],
    "edges": [
        {"source": "claude-code", "target": "cap-code", "relation": "HAS_CAPABILITY"},
    ],
}


@pytest.fixture
def setup_api(monkeypatch, tmp_path):
    """Patch REGISTRY and GRAPH paths to temp files."""
    import http_api

    reg_file = tmp_path / "tools-registry.json"
    reg_file.write_text(json.dumps(SAMPLE_REGISTRY))
    monkeypatch.setattr(http_api, "REGISTRY", reg_file)

    graph_dir = tmp_path / "graph"
    graph_dir.mkdir()
    graph_file = graph_dir / "graph.json"
    graph_file.write_text(json.dumps(SAMPLE_GRAPH))
    monkeypatch.setattr(http_api, "GRAPH", graph_file)

    return http_api


def _make_handler(api, path="/health", headers=None):
    """Helper to create a ForgeAPIHandler instance with mocked HTTP plumbing."""
    handler = api.ForgeAPIHandler.__new__(api.ForgeAPIHandler)
    handler.path = path
    handler.headers = headers or {"Origin": "*"}
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()
    handler.wfile = MagicMock()
    return handler


# ═══════════════════════════════════════════════════
# 1. 模块导入与结构
# ═══════════════════════════════════════════════════


class TestImports:
    def test_module_imports(self):
        import http_api

        assert hasattr(http_api, "query_assets")
        assert hasattr(http_api, "build_asset_stats")
        assert hasattr(http_api, "get_categories")
        assert hasattr(http_api, "export_assets")
        assert hasattr(http_api, "query_graph")
        assert hasattr(http_api, "ForgeAPIHandler")
        assert hasattr(http_api, "respond")
        assert hasattr(http_api, "error")
        assert hasattr(http_api, "main")

    def test_constants_defined(self):
        import http_api

        assert hasattr(http_api, "REGISTRY")
        assert hasattr(http_api, "GRAPH")
        assert hasattr(http_api, "PORT")
        assert http_api.PORT == 8766


# ═══════════════════════════════════════════════════
# 2. query_assets
# ═══════════════════════════════════════════════════


class TestQueryAssets:
    def test_search_by_query(self, setup_api):
        api = setup_api
        result, total = api.query_assets(query="claude", limit=10)
        assert isinstance(result, list)
        assert total > 0
        assert any(t["id"] == "claude-code" for t in result)

    def test_search_with_capability_filter(self, setup_api):
        api = setup_api
        result, total = api.query_assets(capabilities=["vision"], limit=5)
        assert isinstance(result, list)
        for t in result:
            caps = [c.lower() for c in t.get("capabilities", [])]
            assert any("vision" in c for c in caps)

    def test_search_empty_query_returns_all_active(self, setup_api):
        api = setup_api
        result, total = api.query_assets(limit=10)
        assert len(result) == 4  # all tools (query with no filters returns everything)
        assert total == 4

    def test_search_no_match(self, setup_api):
        api = setup_api
        result, total = api.query_assets(query="zzz_nonexistent", limit=10)
        assert result == []
        assert total == 0

    def test_faceted_by_category(self, setup_api):
        api = setup_api
        result, total = api.query_assets(category="MCP", limit=10)
        assert isinstance(result, list)
        assert total > 0
        for t in result:
            assert "MCP" in t.get("category", [])

    def test_faceted_by_status(self, setup_api):
        api = setup_api
        result, total = api.query_assets(status="candidate", limit=10)
        assert total >= 1
        for t in result:
            assert t.get("status") == "candidate"

    def test_pagination(self, setup_api):
        api = setup_api
        result1, total = api.query_assets(limit=2, offset=0)
        result2, _ = api.query_assets(limit=2, offset=2)
        assert len(result1) == 2
        assert len(result2) == 2
        assert result1[0]["id"] != result2[0]["id"]  # different pages


# ═══════════════════════════════════════════════════
# 3. build_asset_stats / get_categories / export_assets
# ═══════════════════════════════════════════════════


class TestAssetStats:
    def test_build_asset_stats(self, setup_api):
        api = setup_api
        stats = api.build_asset_stats()
        assert stats["total"] == 4
        assert "active" in stats["by_status"]
        assert stats["by_status"]["active"] == 3
        assert "by_category" in stats
        assert "by_type" in stats
        assert "top_sources" in stats
        assert stats["total_capabilities"] > 0

    def test_get_categories(self, setup_api):
        api = setup_api
        cats = api.get_categories()
        assert isinstance(cats, list)
        assert len(cats) > 0
        assert "name" in cats[0]
        assert "count" in cats[0]

    def test_export_csv(self, setup_api):
        api = setup_api
        csv = api.export_assets(format="csv")
        assert isinstance(csv, str)
        assert csv.startswith("id,name,")
        lines = csv.strip().split("\n")
        assert len(lines) == 5  # header + 4 tools

    def test_export_filtered_csv(self, setup_api):
        api = setup_api
        csv = api.export_assets(format="csv", category="MCP")
        lines = csv.strip().split("\n")
        assert len(lines) == 2  # header + 1 tool (claude-code)

    def test_export_json(self, setup_api):
        api = setup_api
        json_str = api.export_assets(format="json")
        data = json.loads(json_str)
        assert isinstance(data, list)
        assert len(data) == 4


# ═══════════════════════════════════════════════════
# 4. query_graph
# ═══════════════════════════════════════════════════


class TestQueryGraph:
    def test_query_graph_found(self, setup_api):
        api = setup_api
        result = api.query_graph("Claude")
        assert isinstance(result, list)
        assert any(n["id"] == "claude-code" for n in result)

    def test_query_graph_not_found(self, setup_api):
        api = setup_api
        result = api.query_graph("ZZZZZ")
        assert result == []


# ═══════════════════════════════════════════════════
# 5. load_registry / load_graph
# ═══════════════════════════════════════════════════


class TestLoadFunctions:
    def test_load_registry(self, setup_api):
        api = setup_api
        reg = api.load_registry()
        assert "tools" in reg
        assert reg["schema_version"] == "1.2"

    def test_load_graph(self, setup_api):
        api = setup_api
        g = api.load_graph()
        assert "nodes" in g
        assert "edges" in g

    def test_load_graph_missing(self, setup_api, monkeypatch):
        import http_api

        missing_path = Path("/nonexistent/graph.json")
        monkeypatch.setattr(http_api, "GRAPH", missing_path)
        g = http_api.load_graph()
        assert g == {"nodes": [], "edges": [], "stats": {}}


# ═══════════════════════════════════════════════════
# 6. respond / error 辅助函数
# ═══════════════════════════════════════════════════


class TestRespond:
    def test_respond_sends_json(self):
        import http_api

        handler = MagicMock()
        handler.headers = {"Origin": "*"}
        http_api.respond(handler, {"status": "ok"}, 200)
        handler.send_response.assert_called_with(200)
        handler.send_header.assert_any_call("Content-Type", "application/json; charset=utf-8")
        handler.send_header.assert_any_call("Access-Control-Allow-Origin", "*")
        handler.wfile.write.assert_called_once()

    def test_error_sends_error_json(self):
        import http_api

        handler = MagicMock()
        handler.headers = {"Origin": "*"}
        http_api.error(handler, "bad request", 400)
        handler.send_response.assert_called_with(400)
        written = handler.wfile.write.call_args[0][0]
        decoded = json.loads(written)
        assert decoded["error"] == "bad request"


# ═══════════════════════════════════════════════════
# 7. ForgeAPIHandler — _parse_path / _read_body
# ═══════════════════════════════════════════════════


class TestForgeAPIHandlerParse:
    def test_parse_simple_path(self):
        import http_api

        handler_instance = http_api.ForgeAPIHandler.__new__(http_api.ForgeAPIHandler)
        handler_instance.path = "/health"
        path, qs = handler_instance._parse_path()
        assert path == "/health"
        assert qs == {}

    def test_parse_path_with_query(self):
        import http_api

        handler_instance = http_api.ForgeAPIHandler.__new__(http_api.ForgeAPIHandler)
        handler_instance.path = "/assets?q=PDF&limit=5"
        path, qs = handler_instance._parse_path()
        assert path == "/assets"
        assert qs == {"q": "PDF", "limit": "5"}

    def test_parse_path_trailing_slash(self):
        import http_api

        handler_instance = http_api.ForgeAPIHandler.__new__(http_api.ForgeAPIHandler)
        handler_instance.path = "/assets/"
        path, qs = handler_instance._parse_path()
        assert path == "/assets"

    def test_parse_url_encoded_query(self):
        import http_api

        handler_instance = http_api.ForgeAPIHandler.__new__(http_api.ForgeAPIHandler)
        handler_instance.path = "/assets?category=AI%2F%E6%A8%A1%E5%9E%8B"
        path, qs = handler_instance._parse_path()
        assert qs.get("category") == "AI/模型"

    def test_read_body_empty(self):
        import http_api

        handler_instance = http_api.ForgeAPIHandler.__new__(http_api.ForgeAPIHandler)
        handler_instance.headers = {"Content-Length": "0"}
        handler_instance.rfile = MagicMock()
        assert handler_instance._read_body() == {}

    def test_read_body_with_data(self):
        import http_api

        handler_instance = http_api.ForgeAPIHandler.__new__(http_api.ForgeAPIHandler)
        data = json.dumps({"name": "test"})
        handler_instance.headers = {"Content-Length": str(len(data))}
        handler_instance.rfile = io.BytesIO(data.encode())
        body = handler_instance._read_body()
        assert body["name"] == "test"


# ═══════════════════════════════════════════════════
# 8. ForgeAPIHandler — do_GET
# ═══════════════════════════════════════════════════


class TestForgeAPIHandlerGET:
    def test_get_health(self, setup_api):
        api = setup_api
        h = _make_handler(api, "/health")
        h.do_GET()
        h.send_response.assert_called_with(200)
        written = json.loads(h.wfile.write.call_args[0][0])
        assert written["status"] == "ok"
        assert written["tools"] == 4
        assert written["active"] == 3

    def test_get_status(self, setup_api):
        api = setup_api
        h = _make_handler(api, "/status")
        h.do_GET()
        written = json.loads(h.wfile.write.call_args[0][0])
        assert written["tools"] == 4
        assert written["active"] == 3
        assert written["candidates"] == 1

    def test_get_assets_search(self, setup_api):
        api = setup_api
        h = _make_handler(api, "/assets?q=claude&limit=5")
        h.do_GET()
        written = json.loads(h.wfile.write.call_args[0][0])
        assert isinstance(written, dict)
        assert "total" in written
        assert "assets" in written
        assert any(t["id"] == "claude-code" for t in written["assets"])

    def test_get_assets_empty_search(self, setup_api):
        api = setup_api
        h = _make_handler(api, "/assets?limit=5")
        h.do_GET()
        written = json.loads(h.wfile.write.call_args[0][0])
        assert written["total"] == 4

    def test_get_asset_by_id(self, setup_api):
        api = setup_api
        h = _make_handler(api, "/assets/claude-code")
        h.do_GET()
        written = json.loads(h.wfile.write.call_args[0][0])
        assert written["id"] == "claude-code"
        assert written["name"] == "Claude Code"

    def test_get_asset_not_found(self, setup_api):
        api = setup_api
        h = _make_handler(api, "/assets/nonexistent")
        h.do_GET()
        h.send_response.assert_called_with(404)
        written = json.loads(h.wfile.write.call_args[0][0])
        assert "error" in written

    def test_get_assets_stats(self, setup_api):
        api = setup_api
        h = _make_handler(api, "/assets/stats")
        h.do_GET()
        written = json.loads(h.wfile.write.call_args[0][0])
        assert written["total"] == 4

    def test_get_assets_categories(self, setup_api):
        api = setup_api
        h = _make_handler(api, "/assets/categories")
        h.do_GET()
        written = json.loads(h.wfile.write.call_args[0][0])
        assert isinstance(written, list)
        assert len(written) > 0

    def test_get_assets_export_csv(self, setup_api):
        api = setup_api
        h = _make_handler(api, "/assets/export?format=csv")
        h.do_GET()
        h.send_response.assert_called_with(200)

    def test_get_graph_stats(self, setup_api):
        api = setup_api
        h = _make_handler(api, "/graph/stats")
        h.do_GET()
        written = json.loads(h.wfile.write.call_args[0][0])
        assert written["total_nodes"] == 3

    def test_get_graph_query(self, setup_api):
        api = setup_api
        h = _make_handler(api, "/graph/query?q=Claude")
        h.do_GET()
        written = json.loads(h.wfile.write.call_args[0][0])
        assert isinstance(written, list)
        assert any(n["id"] == "claude-code" for n in written)

    def test_get_recommend(self, setup_api):
        api = setup_api
        h = _make_handler(api, "/recommend?tool_id=claude-code")
        h.do_GET()
        written = json.loads(h.wfile.write.call_args[0][0])
        assert isinstance(written, dict)

    def test_get_unknown_path(self, setup_api):
        api = setup_api
        h = _make_handler(api, "/unknown/route")
        h.do_GET()
        h.send_response.assert_called_with(404)
        written = json.loads(h.wfile.write.call_args[0][0])
        assert "error" in written


# ═══════════════════════════════════════════════════
# 9. ForgeAPIHandler — do_OPTIONS
# ═══════════════════════════════════════════════════


class TestForgeAPIHandlerOPTIONS:
    def test_options_returns_204(self):
        import http_api

        handler_instance = http_api.ForgeAPIHandler.__new__(http_api.ForgeAPIHandler)
        handler_instance.headers = {"Origin": "*"}
        handler_instance.send_response = MagicMock()
        handler_instance.send_header = MagicMock()
        handler_instance.end_headers = MagicMock()

        handler_instance.do_OPTIONS()

        handler_instance.send_response.assert_called_with(204)
        handler_instance.send_header.assert_any_call("Access-Control-Allow-Origin", "*")
        handler_instance.send_header.assert_any_call("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
