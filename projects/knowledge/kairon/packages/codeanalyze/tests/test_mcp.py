"""Basic tests for MCP server module."""

from pathlib import Path

from codeanalyze.mcp import FORMAT_VERSION, _error, _ok, _resolve


class TestHelpers:
    def test_ok_response(self):
        result = _ok({"status": "ok", "format_version": FORMAT_VERSION})
        assert result["status"] == "ok"
        assert result["format_version"] == FORMAT_VERSION
        assert result["status"] == "ok"

    def test_ok_merges_data(self):
        result = _ok({"entities": 10, "relations": 5, "format_version": FORMAT_VERSION})
        assert result["entities"] == 10
        assert result["relations"] == 5
        assert result["status"] == "ok"

    def test_error_response(self):
        result = _error("something went wrong")
        assert result["status"] == "error"
        assert result["error"] == "something went wrong"
        assert result["format_version"] == FORMAT_VERSION

    def test_resolve_relative(self):
        resolved = _resolve(".")
        assert resolved == str(Path(".").resolve())

    def test_resolve_absolute(self):
        resolved = _resolve("/tmp")
        assert resolved == "/private/tmp" or resolved == "/tmp"

    def test_format_version_constant(self):
        assert FORMAT_VERSION == "codeanalyze-v1"


class TestTools:
    """Integration tests for MCP tools — smoke tests that they return expected shapes."""

    def test_analyze_project_return_shape(self):
        from codeanalyze.mcp import analyze_project

        result = analyze_project(".")
        # 应该返回 dict 含 status
        assert isinstance(result, dict)
        assert "status" in result

    def test_codegraph_search_return_shape(self):
        from codeanalyze.mcp import codegraph_search

        result = codegraph_search("def ", path=".")
        assert isinstance(result, dict)
        assert "status" in result

    def test_status_tool(self):
        # 直接测试 status 逻辑
        from codeanalyze.mcp import analyze_project

        result = analyze_project("/nonexistent/path/xyz")
        assert isinstance(result, dict)
