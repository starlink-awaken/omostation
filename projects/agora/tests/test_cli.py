"""Tests for Agora CLI — parser structure and command routing."""

import sys

import pytest
from agora.cli import build_parser


class TestParserStructure:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.parser = build_parser()

    def test_all_top_level_commands(self):
        choices = set()
        for action in self.parser._actions:
            if hasattr(action, "choices") and action.choices is not None:
                choices.update(action.choices.keys())
        expected = {
            "register",
            "list",
            "discover",
            "instance",
            "tenant",
            "market",
            "search",
            "info",
            "stats",
            "health",
            "route",
            "routes",
            "mcp",
            "init",
            "completion",
            "config",
            "web",
            "pipeline",
            "pipelines",
            "pipeline-define",
            "event",
            "a2a",
            "transitions",
            "audit",
            "key",
            "agent-card",
            "proto",
            "sync",
            "start-pipeline",
            "run",
        }
        for cmd in expected:
            assert cmd in choices, f"Missing command: {cmd}"

    def test_register_has_protocol_arg(self):
        parsed = self.parser.parse_args(["register", "test"])
        assert parsed.protocol == "mcp"

    def test_register_with_protocol(self):
        parsed = self.parser.parse_args(
            [
                "register",
                "api",
                "--protocol",
                "rest",
                "--protocol-config",
                '{"method":"GET"}',
            ]
        )
        assert parsed.protocol == "rest"
        assert parsed.protocol_config == '{"method":"GET"}'

    def test_register_with_endpoint(self):
        parsed = self.parser.parse_args(
            [
                "register",
                "minerva",
                "--mcp",
                "http://192.0.2.1:8765/mcp",
                "--health",
                "http://192.0.2.1:8765/health",
                "--port",
                "8765",
            ]
        )
        assert parsed.name == "minerva"
        assert parsed.mcp == "http://192.0.2.1:8765/mcp"
        assert parsed.health == "http://192.0.2.1:8765/health"
        assert parsed.port == 8765

    def test_register_has_a2a_args(self):
        """register subcommand accepts A2A metadata arguments."""
        parsed = self.parser.parse_args(
            [
                "register",
                "a2a-svc",
                "--has-auth",
                "--has-push-notifications",
                "--has-state-transitions",
                "--provider-info",
                '{"organization":"MyOrg"}',
                "--documentation-url",
                "https://docs.example.com",
            ]
        )
        assert parsed.name == "a2a-svc"
        assert parsed.has_auth is True
        assert parsed.has_push_notifications is True
        assert parsed.has_state_transitions is True
        assert parsed.provider_info == '{"organization":"MyOrg"}'
        assert parsed.documentation_url == "https://docs.example.com"

    def test_a2a_list_command(self):
        """a2a list subcommand parses correctly."""
        parsed = self.parser.parse_args(["a2a", "list"])
        assert parsed.command == "a2a"
        assert parsed.a2a_cmd == "list"

    def test_a2a_list_with_filters(self):
        """a2a list subcommand accepts filter arguments."""
        parsed = self.parser.parse_args(
            [
                "a2a",
                "list",
                "--service",
                "minerva",
                "--status",
                "completed",
                "--since",
                "2026-01-01T00:00:00",
                "--limit",
                "10",
            ]
        )
        assert parsed.command == "a2a"
        assert parsed.a2a_cmd == "list"
        assert parsed.service == "minerva"
        assert parsed.status == "completed"
        assert parsed.since == "2026-01-01T00:00:00"
        assert parsed.limit == 10

    def test_agent_card_list_command(self):
        """agent-card list subcommand parses correctly."""
        parsed = self.parser.parse_args(["agent-card", "list"])
        assert parsed.command == "agent-card"
        assert parsed.agent_card_cmd == "list"

    def test_agent_card_get_command(self):
        """agent-card get subcommand parses correctly."""
        parsed = self.parser.parse_args(["agent-card", "get", "test-svc"])
        assert parsed.command == "agent-card"
        assert parsed.agent_card_cmd == "get"
        assert parsed.name == "test-svc"

    def test_list_command(self):
        parsed = self.parser.parse_args(["list"])
        assert parsed.command == "list"

    def test_health_command(self):
        parsed = self.parser.parse_args(["health"])
        assert parsed.command == "health"

    def test_health_watch_mode(self):
        parsed = self.parser.parse_args(["health", "--watch", "--interval", "10"])
        assert parsed.watch is True
        assert parsed.interval == 10

    def test_discover_command(self):
        parsed = self.parser.parse_args(["discover", "--register", "--json"])
        assert parsed.command == "discover"
        assert parsed.register is True
        assert parsed.json is True

    def test_pipeline_command(self):
        parsed = self.parser.parse_args(
            [
                "pipeline",
                "my-pipeline",
                "--goal",
                "test-goal",
                "--stream",
                "--parallel",
            ]
        )
        assert parsed.name == "my-pipeline"
        assert parsed.goal == "test-goal"
        assert parsed.stream is True
        assert parsed.parallel is True

    def test_route_command(self):
        parsed = self.parser.parse_args(["route", "minerva.research_now", "minerva"])
        assert parsed.tool == "minerva.research_now"
        assert parsed.service == "minerva"

    def test_market_list(self):
        parsed = self.parser.parse_args(["market", "list"])
        assert parsed.market_cmd == "list"

    def test_market_search(self):
        parsed = self.parser.parse_args(["market", "search", "知识图谱"])
        assert parsed.keyword == "知识图谱"

    def test_tenant_list(self):
        parsed = self.parser.parse_args(["tenant", "list"])
        assert parsed.tenant_cmd == "list"

    def test_event_publish(self):
        parsed = self.parser.parse_args(["event", "publish", "test:event", "--payload", '{"k":"v"}'])
        assert parsed.type == "test:event"

    def test_event_log(self):
        parsed = self.parser.parse_args(["event", "log", "--limit", "10"])
        assert parsed.limit == 10

    def test_mcp_command(self):
        parsed = self.parser.parse_args(["mcp"])
        assert parsed.command == "mcp"

    def test_web_command(self):
        parsed = self.parser.parse_args(["web"])
        assert parsed.command == "web"

    def test_completion_command(self):
        parsed = self.parser.parse_args(["completion"])
        assert parsed.command == "completion"


class TestCommandRouting:
    """Smoke test: each command handler doesn't crash on its happy path."""

    def test_register_handler_runs(self):
        sys.argv = ["agora", "register", "smoke-test", "--protocol", "rest"]
        try:
            # CLI main may call sys.exit(0) or print
            from agora.cli import main

            main()
        except SystemExit:
            pass  # expected for some exit paths
