"""Tests for MCP Registry CLI commands — Phase 2: load/unload + pipeline."""

import argparse
import json
from unittest.mock import AsyncMock, patch

from agora.cli.commands_repo import cmd_repo

# ── Helpers ────────────────────────────────────────────────────────────


def _make_args(**kwargs) -> argparse.Namespace:
    """Create an argparse.Namespace with the given attributes."""
    defaults = {
        "repo_cmd": "list",
        "json": False,
        "query": "",
        "status": None,
        "name_or_id": "",
        "sources": None,
    }
    merged = {**defaults, **kwargs}
    return argparse.Namespace(**merged)


def _make_tool(tool_id: str, name: str = "", status: str = "discovered", **kwargs) -> dict:
    return {
        "id": tool_id,
        "name": name or tool_id,
        "status": status,
        "description": kwargs.get("description", "test tool"),
        "tool_type": kwargs.get("tool_type", "python"),
        "quality_score": kwargs.get("quality_score", 0.5),
        "stars": kwargs.get("stars", 0),
        **kwargs,
    }


# ── Tests: list ────────────────────────────────────────────────────────


class TestCmdRepoList:
    def test_list_empty(self, capsys):
        """List with empty catalog should print 'No tools'."""
        with patch("agora.cli.commands_repo.ToolCatalog") as MockCatalog:  # noqa: N806
            instance = MockCatalog.return_value
            instance.list_tools.return_value = []

            rc = cmd_repo(_make_args(repo_cmd="list"))
            assert rc == 0
            captured = capsys.readouterr()
            assert "No tools" in captured.out

    def test_list_with_tools(self, capsys):
        with patch("agora.cli.commands_repo.ToolCatalog") as MockCatalog:  # noqa: N806
            instance = MockCatalog.return_value
            instance.list_tools.return_value = [
                _make_tool("t1", name="Tool One", status="loaded", quality_score=0.85, stars=42),
                _make_tool("t2", name="Tool Two", status="idle", quality_score=0.50, stars=10),
            ]

            rc = cmd_repo(_make_args(repo_cmd="list"))
            assert rc == 0
            captured = capsys.readouterr()
            assert "Tool One" in captured.out
            assert "Tool Two" in captured.out
            assert "loaded" in captured.out
            assert "idle" in captured.out

    def test_list_filtered_by_status(self, capsys):
        with patch("agora.cli.commands_repo.ToolCatalog") as MockCatalog:  # noqa: N806
            instance = MockCatalog.return_value
            instance.list_tools.return_value = [
                _make_tool("t1", name="Loaded Tool", status="loaded"),
            ]

            rc = cmd_repo(_make_args(repo_cmd="list", status="loaded"))
            assert rc == 0
            instance.list_tools.assert_called_with(status="loaded")

    def test_list_json(self, capsys):
        with patch("agora.cli.commands_repo.ToolCatalog") as MockCatalog:  # noqa: N806
            instance = MockCatalog.return_value
            instance.list_tools.return_value = [
                _make_tool("t1", name="Tool One", quality_score=0.85),
            ]
            rc = cmd_repo(_make_args(repo_cmd="list", json=True))
            assert rc == 0
            captured = capsys.readouterr()
            output = json.loads(captured.out)
            assert len(output) == 1
            assert output[0]["id"] == "t1"


# ── Tests: search ──────────────────────────────────────────────────────


class TestCmdRepoSearch:
    def test_search_no_query(self, capsys):
        rc = cmd_repo(_make_args(repo_cmd="search"))
        assert rc == 1
        captured = capsys.readouterr()
        assert "requires a query" in captured.err

    def test_search_no_results(self, capsys):
        with patch("agora.cli.commands_repo.ToolCatalog") as MockCatalog:  # noqa: N806
            instance = MockCatalog.return_value
            instance.search_tools.return_value = []

            rc = cmd_repo(_make_args(repo_cmd="search", query="nothing"))
            assert rc == 0
            captured = capsys.readouterr()
            assert "No results" in captured.out

    def test_search_with_results(self, capsys):
        with patch("agora.cli.commands_repo.ToolCatalog") as MockCatalog:  # noqa: N806
            instance = MockCatalog.return_value
            instance.search_tools.return_value = [
                _make_tool("sqlite", name="sqlite", status="loaded", quality_score=0.9),
            ]

            rc = cmd_repo(_make_args(repo_cmd="search", query="sqlite"))
            assert rc == 0
            captured = capsys.readouterr()
            assert "sqlite" in captured.out

    def test_search_json(self, capsys):
        with patch("agora.cli.commands_repo.ToolCatalog") as MockCatalog:  # noqa: N806
            instance = MockCatalog.return_value
            instance.search_tools.return_value = [
                _make_tool("t1", name="t1", quality_score=0.9),
            ]

            rc = cmd_repo(_make_args(repo_cmd="search", query="t1", json=True))
            assert rc == 0
            captured = capsys.readouterr()
            output = json.loads(captured.out)
            assert output[0]["id"] == "t1"


