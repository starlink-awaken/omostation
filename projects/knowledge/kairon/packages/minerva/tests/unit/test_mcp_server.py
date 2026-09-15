"""Tests for Minerva MCP Server — tool registration and server startup."""

import pytest


class TestMCPServer:
    """Tests for MCP server tool registration."""

    def test_mcp_server_imports(self):
        """Test MCP server module imports without errors."""
        from minerva.mcp_server.server import mcp

        assert mcp is not None
        assert mcp.name == "Minerva Deep Research"

    @pytest.mark.asyncio
    async def test_mcp_server_has_all_tools(self):
        """Test all 6 Super Tools are registered."""
        from minerva.mcp_server.server import mcp

        tools = await mcp.list_tools()
        tool_names = {t.name for t in tools}
        expected = {
            "research_now",
            "research_schedule",
            "research_watch",
            "knowledge_search",
            "cross_domain_research",
            "knowledge_ingest",
            "minerva_bfs_search",
            "knowledge_closed_loop",
        }
        assert tool_names == expected

    @pytest.mark.asyncio
    async def test_research_now_tool_exists(self):
        """Test research_now tool is callable."""
        from minerva.mcp_server.server import mcp

        tools = await mcp.list_tools()
        research_tool = next(t for t in tools if t.name == "research_now")
        assert research_tool is not None
        params = research_tool.parameters
        assert "query" in params.get("properties", params)

    def test_cli_mcp_command_registered(self):
        """Test CLI has mcp command."""
        from minerva.cli import build_parser

        parser = build_parser()
        # MCP should be a valid subcommand
        actions = [a for a in parser._actions if hasattr(a, "choices")]
        subcommands = set()
        for a in actions:
            if hasattr(a, "choices") and a.choices:
                subcommands.update(a.choices.keys())  # type: ignore[reportAttributeAccessIssue]
        assert "mcp" in subcommands

    def test_cli_maintenance_cleanup_temp_action_registered(self):
        """Test CLI exposes cleanup-temp maintenance action."""
        from minerva.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["maintenance", "--action", "cleanup-temp"])

        assert args.command == "maintenance"
        assert args.action == "cleanup-temp"

    @pytest.mark.asyncio
    async def test_cross_domain_research_tool_exists(self):
        from minerva.mcp_server.server import mcp

        tools = await mcp.list_tools()
        tool_names = {t.name for t in tools}
        assert "cross_domain_research" in tool_names


class TestCrossDomainResearch:
    def test_build_cross_domain_report_preserves_requested_domains(self):
        from minerva.mcp_server.server import build_cross_domain_report

        report = build_cross_domain_report(
            "统一 LLM provider",
            [
                {
                    "title": "agentmesh gateway route",
                    "snippet": "agentmesh routes claude through litellm",
                    "domain": "agentmesh",
                    "path": "projects/agentmesh/config/gateway.yaml",
                },
                {
                    "title": "gbrain memory tree",
                    "snippet": "gbrain builds compressed memory clusters",
                    "domain": "gbrain",
                    "path": "projects/gbrain/src/core/memory-tree.ts",
                },
            ],
            ["agentmesh", "gbrain", "kairon"],
        )

        assert [brief["domain"] for brief in report["domain_briefs"]] == ["agentmesh", "gbrain", "kairon"]
        assert report["domain_briefs"][2]["status"] == "gap"

    @pytest.mark.asyncio
    async def test_cross_domain_research_returns_three_domain_briefs(self):
        from minerva.mcp_server import server

        class _StubKB:
            async def search(self, query, mode="hybrid", limit=8, source_id=None):
                return [
                    {
                        "title": "agentmesh gateway route",
                        "snippet": "agentmesh routes claude through litellm",
                        "domain": "agentmesh",
                        "path": "projects/agentmesh/config/gateway.yaml",
                    },
                    {
                        "title": "gbrain memory tree",
                        "snippet": "gbrain clusters memory into branches",
                        "domain": "gbrain",
                        "path": "projects/gbrain/src/core/memory-tree.ts",
                    },
                    {
                        "title": "kairon minerva research",
                        "snippet": "minerva synthesizes research evidence",
                        "domain": "kairon",
                        "path": "projects/kairon/packages/minerva/src/minerva/mcp_server/server.py",
                    },
                ]

        class _StubExecutor:
            kb = _StubKB()

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(server, "executor", _StubExecutor())
            result = await server.cross_domain_research(
                "统一 LLM provider",
                domains="agentmesh,gbrain,kairon",
                limit=6,
            )

        assert result["status"] == "ok"
        assert len(result["domain_briefs"]) == 3
        assert result["domain_briefs"][0]["domain"] == "agentmesh"
