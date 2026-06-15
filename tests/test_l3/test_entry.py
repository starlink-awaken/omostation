"""L3 入口层测试"""

from ecos.l3.entry import GovernanceCLI, GovernanceMCP


class TestGovernanceCLI:
    """治理 CLI 测试"""

    def test_run_check(self):
        cli = GovernanceCLI()
        result = cli.run(["check"])
        assert result == 0
        output = cli.get_output()
        assert any("检查完成" in line for line in output)

    def test_run_check_dimension(self):
        cli = GovernanceCLI()
        result = cli.run(["check", "--dimension", "X1"])
        assert result == 0
        output = cli.get_output()
        assert any("X1" in line for line in output)

    def test_run_status(self):
        cli = GovernanceCLI()
        result = cli.run(["status"])
        assert result == 0

    def test_run_status_verbose(self):
        cli = GovernanceCLI()
        result = cli.run(["status", "--verbose"])
        assert result == 0
        output = cli.get_output()
        assert any("详细模式" in line for line in output)

    def test_run_unknown(self):
        cli = GovernanceCLI()
        result = cli.run(["unknown"])
        assert result == 1

    def test_print_help(self):
        cli = GovernanceCLI()
        cli._print_help()
        output = cli.get_output()
        assert len(output) > 0

    def test_cluster_list(self):
        cli = GovernanceCLI()
        result = cli.run(["cluster", "list"])
        assert result == 0
        output = cli.get_output()
        assert any("集群节点" in line for line in output)

    def test_cluster_health(self):
        cli = GovernanceCLI()
        result = cli.run(["cluster", "health"])
        assert result == 0

    def test_swarm_status(self):
        cli = GovernanceCLI()
        result = cli.run(["swarm", "status"])
        assert result == 0

    def test_swarm_detect(self):
        cli = GovernanceCLI()
        result = cli.run(["swarm", "detect"])
        assert result == 0
        output = cli.get_output()
        assert any("涌现检测" in line for line in output)

    def test_knowledge_stats(self):
        cli = GovernanceCLI()
        result = cli.run(["knowledge", "stats"])
        assert result == 0

    def test_help_command(self):
        cli = GovernanceCLI()
        result = cli.run(["help", "check"])
        assert result == 0
        output = cli.get_output()
        assert any("check" in line for line in output)


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
        assert "available" in result

    def test_list_tools(self):
        mcp = GovernanceMCP()
        tools = mcp.list_tools()
        assert len(tools) == 14
        assert any(t["name"] == "governance_check" for t in tools)
        assert any(t["name"] == "swarm_status" for t in tools)
        assert any(t["name"] == "knowledge_query" for t in tools)

    def test_cluster_tools(self):
        mcp = GovernanceMCP()
        result = mcp.call_tool("cluster_list")
        assert result["status"] == "ok"
        assert "nodes" in result

    def test_swarm_tools(self):
        mcp = GovernanceMCP()
        result = mcp.call_tool("swarm_status")
        assert result["status"] == "ok"
        assert "agent_count" in result

    def test_knowledge_tools(self):
        mcp = GovernanceMCP()
        result = mcp.call_tool("knowledge_stats")
        assert result["status"] == "ok"
        assert "node_count" in result

    def test_task_tools(self):
        mcp = GovernanceMCP()
        result = mcp.call_tool("task_submit", {"task_id": "t1", "name": "test"})
        assert result["status"] == "ok"

    def test_role_tools(self):
        mcp = GovernanceMCP()
        result = mcp.call_tool("role_switch", {"agent_id": "a1", "new_role": "worker"})
        assert result["status"] == "ok"

    def test_tool_count(self):
        mcp = GovernanceMCP()
        assert mcp.get_tool_count() == 14
