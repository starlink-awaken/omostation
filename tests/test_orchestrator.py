"""Tests for MCP Registry Orchestrator — Phase 2: discover → install → load pipeline."""

from unittest.mock import AsyncMock, patch

import pytest
from agora.mcp_registry.orchestrator import Orchestrator

from tests.conftest import FakeToolCatalog

# ── Helpers ────────────────────────────────────────────────────────────


def _make_tool(tool_id: str, name: str = "", status: str = "discovered", **kwargs) -> dict:
    """Create a minimal tool dict for testing."""
    return {
        "id": tool_id,
        "name": name or tool_id,
        "status": status,
        "description": kwargs.get("description", "test tool"),
        "tool_type": kwargs.get("tool_type", "python"),
        "entry": kwargs.get("entry", ""),
        "install_path": kwargs.get("install_path", ""),
        "repo_url": kwargs.get("repo_url", ""),
        "metadata": kwargs.get("metadata", {}),
        "quality_score": kwargs.get("quality_score", 0.5),
        **kwargs,
    }


class FakeLifecycleManager:
    """In-memory fake of LifecycleManager for orchestrator tests."""

    def __init__(self, catalog):
        self._catalog = catalog
        self.load_calls: list[str] = []
        self.unload_calls: list[str] = []
        self.idle_watch_started = False
        self.idle_watch_stopped = False
        self.health_watch_started = False
        self.health_watch_stopped = False
        self.usage_records: list[str] = []
        self.load_failures: set[str] = set()
        self._closed = False

    async def load_tool(self, tool_id: str) -> bool:
        self.load_calls.append(tool_id)
        tool = self._catalog.get_tool(tool_id)
        if not tool:
            return False
        if tool_id in self.load_failures:
            return False
        self._catalog.update_status(tool_id, "loaded")
        return True

    async def unload_tool(self, tool_id: str) -> bool:
        self.unload_calls.append(tool_id)
        tool = self._catalog.get_tool(tool_id)
        if not tool:
            return False
        if tool.get("status") != "loaded":
            return True
        self._catalog.update_status(tool_id, "idle")
        return True

    async def load_by_status(self, status: str = "idle") -> int:
        count = 0
        for tool in self._catalog.list_tools(status=status):
            ok = await self.load_tool(tool["id"])
            if ok:
                count += 1
        return count

    async def unload_by_status(self, status: str = "loaded") -> int:
        count = 0
        for tool in self._catalog.list_tools(status=status):
            ok = await self.unload_tool(tool["id"])
            if ok:
                count += 1
        return count

    async def start_idle_watch(self):
        self.idle_watch_started = True

    async def stop_idle_watch(self):
        self.idle_watch_stopped = True

    async def start_health_watch(self):
        self.health_watch_started = True

    async def stop_health_watch(self):
        self.health_watch_stopped = True

    def get_status(self) -> dict:
        loaded = []
        idle = []
        for t in self._catalog.tools.values():
            s = t.get("status", "")
            if s == "loaded":
                loaded.append(t.get("id", ""))
            elif s == "idle":
                idle.append(t.get("id", ""))
        return {
            "loaded": loaded,
            "loaded_count": len(loaded),
            "idle": idle,
            "unloaded": [],
            "idle_watch_running": self.idle_watch_started,
            "health_watch_running": self.health_watch_started,
            "idle_timeout": 300.0,
            "check_interval": 60.0,
        }

    async def record_usage(self, tool_id: str):
        self.usage_records.append(tool_id)
        self._catalog.record_usage(tool_id)

    async def close(self):
        self._closed = True


# ── Test fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def catalog():
    return FakeToolCatalog()


@pytest.fixture
def lifecycle(catalog):
    return FakeLifecycleManager(catalog)


@pytest.fixture
def orchestrator(catalog, lifecycle):
    return Orchestrator(catalog=catalog, lifecycle=lifecycle)


# ── Tests: discover_and_save ─────────────────────────────────────────