# ── Tests: status ──────────────────────────────────────────────────────


class TestCmdRepoStatus:
    def test_status_empty(self, capsys):
        with patch("agora.cli.commands_repo.ToolCatalog") as MockCatalog:  # noqa: N806
            instance = MockCatalog.return_value
            instance.count_by_status.return_value = {}

            rc = cmd_repo(_make_args(repo_cmd="status"))
            assert rc == 0
            captured = capsys.readouterr()
            assert "Total tools:" in captured.out

    def test_status_with_counts(self, capsys):
        with patch("agora.cli.commands_repo.ToolCatalog") as MockCatalog:  # noqa: N806
            instance = MockCatalog.return_value
            instance.count_by_status.return_value = {
                "discovered": 5,
                "installed": 3,
                "loaded": 2,
            }

            rc = cmd_repo(_make_args(repo_cmd="status"))
            assert rc == 0
            captured = capsys.readouterr()
            assert "Total tools: 10" in captured.out
            assert "discovered: 5" in captured.out
            assert "loaded: 2" in captured.out
            assert "idle: 0" not in captured.out  # zero-count should not print

    def test_status_json(self, capsys):
        with patch("agora.cli.commands_repo.ToolCatalog") as MockCatalog:  # noqa: N806
            instance = MockCatalog.return_value
            instance.count_by_status.return_value = {"discovered": 5}

            rc = cmd_repo(_make_args(repo_cmd="status", json=True))
            assert rc == 0
            captured = capsys.readouterr()
            output = json.loads(captured.out)
            assert output["total"] == 5


# ── Tests: info ────────────────────────────────────────────────────────


class TestCmdRepoInfo:
    def test_info_found(self, capsys):
        with patch("agora.cli.commands_repo.ToolCatalog") as MockCatalog:  # noqa: N806
            instance = MockCatalog.return_value
            instance.get_tool.return_value = _make_tool("my-tool", name="my-tool", stars=100)

            rc = cmd_repo(_make_args(repo_cmd="info", name_or_id="my-tool"))
            assert rc == 0
            captured = capsys.readouterr()
            output = json.loads(captured.out)
            assert output["id"] == "my-tool"
            assert output["stars"] == 100

    def test_info_not_found(self, capsys):
        with patch("agora.cli.commands_repo.ToolCatalog") as MockCatalog:  # noqa: N806
            instance = MockCatalog.return_value
            instance.get_tool.return_value = None

            rc = cmd_repo(_make_args(repo_cmd="info", name_or_id="ghost"))
            assert rc == 1
            captured = capsys.readouterr()
            assert "not found" in captured.out


# ── Tests: discover ────────────────────────────────────────────────────


