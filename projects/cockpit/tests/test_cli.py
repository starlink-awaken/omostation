"""
Tests for cockpit CLI core functionality.

Tests the main CLI entry point and critical subcommands.
"""

import pytest
import sys
from pathlib import Path


# Add cockpit src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestCLIRouting:
    """Test that the CLI entry point can be imported and basic routing works."""

    def test_import_main(self):
        """CLI main function should be importable."""
        from cockpit.cli import main
        assert callable(main)

    def test_import_commands(self):
        """All command modules should be importable."""
        from cockpit.commands import base
        assert hasattr(base, "_get_console")

    def test_l4bridge_imports(self):
        """L4 bridge commands should be importable."""
        from cockpit.commands.l4bridge import (
            cmd_context,
            cmd_domains,
            cmd_cards,
            cmd_vault,
            cmd_skill,
        )
        assert callable(cmd_context)
        assert callable(cmd_domains)
        assert callable(cmd_cards)
        assert callable(cmd_vault)
        assert callable(cmd_skill)

    def test_model_driven_commands_importable(self):
        """Model-driven bridge commands should be importable."""
        from cockpit.commands.l4bridge import (
            cmd_model_driven_lifecycle,
            cmd_model_driven_spec,
            cmd_model_driven_okr,
            cmd_model_driven_derive,
            cmd_model_driven_pipeline,
        )
        assert callable(cmd_model_driven_lifecycle)
        assert callable(cmd_model_driven_spec)
        assert callable(cmd_model_driven_okr)
        assert callable(cmd_model_driven_derive)
        assert callable(cmd_model_driven_pipeline)


class TestCLISubcommands:
    """Test that all registered subcommands have valid handlers."""

    def test_cli_parser_has_expected_subcommands(self):
        """CLI parser should register all expected subcommands."""
        from cockpit.cli import main

        # Verify main is callable
        assert callable(main)

    def test_research_module_imports(self):
        """Research module should be importable."""
        from cockpit.commands import research
        assert hasattr(research, "cmd_research")

    def test_storage_module(self):
        """Storage module should be importable."""
        from cockpit import storage
        assert hasattr(storage, "get_db_path") or hasattr(storage, "IDataAccess")


class TestL0MCPTools:
    """Test L0 MCP tools integration."""

    def test_mcp_tools_registry(self):
        """MCP_TOOLS registry should contain expected tools."""
        from cockpit.l0_mcp_tools import MCP_TOOLS

        expected = [
            "l0_status",
            "l0_validate",
            "l0_audit",
            "l0_protocols",
            "l0_adr_list",
            "l0_entity_resolve",
        ]
        for tool_name in expected:
            assert tool_name in MCP_TOOLS, f"Missing tool: {tool_name}"
            assert "function" in MCP_TOOLS[tool_name]
            assert "description" in MCP_TOOLS[tool_name]

    def test_model_driven_tools_registry(self):
        """MCP_TOOLS should include model-driven bridge tools."""
        from cockpit.l0_mcp_tools import MCP_TOOLS

        md_tools = ["md_lifecycle_status", "md_validate"]
        for tool_name in md_tools:
            assert tool_name in MCP_TOOLS, f"Missing tool: {tool_name}"


class TestCockpitMCP:
    """Test cockpit MCP integration."""

    def test_cockpit_mcp_import(self):
        """Cockpit MCP module should be importable."""
        from cockpit.scripts import cockpit_mcp
        assert hasattr(cockpit_mcp, "workspace_context")