class TestDiscoverAndSave:
    async def test_discover_and_save(self, orchestrator, catalog):
        """Mock search_all and verify tools are saved to catalog."""
        with patch("agora.mcp_registry.orchestrator.search_all", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [
                _make_tool("tool-a", name="tool-a"),
                _make_tool("tool-b", name="tool-b"),
            ]
            results = await orchestrator.discover_and_save(query="test")
            assert len(results) == 2
            assert "tool-a" in catalog.tools
            assert "tool-b" in catalog.tools
            mock_search.assert_called_once_with("test", None)

    async def test_discover_and_save_empty(self, orchestrator, catalog):
        with patch("agora.mcp_registry.orchestrator.search_all", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []
            results = await orchestrator.discover_and_save(query="nothing")
            assert len(results) == 0
            assert len(catalog.tools) == 0

    async def test_discover_and_save_with_sources(self, orchestrator):
        with patch("agora.mcp_registry.orchestrator.search_all", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [_make_tool("tool-x", name="tool-x")]
            results = await orchestrator.discover_and_save(query="test", sources=["github"])
            assert len(results) == 1
            mock_search.assert_called_once_with("test", ["github"])

    async def test_discover_error_handling(self, orchestrator, catalog):
        """If search_all raises, the exception should propagate."""
        with patch("agora.mcp_registry.orchestrator.search_all", new_callable=AsyncMock) as mock_search:
            mock_search.side_effect = RuntimeError("API failure")
            with pytest.raises(RuntimeError):
                await orchestrator.discover_and_save(query="test")

    async def test_discover_quality_score_added(self, orchestrator):
        """Each discovered tool should get a quality_score field."""
        with patch("agora.mcp_registry.orchestrator.search_all", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [{"id": "t1", "name": "tool1", "stars": 100, "description": "desc"}]
            results = await orchestrator.discover_and_save(query="test")
            assert len(results) == 1
            assert "quality_score" in results[0]


# ── Tests: discover_install_load ──────────────────────────────────────


class TestDiscoverInstallLoad:
    async def test_full_pipeline(self, orchestrator, catalog):
        """Full discover → install → load pipeline."""
        with patch("agora.mcp_registry.orchestrator.search_all", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [
                _make_tool("t1", name="tool1", description="desc"),
            ]
            result = await orchestrator.discover_install_load(query="test", auto_load=True)
            assert result["discovered"] == 1
            assert result["installed"] == 1
            assert result["loaded"] == 1
            assert catalog.tools["t1"]["status"] == "loaded"

    async def test_pipeline_no_auto_load(self, orchestrator, catalog):
        """Without auto_load, tools should be installed but not loaded."""
        with patch("agora.mcp_registry.orchestrator.search_all", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [
                _make_tool("t1", name="tool1"),
            ]
            result = await orchestrator.discover_install_load(query="test", auto_load=False)
            assert result["discovered"] == 1
            assert result["installed"] == 1
            assert result["loaded"] == 0
            assert catalog.tools["t1"]["status"] == "installed"

    async def test_pipeline_no_lifecycle(self, catalog):
        """Without LifecycleManager, load should be skipped."""
        orch = Orchestrator(catalog=catalog)
        with patch("agora.mcp_registry.orchestrator.search_all", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [_make_tool("t1", name="tool1")]
            result = await orch.discover_install_load(query="test", auto_load=True)
            assert result["discovered"] == 1
            assert result["installed"] == 1
            assert result["loaded"] == 0  # no lifecycle → can't load

    async def test_pipeline_empty_discovery(self, orchestrator):
        """Empty discovery should return zeros."""
        with patch("agora.mcp_registry.orchestrator.search_all", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []
            result = await orchestrator.discover_install_load(query="test")
            assert result["discovered"] == 0
            assert result["installed"] == 0
            assert result["loaded"] == 0

    async def test_pipeline_returns_tool_names(self, orchestrator):
        """discover_install_load should include tool_names in result."""
        with patch("agora.mcp_registry.orchestrator.search_all", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [
                _make_tool("t1", name="tool1"),
                _make_tool("t2", name="tool2"),
            ]
            result = await orchestrator.discover_install_load(query="test", auto_load=True)
            assert "tool_names" in result
            assert "tool1" in result["tool_names"]
            assert "tool2" in result["tool_names"]
            assert len(result["tool_names"]) == 2


# ── Tests: install_tool ────────────────────────────────────────────────


class TestInstallTool:
    async def test_install_success(self, catalog, orchestrator):
        catalog.tools["my-tool"] = _make_tool("my-tool", status="discovered")
        ok, msg = await orchestrator.install_tool("my-tool")
        assert ok is True
        assert "installed" in msg
        assert catalog.tools["my-tool"]["status"] == "installed"

    async def test_install_not_found(self, orchestrator):
        ok, msg = await orchestrator.install_tool("ghost")
        assert ok is False
        assert "not found" in msg

    async def test_install_already_installed(self, catalog, orchestrator):
        catalog.tools["existing"] = _make_tool("existing", status="installed")
        ok, msg = await orchestrator.install_tool("existing")
        assert ok is True
        assert "already" in msg.lower()

    async def test_install_already_loaded(self, catalog, orchestrator):
        catalog.tools["loaded"] = _make_tool("loaded", status="loaded")
        ok, msg = await orchestrator.install_tool("loaded")
        assert ok is True
        assert "already" in msg.lower()


# ── Tests: ensure_tool_available ───────────────────────────────────────


class TestEnsureToolAvailable:
    async def test_ensure_already_loaded(self, catalog, orchestrator, lifecycle):
        catalog.tools["ready"] = _make_tool("ready", status="loaded")
        ok, msg = await orchestrator.ensure_tool_available("ready")
        assert ok is True
        assert "loaded and ready" in msg
        assert "ready" not in lifecycle.load_calls  # no load needed

    async def test_ensure_load_idle(self, catalog, orchestrator, lifecycle):
        catalog.tools["idle-tool"] = _make_tool("idle-tool", status="idle")
        ok, msg = await orchestrator.ensure_tool_available("idle-tool")
        assert ok is True
        assert "loaded" in msg
        assert "idle-tool" in lifecycle.load_calls

    async def test_ensure_load_installed(self, catalog, orchestrator, lifecycle):
        catalog.tools["inst-tool"] = _make_tool("inst-tool", status="installed")
        ok, msg = await orchestrator.ensure_tool_available("inst-tool")
        assert ok is True
        assert "loaded" in msg
        assert "inst-tool" in lifecycle.load_calls

    async def test_ensure_not_found(self, orchestrator):
        ok, msg = await orchestrator.ensure_tool_available("ghost")
        assert ok is False
        assert "not found" in msg

    async def test_ensure_discovered_no_load(self, catalog, orchestrator):
        """Discovered tools should not be loaded automatically."""
        catalog.tools["new"] = _make_tool("new", status="discovered")
        ok, msg = await orchestrator.ensure_tool_available("new")
        assert ok is False
        assert "status" in msg or "discovered" in msg

    async def test_ensure_no_lifecycle(self, catalog):
        """Without lifecycle, ensure should fail for non-loaded tools."""
        orch = Orchestrator(catalog=catalog)
        catalog.tools["idle"] = _make_tool("idle", status="idle")
        ok, msg = await orch.ensure_tool_available("idle")
        assert ok is False

    async def test_ensure_load_failure(self, catalog, lifecycle, orchestrator):
        """When lifecycle load fails, ensure should return False."""
        catalog.tools["failing"] = _make_tool("failing", status="idle")
        lifecycle.load_failures.add("failing")
        ok, msg = await orchestrator.ensure_tool_available("failing")
        assert ok is False
        assert "fail" in msg.lower()


# ── Tests: load_tool / unload_tool via orchestrator ──────────────────


class TestOrchestratorLoadUnload:
    async def test_load_tool_success(self, catalog, orchestrator, lifecycle):
        catalog.tools["t"] = _make_tool("t", status="idle")
        ok, msg = await orchestrator.load_tool("t")
        assert ok is True
        assert "loaded" in msg.lower()
        assert "t" in lifecycle.load_calls

    async def test_load_tool_no_lifecycle(self, catalog):
        orch = Orchestrator(catalog=catalog)
        catalog.tools["t"] = _make_tool("t", status="idle")
        ok, msg = await orch.load_tool("t")
        assert ok is False
        assert "not configured" in msg

    async def test_load_tool_lifecycle_failure(self, catalog, lifecycle, orchestrator):
        catalog.tools["f"] = _make_tool("f", status="idle")
        lifecycle.load_failures.add("f")
        ok, msg = await orchestrator.load_tool("f")
        assert ok is False
        assert "fail" in msg.lower()

    async def test_unload_tool_success(self, catalog, orchestrator, lifecycle):
        catalog.tools["t"] = _make_tool("t", status="loaded")
        ok, msg = await orchestrator.unload_tool("t")
        assert ok is True
        assert "unloaded" in msg.lower()
        assert "t" in lifecycle.unload_calls

    async def test_unload_tool_no_lifecycle(self, catalog):
        orch = Orchestrator(catalog=catalog)
        catalog.tools["t"] = _make_tool("t", status="loaded")
        ok, msg = await orch.unload_tool("t")
        assert ok is False
        assert "not configured" in msg


# ── Phase 2 Tests: reload_tool ────────────────────────────────────────


class TestReloadTool:
    async def test_reload_tool(self, catalog, orchestrator, lifecycle):
        catalog.tools["t"] = _make_tool("t", status="loaded")
        ok, msg = await orchestrator.reload_tool("t")
        assert ok is True
        assert "loaded" in msg.lower()
        assert "t" in lifecycle.unload_calls
        assert "t" in lifecycle.load_calls

    async def test_reload_unloaded_tool(self, catalog, orchestrator, lifecycle):
        """Reload should work for unloaded (idle) tools."""
        catalog.tools["t"] = _make_tool("t", status="idle")
        ok, msg = await orchestrator.reload_tool("t")
        assert ok is True
        assert "loaded" in msg.lower()
        # unload is a no-op for idle, then load succeeds
        assert "t" in lifecycle.unload_calls
        assert "t" in lifecycle.load_calls

    async def test_reload_with_proxy_reconnect(self, catalog, orchestrator, lifecycle):
        """Reload should force to call unload then load even if currently loaded."""
        catalog.tools["t"] = _make_tool("t", status="loaded")
        ok, msg = await orchestrator.reload_tool("t")
        assert ok is True
        assert "reloaded" in msg.lower()
        assert "t" in lifecycle.unload_calls
        assert "t" in lifecycle.load_calls

    async def test_reload_nonexistent_tool(self, catalog, orchestrator, lifecycle):
        """Reload of nonexistent tool should fail."""
        ok, msg = await orchestrator.reload_tool("ghost")
        assert ok is False

    async def test_reload_no_lifecycle_returns_false(self, catalog):
        """Reload without lifecycle should fail."""
        orch = Orchestrator(catalog=catalog)
        catalog.tools["t"] = _make_tool("t", status="loaded")
        ok, msg = await orch.reload_tool("t")
        assert ok is False
        assert "not configured" in msg


# ── Tests: batch operations ────────────────────────────────────────────


class TestOrchestratorBatch:
    async def test_load_all_idle(self, catalog, lifecycle, orchestrator):
        catalog.tools["a"] = _make_tool("a", status="idle")
        catalog.tools["b"] = _make_tool("b", status="idle")
        catalog.tools["c"] = _make_tool("c", status="loaded")  # not idle

        count = await orchestrator.load_all_idle()
        assert count == 2
        assert "a" in lifecycle.load_calls
        assert "b" in lifecycle.load_calls

    async def test_load_all_idle_no_lifecycle(self, catalog):
        orch = Orchestrator(catalog=catalog)
        count = await orch.load_all_idle()
        assert count == 0

    async def test_unload_all_loaded(self, catalog, lifecycle, orchestrator):
        catalog.tools["x"] = _make_tool("x", status="loaded")
        catalog.tools["y"] = _make_tool("y", status="loaded")
        catalog.tools["z"] = _make_tool("z", status="idle")  # not loaded

        count = await orchestrator.unload_all_loaded()
        assert count == 2
        assert "x" in lifecycle.unload_calls
        assert "y" in lifecycle.unload_calls

    async def test_unload_all_no_lifecycle(self, catalog):
        orch = Orchestrator(catalog=catalog)
        count = await orch.unload_all_loaded()
        assert count == 0

    async def test_load_all_empty(self, orchestrator):
        count = await orchestrator.load_all_idle()
        assert count == 0

    async def test_unload_all_empty(self, orchestrator):
        count = await orchestrator.unload_all_loaded()
        assert count == 0


# ── Tests: lifecycle control ──────────────────────────────────────────


class TestOrchestratorLifecycleControl:
    async def test_start_idle_watch(self, orchestrator, lifecycle):
        assert lifecycle.idle_watch_started is False
        await orchestrator.start_idle_watch()
        assert lifecycle.idle_watch_started is True

    async def test_stop_idle_watch(self, orchestrator, lifecycle):
        await orchestrator.stop_idle_watch()
        assert lifecycle.idle_watch_stopped is True

    async def test_start_watch_no_lifecycle(self, catalog):
        orch = Orchestrator(catalog=catalog)
        await orch.start_idle_watch()  # should not raise

    async def test_stop_watch_no_lifecycle(self, catalog):
        orch = Orchestrator(catalog=catalog)
        await orch.stop_idle_watch()  # should not raise

    # ── Phase 2: health watch pass-through ──

    async def test_start_health_watch(self, orchestrator, lifecycle):
        assert lifecycle.health_watch_started is False
        await orchestrator.start_health_watch()
        assert lifecycle.health_watch_started is True

    async def test_stop_health_watch(self, orchestrator, lifecycle):
        await orchestrator.stop_health_watch()
        assert lifecycle.health_watch_stopped is True

    async def test_start_health_watch_no_lifecycle(self, catalog):
        orch = Orchestrator(catalog=catalog)
        await orch.start_health_watch()  # should not raise

    async def test_stop_health_watch_no_lifecycle(self, catalog):
        orch = Orchestrator(catalog=catalog)
        await orch.stop_health_watch()  # should not raise


# ── Phase 2 Tests: get_status ─────────────────────────────────────────


class TestOrchestratorGetStatus:
    async def test_get_status_with_lifecycle(self, catalog, orchestrator, lifecycle):
        catalog.tools["t1"] = _make_tool("t1", status="loaded")
        catalog.tools["t2"] = _make_tool("t2", status="idle")
        catalog.tools["t3"] = _make_tool("t3", status="discovered")

        status = orchestrator.get_status()

        assert "lifecycle" in status
        assert "catalog" in status
        assert status["catalog"]["total"] == 3
        assert status["catalog"]["by_status"].get("loaded") == 1
        assert status["catalog"]["by_status"].get("idle") == 1
        assert status["catalog"]["by_status"].get("discovered") == 1

    async def test_get_status_no_lifecycle(self, catalog):
        orch = Orchestrator(catalog=catalog)
        status = orch.get_status()
        assert "lifecycle" not in status
        assert "catalog" in status


# ── Tests: record_usage ────────────────────────────────────────────────


class TestOrchestratorRecordUsage:
    async def test_record_usage_with_lifecycle(self, catalog, lifecycle, orchestrator):
        catalog.tools["t"] = _make_tool("t", status="loaded")
        await orchestrator.record_usage("t")
        assert "t" in lifecycle.usage_records
        assert "t" in catalog.usage_records

    async def test_record_usage_no_lifecycle(self, catalog):
        orch = Orchestrator(catalog=catalog)
        catalog.tools["t"] = _make_tool("t", status="loaded")
        await orch.record_usage("t")
        assert "t" in catalog.usage_records


# ── Tests: close ────────────────────────────────────────────────────────


class TestOrchestratorClose:
    async def test_close_with_lifecycle(self, catalog, orchestrator, lifecycle):
        """close() should close lifecycle and catalog."""
        await orchestrator.close()
        assert lifecycle._closed is True

    async def test_close_no_lifecycle(self, catalog):
        """close() should work without lifecycle."""
        orch = Orchestrator(catalog=catalog)
        await orch.close()  # should not raise

    async def test_close_none_catalog(self):
        """Close should handle None catalog gracefully."""
        orch = Orchestrator(catalog=None)  # type: ignore[arg-type]
        await orch.close()  # should not raise

    async def test_close_with_active_health_watch(self, catalog, lifecycle):
        """Close should work when health watch is active."""
        orchestrator = Orchestrator(catalog=catalog, lifecycle=lifecycle)
        await orchestrator.start_health_watch()
        catalog.tools["t1"] = _make_tool("t1", status="loaded")
        await orchestrator.close()
        assert lifecycle._closed is True
