"""L3 入口层测试"""

from ecos.l3.entry import GovernanceCLI, GovernanceMCP


class TestGovernanceCLI:
    """治理 CLI 测试"""
    
    def test_run_check(self):
        cli = GovernanceCLI()
        result = cli.run(["check"])
        assert result == 0
    
    def test_run_status(self):
        cli = GovernanceCLI()
        result = cli.run(["status"])
        assert result == 0
    
    def test_run_unknown(self):
        cli = GovernanceCLI()
        result = cli.run(["unknown"])
        assert result == 1
    
    def test_print_help(self):
        cli = GovernanceCLI()
        # 测试帮助输出不会崩溃
        cli._print_help()


class TestGovernanceMCP:
    """治理 MCP 测试"""
    
    def test_call_check(self):
        mcp = GovernanceMCP()
        result = mcp.call_tool("governance_check", {"dimension": "X1"})
        assert result["status"] == "ok"
        assert result["dimension"] == "X1"
    
    def test_call_status(self):
        mcp = GovernanceMCP()
        result = mcp.call_tool("governance_status")
        assert result["status"] == "ok"
        assert "health_score" in result
    
    def test_call_history(self):
        mcp = GovernanceMCP()
        result = mcp.call_tool("governance_history", {"days": 7})
        assert result["status"] == "ok"
        assert result["days"] == 7
    
    def test_call_unknown(self):
        mcp = GovernanceMCP()
        result = mcp.call_tool("unknown_tool")
        assert "error" in result
    
    def test_list_tools(self):
        mcp = GovernanceMCP()
        tools = mcp.list_tools()
        assert len(tools) == 3
        assert any(t["name"] == "governance_check" for t in tools)