class TestCmdRepoDiscover:
    def test_discover_success(self, capsys):
        with (
            patch("agora.cli.commands_repo.ToolCatalog"),
            patch("agora.mcp_registry.orchestrator.search_all", new_callable=AsyncMock) as mock_search,
        ):
            mock_search.return_value = [
                _make_tool("t1", name="tool1", source="github", description="A test tool"),
            ]

            rc = cmd_repo(_make_args(repo_cmd="discover", query="mcp-server"))
            assert rc == 0
            captured = capsys.readouterr()
            assert "Discovered 1 tool(s)" in captured.out
            assert "tool1" in captured.out

    def test_discover_empty(self, capsys):
        with patch("agora.mcp_registry.orchestrator.search_all", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []

            rc = cmd_repo(_make_args(repo_cmd="discover", query="nothing"))
            assert rc == 0
            captured = capsys.readouterr()
            assert "Discovered 0 tool(s)" in captured.out

    def test_discover_json(self, capsys):
        with patch("agora.mcp_registry.orchestrator.search_all", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [
                {"id": "t1", "name": "tool1", "quality_score": 0.8, "source": "github"},
            ]

            rc = cmd_repo(_make_args(repo_cmd="discover", query="test", json=True))
            assert rc == 0
            captured = capsys.readouterr()
            # structlog may write to stdout; find and parse the JSON array
            lines = captured.out.strip().split("\n")
            json_start = next((i for i, l in enumerate(lines) if l.strip().startswith("[")), None)  # noqa: E741
            if json_start is not None:
                # Collect all lines from json_start to end
                out = "\n".join(lines[json_start:])
            else:
                out = captured.out
            output = json.loads(out)
            assert output[0]["name"] == "tool1"


# ── Tests: install ─────────────────────────────────────────────────────


class TestCmdRepoInstall:
    def test_install_success(self, capsys):
        with (
            patch("agora.cli.commands_repo.ToolCatalog"),
            patch("agora.cli.commands_repo.LifecycleManager"),
        ):
            orchestrator_mock = AsyncMock()

            with patch("agora.cli.commands_repo.Orchestrator") as MockOrch:  # noqa: N806
                MockOrch.return_value = orchestrator_mock
                orchestrator_mock.install_tool.return_value = (True, "Tool 'my-tool' marked as installed.")

                rc = cmd_repo(_make_args(repo_cmd="install", name_or_id="my-tool"))
                assert rc == 0
                captured = capsys.readouterr()
                assert "installed" in captured.out

    def test_install_failure(self, capsys):
        with patch("agora.cli.commands_repo.ToolCatalog"):
            with patch("agora.cli.commands_repo.LifecycleManager"):
                with patch("agora.cli.commands_repo.Orchestrator") as MockOrch:  # noqa: N806
                    orch_instance = MockOrch.return_value
                    orch_instance.install_tool = AsyncMock(return_value=(False, "Tool 'ghost' not found in catalog."))

                    rc = cmd_repo(_make_args(repo_cmd="install", name_or_id="ghost"))
                    assert rc == 1
                    captured = capsys.readouterr()
                    assert "not found" in captured.err


# ── Tests: load ────────────────────────────────────────────────────────


class TestCmdRepoLoad:
    def test_load_success(self, capsys):
        with (
            patch("agora.cli.commands_repo.ToolCatalog"),
            patch("agora.cli.commands_repo.LifecycleManager"),
            patch("agora.cli.commands_repo.Orchestrator") as MockOrch,  # noqa: N806
        ):
            orch_instance = MockOrch.return_value
            orch_instance.load_tool = AsyncMock(return_value=(True, "Tool 'my-tool' loaded."))

            rc = cmd_repo(_make_args(repo_cmd="load", name_or_id="my-tool"))
            assert rc == 0
            captured = capsys.readouterr()
            assert "loaded" in captured.out

    def test_load_failure(self, capsys):
        with (
            patch("agora.cli.commands_repo.ToolCatalog"),
            patch("agora.cli.commands_repo.LifecycleManager"),
            patch("agora.cli.commands_repo.Orchestrator") as MockOrch,  # noqa: N806
        ):
            orch_instance = MockOrch.return_value
            orch_instance.load_tool = AsyncMock(return_value=(False, "Failed to load tool 'broken'."))

            rc = cmd_repo(_make_args(repo_cmd="load", name_or_id="broken"))
            assert rc == 1
            captured = capsys.readouterr()
            assert "Failed" in captured.err


# ── Tests: unload ──────────────────────────────────────────────────────


class TestCmdRepoUnload:
    def test_unload_success(self, capsys):
        with (
            patch("agora.cli.commands_repo.ToolCatalog"),
            patch("agora.cli.commands_repo.LifecycleManager"),
            patch("agora.cli.commands_repo.Orchestrator") as MockOrch,  # noqa: N806
        ):
            orch_instance = MockOrch.return_value
            orch_instance.unload_tool = AsyncMock(return_value=(True, "Tool 'my-tool' unloaded."))

            rc = cmd_repo(_make_args(repo_cmd="unload", name_or_id="my-tool"))
            assert rc == 0
            captured = capsys.readouterr()
            assert "unloaded" in captured.out

    def test_unload_failure(self, capsys):
        with (
            patch("agora.cli.commands_repo.ToolCatalog"),
            patch("agora.cli.commands_repo.LifecycleManager"),
            patch("agora.cli.commands_repo.Orchestrator") as MockOrch,  # noqa: N806
        ):
            orch_instance = MockOrch.return_value
            orch_instance.unload_tool = AsyncMock(return_value=(False, "Failed to unload tool 'broken'."))

            rc = cmd_repo(_make_args(repo_cmd="unload", name_or_id="broken"))
            assert rc == 1
            captured = capsys.readouterr()
            assert "Failed" in captured.err


# ── Tests: load-all ────────────────────────────────────────────────────


class TestCmdRepoLoadAll:
    def test_load_all_zero(self, capsys):
        with (
            patch("agora.cli.commands_repo.ToolCatalog"),
            patch("agora.cli.commands_repo.LifecycleManager"),
            patch("agora.cli.commands_repo.Orchestrator") as MockOrch,  # noqa: N806
        ):
            orch_instance = MockOrch.return_value
            orch_instance.load_all_idle = AsyncMock(return_value=0)

            rc = cmd_repo(_make_args(repo_cmd="load-all"))
            assert rc == 0
            captured = capsys.readouterr()
            assert "Loaded 0 tool(s)" in captured.out

    def test_load_all_some(self, capsys):
        with (
            patch("agora.cli.commands_repo.ToolCatalog"),
            patch("agora.cli.commands_repo.LifecycleManager"),
            patch("agora.cli.commands_repo.Orchestrator") as MockOrch,  # noqa: N806
        ):
            orch_instance = MockOrch.return_value
            orch_instance.load_all_idle = AsyncMock(return_value=3)

            rc = cmd_repo(_make_args(repo_cmd="load-all"))
            assert rc == 0
            captured = capsys.readouterr()
            assert "Loaded 3 tool(s)" in captured.out


# ── Tests: unload-all ──────────────────────────────────────────────────


class TestCmdRepoUnloadAll:
    def test_unload_all_zero(self, capsys):
        with (
            patch("agora.cli.commands_repo.ToolCatalog"),
            patch("agora.cli.commands_repo.LifecycleManager"),
            patch("agora.cli.commands_repo.Orchestrator") as MockOrch,  # noqa: N806
        ):
            orch_instance = MockOrch.return_value
            orch_instance.unload_all_loaded = AsyncMock(return_value=0)

            rc = cmd_repo(_make_args(repo_cmd="unload-all"))
            assert rc == 0
            captured = capsys.readouterr()
            assert "Unloaded 0 tool(s)" in captured.out

    def test_unload_all_some(self, capsys):
        with (
            patch("agora.cli.commands_repo.ToolCatalog"),
            patch("agora.cli.commands_repo.LifecycleManager"),
            patch("agora.cli.commands_repo.Orchestrator") as MockOrch,  # noqa: N806
        ):
            orch_instance = MockOrch.return_value
            orch_instance.unload_all_loaded = AsyncMock(return_value=5)

            rc = cmd_repo(_make_args(repo_cmd="unload-all"))
            assert rc == 0
            captured = capsys.readouterr()
            assert "Unloaded 5 tool(s)" in captured.out


# ── Tests: pipeline ────────────────────────────────────────────────────


class TestCmdRepoPipeline:
    def test_pipeline_success(self, capsys):
        with (
            patch("agora.cli.commands_repo.ToolCatalog"),
            patch("agora.cli.commands_repo.LifecycleManager"),
            patch("agora.cli.commands_repo.Orchestrator") as MockOrch,  # noqa: N806
        ):
            orch_instance = MockOrch.return_value
            orch_instance.discover_install_load = AsyncMock(
                return_value={
                    "discovered": 3,
                    "installed": 3,
                    "loaded": 2,
                }
            )

            rc = cmd_repo(_make_args(repo_cmd="pipeline", query="mcp-server"))
            assert rc == 0
            captured = capsys.readouterr()
            assert "Discovered: 3" in captured.out
            assert "Installed: 3" in captured.out
            assert "Loaded: 2" in captured.out

    def test_pipeline_json(self, capsys):
        with (
            patch("agora.cli.commands_repo.ToolCatalog"),
            patch("agora.cli.commands_repo.LifecycleManager"),
            patch("agora.cli.commands_repo.Orchestrator") as MockOrch,  # noqa: N806
        ):
            orch_instance = MockOrch.return_value
            orch_instance.discover_install_load = AsyncMock(
                return_value={
                    "discovered": 1,
                    "installed": 1,
                    "loaded": 1,
                }
            )

            rc = cmd_repo(_make_args(repo_cmd="pipeline", query="test", json=True))
            assert rc == 0
            captured = capsys.readouterr()
            output = json.loads(captured.out)
            assert output["discovered"] == 1


# ── Tests: remove ──────────────────────────────────────────────────────


class TestCmdRepoRemove:
    def test_remove_success(self, capsys):
        with patch("agora.cli.commands_repo.ToolCatalog") as MockCatalog:  # noqa: N806
            instance = MockCatalog.return_value
            instance.remove_tool.return_value = True

            rc = cmd_repo(_make_args(repo_cmd="remove", name_or_id="old-tool"))
            assert rc == 0
            captured = capsys.readouterr()
            assert "removed" in captured.out

    def test_remove_not_found(self, capsys):
        with patch("agora.cli.commands_repo.ToolCatalog") as MockCatalog:  # noqa: N806
            instance = MockCatalog.return_value
            instance.remove_tool.return_value = False

            rc = cmd_repo(_make_args(repo_cmd="remove", name_or_id="ghost"))
            assert rc == 1
            captured = capsys.readouterr()
            assert "not found" in captured.err


# ── Tests: unknown command ─────────────────────────────────────────────


class TestCmdRepoUnknown:
    def test_unknown_command(self, capsys):
        rc = cmd_repo(_make_args(repo_cmd="unknown"))
        assert rc == 1
        captured = capsys.readouterr()
        assert "Unknown repo subcommand" in captured.out
