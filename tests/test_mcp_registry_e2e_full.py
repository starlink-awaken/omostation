"""Comprehensive end-to-end tests for the agora MCP registry system.

Covers the full pipeline: registry discovery → quality scoring → catalog
storage → embedding → routing → lifecycle management → orchestrator.

These tests use local registry.json, in-memory SQLite databases, and mock
proxy objects, so they do NOT require network access or external dependencies.
"""

from __future__ import annotations

from datetime import UTC
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from agora.mcp_registry.embeddings import EmbeddingStore
from agora.mcp_registry.evaluator import QualityScorer
from agora.mcp_registry.lifecycle import LifecycleManager
from agora.mcp_registry.orchestrator import Orchestrator
from agora.mcp_registry.repository import ToolCatalog
from agora.mcp_registry.router import SmartRouter
from agora.mcp_registry.sources import search_all, search_registry

# ══════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def registry_path() -> str:
    """Absolute path to the bundled registry.json."""
    module_dir = Path(__file__).resolve().parent.parent
    return str(module_dir / "src" / "agora" / "mcp_registry" / "data" / "registry.json")


@pytest.fixture
def catalog() -> ToolCatalog:
    c = ToolCatalog(db_path=":memory:")
    yield c
    c.close()


@pytest.fixture
def catalog_populated(registry_path) -> ToolCatalog:
    """Catalog pre-populated from local registry."""
    import asyncio

    c = ToolCatalog(db_path=":memory:")
    results = asyncio.run(search_registry(f"file://{registry_path}"))
    for svc in results:
        c.add_tool(svc)
    yield c
    c.close()


@pytest.fixture
def embeddings() -> EmbeddingStore:
    e = EmbeddingStore(db_path=":memory:")
    yield e
    e.close()


@pytest.fixture
def mock_proxy_manager():
    """Mock ProxyManager that records operations for verification."""
    pm = MagicMock()
    pm.add_service = AsyncMock(return_value="ok")
    pm.remove_service = AsyncMock(return_value="ok")
    pm.set_usage_callback = MagicMock()
    pm.registry = MagicMock()
    pm.registry._clients = {}
    return pm


@pytest.fixture
def lifecycle(catalog, mock_proxy_manager) -> LifecycleManager:
    lm = LifecycleManager(
        catalog=catalog,
        proxy_manager=mock_proxy_manager,
        idle_timeout=3600.0,
        check_interval=600.0,
        max_load_retries=1,
    )
    yield lm


@pytest.fixture
def orchestrator(catalog, lifecycle) -> Orchestrator:
    return Orchestrator(catalog=catalog, lifecycle=lifecycle)


@pytest.fixture
def orchestrator_no_lifecycle(catalog) -> Orchestrator:
    return Orchestrator(catalog=catalog, lifecycle=None)


# ══════════════════════════════════════════════════════════════════════
# Helper: get a known service dict for testing
# ══════════════════════════════════════════════════════════════════════

_KNOWN_SERVICE = {
    "id": "test-tool",
    "name": "test-tool",
    "description": "A test MCP tool for integration testing",
    "repo_url": "https://github.com/example/test-tool",
    "tool_type": "python",
    "stars": 100,
    "version": "1.2.3",
    "tags": ["test", "integration", "mcp"],
    "source": "registry",
    "metadata": {
        "verified": True,
        "updated_at": "2026-06-01T00:00:00Z",
        "language": "Python",
    },
}


# ══════════════════════════════════════════════════════════════════════
# Test 1: Orchestrator Pipeline (Phase 1 — discover + save)
# ══════════════════════════════════════════════════════════════════════


class TestOrchestratorDiscoverAndSave:
    """Orchestrator.discover_and_save: discovery → evaluation → catalog storage."""

    @pytest.mark.asyncio
    async def test_discover_and_save_from_local_registry(self, registry_path, orchestrator_no_lifecycle, monkeypatch):
        """Discover from local registry, save to catalog, verify counts."""
        monkeypatch.setattr(
            "agora.mcp_registry.orchestrator.search_all",
            lambda query="", sources=None: search_registry(f"file://{registry_path}"),
        )

        saved = await orchestrator_no_lifecycle.discover_and_save(query="test")
        assert len(saved) >= 30, f"Expected >=30 saved, got {len(saved)}"

        cat_tools = orchestrator_no_lifecycle._catalog.list_tools()
        assert len(cat_tools) == len(saved)

    @pytest.mark.asyncio
    async def test_discover_and_save_adds_quality_scores(self, registry_path, orchestrator_no_lifecycle, monkeypatch):
        """Each saved tool should have a quality_score."""
        monkeypatch.setattr(
            "agora.mcp_registry.orchestrator.search_all",
            lambda query="", sources=None: search_registry(f"file://{registry_path}"),
        )

        saved = await orchestrator_no_lifecycle.discover_and_save(query="test")
        for svc in saved:
            assert "quality_score" in svc, f"Missing quality_score in {svc.get('name')}"
            assert 0.0 <= svc["quality_score"] <= 1.0

    @pytest.mark.asyncio
    async def test_discover_and_save_idempotent(self, registry_path, orchestrator_no_lifecycle, monkeypatch):
        """Running discover_and_save twice should not create duplicates."""
        monkeypatch.setattr(
            "agora.mcp_registry.orchestrator.search_all",
            lambda query="", sources=None: search_registry(f"file://{registry_path}"),
        )

        await orchestrator_no_lifecycle.discover_and_save(query="test")
        first_count = len(orchestrator_no_lifecycle._catalog.list_tools())

        await orchestrator_no_lifecycle.discover_and_save(query="test")
        second_count = len(orchestrator_no_lifecycle._catalog.list_tools())

        assert first_count == second_count, "discover_and_save should be idempotent"

    @pytest.mark.asyncio
    async def test_discover_and_save_empty_sources(self, orchestrator_no_lifecycle, monkeypatch):
        """With empty sources, discover_and_save returns empty list."""

        async def _empty_search(query="", sources=None):
            return []

        monkeypatch.setattr(
            "agora.mcp_registry.orchestrator.search_all",
            _empty_search,
        )

        saved = await orchestrator_no_lifecycle.discover_and_save(query="nonexistent")
        assert saved == []

    @pytest.mark.asyncio
    async def test_status_after_discover(self, registry_path, orchestrator_no_lifecycle, monkeypatch):
        """After discover_and_save, tools should have status='discovered'."""
        monkeypatch.setattr(
            "agora.mcp_registry.orchestrator.search_all",
            lambda query="", sources=None: search_registry(f"file://{registry_path}"),
        )

        await orchestrator_no_lifecycle.discover_and_save(query="test")
        tools = orchestrator_no_lifecycle._catalog.list_tools()
        for t in tools:
            assert t.get("status") == "discovered", f"Expected 'discovered', got '{t.get('status')}' for {t['name']}"


# ══════════════════════════════════════════════════════════════════════
# Test 2: Orchestrator Pipeline (Phase 2 — discover → install → load)
# ══════════════════════════════════════════════════════════════════════


class TestOrchestratorDiscoverInstallLoad:
    """Full orchestrator pipeline: discover → install → load."""

    @pytest.mark.asyncio
    async def test_discover_install_load_basic(self, registry_path, orchestrator, monkeypatch):
        """Full pipeline returns correct counts."""
        # Patch search_all to use local registry
        monkeypatch.setattr(
            "agora.mcp_registry.orchestrator.search_all",
            lambda query="", sources=None: search_registry(f"file://{registry_path}"),
        )

        result = await orchestrator.discover_install_load(query="test", auto_load=True)

        assert result["discovered"] >= 30
        assert result["installed"] >= 30
        # loaded count depends on mock proxy — should succeed
        assert result["loaded"] >= 30
        assert len(result["tool_names"]) >= 30

    @pytest.mark.asyncio
    async def test_discover_install_load_no_auto_load(self, registry_path, orchestrator, monkeypatch):
        """With auto_load=False, tools are installed but not loaded."""
        monkeypatch.setattr(
            "agora.mcp_registry.orchestrator.search_all",
            lambda query="", sources=None: search_registry(f"file://{registry_path}"),
        )

        result = await orchestrator.discover_install_load(query="test", auto_load=False)

        assert result["installed"] > 0
        assert result["loaded"] == 0, "With auto_load=False, loaded should be 0"

        # Tools should be in 'installed' status
        tools = orchestrator._catalog.list_tools()
        for t in tools:
            assert t.get("status") == "installed", f"Expected 'installed', got '{t.get('status')}' for {t['name']}"

    @pytest.mark.asyncio
    async def test_discover_install_load_no_lifecycle(self, registry_path, orchestrator_no_lifecycle, monkeypatch):
        """Without lifecycle, auto_load has no effect but pipeline completes."""
        monkeypatch.setattr(
            "agora.mcp_registry.orchestrator.search_all",
            lambda query="", sources=None: search_registry(f"file://{registry_path}"),
        )

        result = await orchestrator_no_lifecycle.discover_install_load(query="test", auto_load=True)

        assert result["installed"] > 0
        assert result["loaded"] == 0, "Without lifecycle, loaded should be 0"
        assert result["discovered"] > 0

    @pytest.mark.asyncio
    async def test_discover_install_load_tool_names(self, registry_path, orchestrator, monkeypatch):
        """tool_names list should contain expected tools."""
        monkeypatch.setattr(
            "agora.mcp_registry.orchestrator.search_all",
            lambda query="", sources=None: search_registry(f"file://{registry_path}"),
        )

        result = await orchestrator.discover_install_load(query="test", auto_load=True)
        names = result["tool_names"]

        assert "kronos" in names, "Expected kronos in tool_names"
        assert "codeanalyze" in names, "Expected codeanalyze in tool_names"
        assert "docker-mcp" in names, "Expected docker-mcp in tool_names"

    @pytest.mark.asyncio
    async def test_discover_install_load_reports_status(self, registry_path, orchestrator, monkeypatch):
        """get_status after pipeline reflects correct state."""
        monkeypatch.setattr(
            "agora.mcp_registry.orchestrator.search_all",
            lambda query="", sources=None: search_registry(f"file://{registry_path}"),
        )

        await orchestrator.discover_install_load(query="test", auto_load=True)
        status = orchestrator.get_status()

        assert "catalog" in status
        assert status["catalog"]["total"] >= 30
        assert "loaded" in status["catalog"]["by_status"]
        assert status["catalog"]["by_status"]["loaded"] >= 30
        assert "lifecycle" in status


# ══════════════════════════════════════════════════════════════════════
# Test 3: Orchestrator — Install / Load / Unload / Reload
# ══════════════════════════════════════════════════════════════════════


class TestOrchestratorToolLifecycle:
    """Orchestrator-level install, load, unload, reload operations."""

    @pytest.mark.asyncio
    async def test_install_tool(self, registry_path, orchestrator_no_lifecycle, monkeypatch):
        """Install a discovered tool transitions it to 'installed' status."""
        monkeypatch.setattr(
            "agora.mcp_registry.orchestrator.search_all",
            lambda query="", sources=None: search_registry(f"file://{registry_path}"),
        )

        await orchestrator_no_lifecycle.discover_and_save(query="test")
        success, msg = await orchestrator_no_lifecycle.install_tool("kronos")

        assert success, f"Install failed: {msg}"
        tool = orchestrator_no_lifecycle._catalog.get_tool("kronos")
        assert tool["status"] == "installed"

    @pytest.mark.asyncio
    async def test_install_tool_not_found(self, orchestrator_no_lifecycle):
        """Installing a non-existent tool returns (False, error)."""
        success, msg = await orchestrator_no_lifecycle.install_tool("nonexistent")
        assert not success
        assert "not found" in msg.lower()

    @pytest.mark.asyncio
    async def test_install_tool_already_installed(self, orchestrator_no_lifecycle):
        """Re-installing an already installed tool returns (True, already)."""
        orchestrator_no_lifecycle._catalog.add_tool(_KNOWN_SERVICE)
        orchestrator_no_lifecycle._catalog.update_status("test-tool", "installed")

        success, msg = await orchestrator_no_lifecycle.install_tool("test-tool")
        assert success
        assert "already" in msg.lower()

    @pytest.mark.asyncio
    async def test_install_and_load(self, registry_path, orchestrator, monkeypatch):
        """Install then load a tool via orchestrator."""
        monkeypatch.setattr(
            "agora.mcp_registry.orchestrator.search_all",
            lambda query="", sources=None: search_registry(f"file://{registry_path}"),
        )

        await orchestrator.discover_and_save(query="test")
        success, msg = await orchestrator.install_tool("kronos")
        assert success

        load_ok, load_msg = await orchestrator.load_tool("kronos")
        assert load_ok, f"Load failed: {load_msg}"

        tool = orchestrator._catalog.get_tool("kronos")
        assert tool["status"] == "loaded"

    @pytest.mark.asyncio
    async def test_load_no_lifecycle(self, orchestrator_no_lifecycle):
        """Loading without lifecycle returns error."""
        orchestrator_no_lifecycle._catalog.add_tool(_KNOWN_SERVICE)
        orchestrator_no_lifecycle._catalog.update_status("test-tool", "installed")

        success, msg = await orchestrator_no_lifecycle.load_tool("test-tool")
        assert not success
        assert "not configured" in msg.lower()

    @pytest.mark.asyncio
    async def test_unload_tool(self, orchestrator, catalog, mock_proxy_manager):
        """Unload a loaded tool."""
        catalog.add_tool(_KNOWN_SERVICE)
        catalog.update_status("test-tool", "loaded")

        load_ok, _ = await orchestrator.load_tool("test-tool")  # ensures tracking
        unload_ok, msg = await orchestrator.unload_tool("test-tool")
        assert unload_ok, f"Unload failed: {msg}"

        tool = catalog.get_tool("test-tool")
        assert tool["status"] == "idle"

    @pytest.mark.asyncio
    async def test_reload_tool(self, orchestrator, catalog, mock_proxy_manager):
        """Reload a tool: unloads then loads."""
        catalog.add_tool(_KNOWN_SERVICE)
        catalog.update_status("test-tool", "loaded")

        await orchestrator.load_tool("test-tool")
        ok, msg = await orchestrator.reload_tool("test-tool")
        assert ok, f"Reload failed: {msg}"

        tool = catalog.get_tool("test-tool")
        assert tool["status"] == "loaded"

    @pytest.mark.asyncio
    async def test_ensure_tool_available_loads_if_needed(self, orchestrator, catalog, mock_proxy_manager):
        """ensure_tool_available should load an installed tool."""
        catalog.add_tool(_KNOWN_SERVICE)
        catalog.update_status("test-tool", "installed")

        ok, msg = await orchestrator.ensure_tool_available("test-tool")
        assert ok, f"ensure_tool_available failed: {msg}"

        tool = catalog.get_tool("test-tool")
        assert tool["status"] == "loaded"

    @pytest.mark.asyncio
    async def test_ensure_tool_available_not_found(self, orchestrator):
        """ensure_tool_available on unknown tool returns False."""
        ok, msg = await orchestrator.ensure_tool_available("nonexistent")
        assert not ok
        assert "not found" in msg.lower()


# ══════════════════════════════════════════════════════════════════════
# Test 4: LifecycleManager
# ══════════════════════════════════════════════════════════════════════


class TestLifecycleManager:
    """LifecycleManager: load/unload, idle timeout, health watch, config building."""

    @pytest.mark.asyncio
    async def test_load_tool_not_found(self, lifecycle):
        """Loading a non-existent tool returns False."""
        ok = await lifecycle.load_tool("nonexistent")
        assert not ok

    @pytest.mark.asyncio
    async def test_load_tool_already_loaded(self, lifecycle, catalog, mock_proxy_manager):
        """Loading an already loaded tool is a no-op returning True."""
        catalog.add_tool(_KNOWN_SERVICE)
        catalog.update_status("test-tool", "loaded")

        ok = await lifecycle.load_tool("test-tool")
        assert ok
        # proxy.add_service should NOT be called for already-loaded tools
        mock_proxy_manager.add_service.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_and_unload_cycle(self, lifecycle, catalog, mock_proxy_manager):
        """Full load → unload cycle with proxy interactions."""
        catalog.add_tool(_KNOWN_SERVICE)
        catalog.update_status("test-tool", "discovered")

        ok = await lifecycle.load_tool("test-tool")
        assert ok
        mock_proxy_manager.add_service.assert_awaited_once()

        tool = catalog.get_tool("test-tool")
        assert tool["status"] == "loaded"

        unload_ok = await lifecycle.unload_tool("test-tool")
        assert unload_ok
        mock_proxy_manager.remove_service.assert_awaited_once_with("test-tool")

        tool = catalog.get_tool("test-tool")
        assert tool["status"] == "idle"

    @pytest.mark.asyncio
    async def test_unload_already_idle(self, lifecycle, catalog):
        """Unloading an idle/not-loaded tool returns True without error."""
        catalog.add_tool(_KNOWN_SERVICE)

        ok = await lifecycle.unload_tool("test-tool")
        assert ok  # Already not loaded

    @pytest.mark.asyncio
    async def test_unload_not_found(self, lifecycle):
        """Unloading a non-existent tool returns False."""
        ok = await lifecycle.unload_tool("nonexistent")
        assert not ok

    @pytest.mark.asyncio
    async def test_load_by_status(self, lifecycle, catalog, mock_proxy_manager):
        """Load all idle tools."""
        svc1 = dict(_KNOWN_SERVICE, id="tool-1", name="tool-1")
        svc2 = dict(_KNOWN_SERVICE, id="tool-2", name="tool-2")
        catalog.add_tool(svc1)
        catalog.add_tool(svc2)
        catalog.update_status("tool-1", "idle")
        catalog.update_status("tool-2", "idle")

        count = await lifecycle.load_by_status("idle")
        assert count == 2

    @pytest.mark.asyncio
    async def test_unload_by_status(self, lifecycle, catalog, mock_proxy_manager):
        """Unload all loaded tools."""
        svc1 = dict(_KNOWN_SERVICE, id="tool-1", name="tool-1")
        svc2 = dict(_KNOWN_SERVICE, id="tool-2", name="tool-2")
        catalog.add_tool(svc1)
        catalog.add_tool(svc2)

        await lifecycle.load_tool("tool-1")
        await lifecycle.load_tool("tool-2")

        count = await lifecycle.unload_by_status("loaded")
        assert count == 2

        for tid in ("tool-1", "tool-2"):
            t = catalog.get_tool(tid)
            assert t["status"] == "idle"

    @pytest.mark.asyncio
    async def test_record_usage(self, lifecycle, catalog):
        """Record usage updates last_used and increments usage_count."""
        catalog.add_tool(_KNOWN_SERVICE)
        catalog.update_status("test-tool", "loaded")

        await lifecycle.load_tool("test-tool")
        await lifecycle.record_usage("test-tool")

        tool = catalog.get_tool("test-tool")
        assert tool["usage_count"] == 1
        assert tool["last_used"] != ""

    @pytest.mark.asyncio
    async def test_usage_callback_wired(self, lifecycle, catalog, mock_proxy_manager):
        """After first load, usage callback is wired to proxy."""
        catalog.add_tool(_KNOWN_SERVICE)

        await lifecycle.load_tool("test-tool")

        mock_proxy_manager.registry.add_usage_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_status(self, lifecycle, catalog, mock_proxy_manager):
        """get_status returns correct counts."""
        catalog.add_tool(_KNOWN_SERVICE)
        await lifecycle.load_tool("test-tool")

        status = lifecycle.get_status()
        assert status["loaded_count"] == 1
        assert "test-tool" in status["loaded"]
        assert not status["idle_watch_running"]
        assert not status["health_watch_running"]


# ══════════════════════════════════════════════════════════════════════
# Test 5: Service Config Building
# ══════════════════════════════════════════════════════════════════════


class TestServiceConfigBuilding:
    """Service config building from catalog entries."""

    def test_http_endpoint(self):
        """HTTP mcp_endpoint produces HTTP transport config."""
        tool = {
            "name": "http-tool",
            "mcp_endpoint": "http://localhost:8080/mcp",
            "metadata": {},
        }
        config = LifecycleManager._build_service_config(tool)
        assert config is not None
        assert config["mcp_endpoint"] == "http://localhost:8080/mcp"
        assert "command" not in config

    def test_metadata_command(self):
        """metadata.command produces stdio config with explicit command."""
        tool = {
            "name": "cmd-tool",
            "metadata": {"command": "my-mcp", "args": ["--port", "9000"]},
        }
        config = LifecycleManager._build_service_config(tool)
        assert config is not None
        assert config["command"] == "my-mcp"
        assert config["args"] == ["--port", "9000"]
        assert config["mcp_endpoint"] == "stdio"

    def test_qualified_entry(self):
        """Dot-qualified entry produces uv run command."""
        tool = {
            "name": "kos-tool",
            "entry": "kos.mcp.server",
            "metadata": {},
        }
        config = LifecycleManager._build_service_config(tool)
        assert config is not None
        assert config["command"] == "uv"
        assert "kos" in str(config["args"])

    def test_simple_entry(self):
        """Simple entry (no dots) produces uv run with entry."""
        tool = {
            "name": "kronos",
            "entry": "kronos-mcp",
            "metadata": {},
        }
        config = LifecycleManager._build_service_config(tool)
        assert config is not None
        assert config["command"] == "uv"
        assert "kronos-mcp" in str(config["args"])

    def test_install_path(self):
        """install_path produces stdio config with explicit path."""
        tool = {
            "name": "path-tool",
            "install_path": "/usr/local/bin/my-mcp",
            "metadata": {},
        }
        config = LifecycleManager._build_service_config(tool)
        assert config is not None
        assert config["command"] == "/usr/local/bin/my-mcp"
        assert config["args"] == []

    def test_node_type(self):
        """tool_type='node' produces npx command."""
        tool = {
            "name": "node-tool",
            "tool_type": "node",
            "metadata": {},
        }
        config = LifecycleManager._build_service_config(tool)
        assert config is not None
        assert config["command"] == "npx"
        assert "-y" in config["args"]

    def test_python_type(self):
        """tool_type='python' produces pipx command."""
        tool = {
            "name": "python-tool",
            "tool_type": "python",
            "metadata": {},
        }
        config = LifecycleManager._build_service_config(tool)
        assert config is not None
        assert config["command"] == "pipx"

    def test_empty_name(self):
        """Empty name returns None."""
        assert LifecycleManager._build_service_config({"name": ""}) is None

    def test_no_entry(self):
        """No entry, install_path, or type returns None."""
        tool = {"name": "unconfigurable", "metadata": {}}
        config = LifecycleManager._build_service_config(tool)
        assert config is None

    def test_repo_url_only(self):
        """Only repo_url without usable config returns None."""
        tool = {
            "name": "repo-only",
            "repo_url": "https://github.com/org/repo",
            "metadata": {},
        }
        config = LifecycleManager._build_service_config(tool)
        assert config is None


# ══════════════════════════════════════════════════════════════════════
# Test 6: ToolCatalog Extended Operations
# ══════════════════════════════════════════════════════════════════════


class TestToolCatalogExtended:
    """Extended ToolCatalog operations beyond basic CRUD."""

    @pytest.mark.asyncio
    async def test_update_entry(self, catalog):
        """update_entry correctly updates entry, install_path, and metadata."""
        catalog.add_tool(_KNOWN_SERVICE)

        ok = catalog.update_entry(
            "test-tool",
            entry="new.entry.point",
            install_path="/opt/tools/test-tool",
            metadata={"command": "my-cmd", "args": ["--debug"]},
        )
        assert ok

        tool = catalog.get_tool("test-tool")
        assert tool["entry"] == "new.entry.point"
        assert tool["install_path"] == "/opt/tools/test-tool"
        assert tool["metadata"]["command"] == "my-cmd"
        assert tool["metadata"]["args"] == ["--debug"]

    @pytest.mark.asyncio
    async def test_update_entry_not_found(self, catalog):
        """update_entry on non-existent tool returns False."""
        assert not catalog.update_entry("nonexistent")

    @pytest.mark.asyncio
    async def test_update_entry_merge_metadata(self, catalog):
        """update_entry merges metadata instead of replacing."""
        catalog.add_tool(_KNOWN_SERVICE)

        catalog.update_entry("test-tool", metadata={"command": "run"})

        tool = catalog.get_tool("test-tool")
        # Original metadata should still be there
        assert tool["metadata"]["verified"] is True
        assert tool["metadata"]["command"] == "run"

    @pytest.mark.asyncio
    async def test_update_install(self, catalog):
        """update_install sets status to installed + stores path and error."""
        catalog.add_tool(_KNOWN_SERVICE)

        ok = catalog.update_install("test-tool", install_path="/opt/tools/test")
        assert ok

        tool = catalog.get_tool("test-tool")
        assert tool["status"] == "installed"
        assert tool["install_path"] == "/opt/tools/test"

    @pytest.mark.asyncio
    async def test_update_install_with_error(self, catalog):
        """update_install captures install errors."""
        catalog.add_tool(_KNOWN_SERVICE)

        ok = catalog.update_install("test-tool", install_path="", install_error="dep missing")
        assert ok

        tool = catalog.get_tool("test-tool")
        assert tool["status"] == "installed"
        assert tool["install_error"] == "dep missing"

    @pytest.mark.asyncio
    async def test_update_quality(self, catalog):
        """update_quality modifies the quality_score."""
        catalog.add_tool(_KNOWN_SERVICE)

        ok = catalog.update_quality("test-tool", 0.85)
        assert ok

        tool = catalog.get_tool("test-tool")
        assert tool["quality_score"] == 0.85

    @pytest.mark.asyncio
    async def test_update_quality_not_found(self, catalog):
        """update_quality on non-existent tool returns False."""
        assert not catalog.update_quality("nonexistent", 0.5)

    @pytest.mark.asyncio
    async def test_record_usage(self, catalog):
        """record_usage increments usage_count and sets last_used."""
        catalog.add_tool(_KNOWN_SERVICE)

        ok = catalog.record_usage("test-tool")
        assert ok

        tool = catalog.get_tool("test-tool")
        assert tool["usage_count"] == 1
        assert tool["last_used"] != ""

        # Second call increments
        catalog.record_usage("test-tool")
        tool = catalog.get_tool("test-tool")
        assert tool["usage_count"] == 2

    @pytest.mark.asyncio
    async def test_remove_tool(self, catalog):
        """remove_tool deletes the tool and returns True."""
        catalog.add_tool(_KNOWN_SERVICE)
        assert catalog.get_tool("test-tool") is not None

        ok = catalog.remove_tool("test-tool")
        assert ok
        assert catalog.get_tool("test-tool") is None

    @pytest.mark.asyncio
    async def test_remove_tool_not_found(self, catalog):
        """remove_tool on non-existent tool returns False."""
        assert not catalog.remove_tool("nonexistent")

    @pytest.mark.asyncio
    async def test_search_tools_by_name(self, catalog_populated):
        """search_tools finds tools by name substring."""
        results = catalog_populated.search_tools(query="kronos", limit=5)
        assert len(results) >= 1
        assert any("kronos" in t["name"] for t in results)

    @pytest.mark.asyncio
    async def test_search_tools_by_description(self, catalog_populated):
        """search_tools finds tools by description substring."""
        results = catalog_populated.search_tools(query="analysis", limit=5)
        # Should find tools with 'analysis' in name or description
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_search_tools_by_tag(self, catalog_populated):
        """search_tools finds tools by tags (stored as JSON string)."""
        results = catalog_populated.search_tools(query="known_service", limit=10)
        assert len(results) >= 5, f"Expected >=5 with 'known_service', got {len(results)}"

    @pytest.mark.asyncio
    async def test_search_tools_with_status_filter(self, catalog):
        """search_tools respects status filter."""
        catalog.add_tool(dict(_KNOWN_SERVICE))
        catalog.update_status("test-tool", "loaded")

        results = catalog.search_tools(query="test", status="loaded")
        assert len(results) == 1

        results = catalog.search_tools(query="test", status="idle")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_tools_empty_query(self, catalog_populated):
        """Empty query returns all tools (limited)."""
        results = catalog_populated.search_tools(query="", limit=5)
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_count_by_status(self, catalog):
        """count_by_status returns correct counts."""
        catalog.add_tool(dict(_KNOWN_SERVICE, id="t1", name="t1"))
        catalog.add_tool(dict(_KNOWN_SERVICE, id="t2", name="t2"))
        catalog.add_tool(dict(_KNOWN_SERVICE, id="t3", name="t3"))

        catalog.update_status("t1", "installed")
        catalog.update_status("t2", "loaded")
        catalog.update_status("t3", "idle")

        counts = catalog.count_by_status()
        assert counts.get("discovered", 0) == 0
        assert counts.get("installed", 0) == 1
        assert counts.get("loaded", 0) == 1
        assert counts.get("idle", 0) == 1

    @pytest.mark.asyncio
    async def test_list_tools_by_status(self, catalog):
        """list_tools with status filter works."""
        catalog.add_tool(dict(_KNOWN_SERVICE, id="t1", name="t1"))
        catalog.update_status("t1", "loaded")

        loaded = catalog.list_tools(status="loaded")
        assert len(loaded) == 1
        assert loaded[0]["id"] == "t1"

        idle = catalog.list_tools(status="idle")
        assert len(idle) == 0


# ══════════════════════════════════════════════════════════════════════
# Test 7: QualityScorer Extended
# ══════════════════════════════════════════════════════════════════════


class TestQualityScorerExtended:
    """Unit tests for individual QualityScorer normalization methods."""

    def test_normalize_stars_zero(self):
        assert QualityScorer.normalize_stars(0) == 0.0
        assert QualityScorer.normalize_stars(-1) == 0.0

    def test_normalize_stars_low(self):
        assert QualityScorer.normalize_stars(1) == 0.2
        assert QualityScorer.normalize_stars(9) == 0.2

    def test_normalize_stars_medium(self):
        assert QualityScorer.normalize_stars(10) == 0.4
        assert QualityScorer.normalize_stars(50) == 0.4
        assert QualityScorer.normalize_stars(99) == 0.4

    def test_normalize_stars_high(self):
        assert QualityScorer.normalize_stars(100) == 0.6
        assert QualityScorer.normalize_stars(499) == 0.6
        assert QualityScorer.normalize_stars(500) == 0.8

    def test_normalize_stars_very_high(self):
        assert QualityScorer.normalize_stars(1000) == 0.9
        assert QualityScorer.normalize_stars(4999) == 0.9
        assert QualityScorer.normalize_stars(5000) == 1.0
        assert QualityScorer.normalize_stars(10000) == 1.0

    def test_normalize_freshness_none(self):
        assert QualityScorer.normalize_freshness(None) == 0.5
        assert QualityScorer.normalize_freshness("") == 0.5

    def test_normalize_freshness_invalid(self):
        assert QualityScorer.normalize_freshness("not-a-date") == 0.5

    def test_normalize_freshness_recent(self):
        from datetime import datetime, timedelta

        recent = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        assert QualityScorer.normalize_freshness(recent) == 1.0

    def test_normalize_freshness_old(self):
        old = "2020-01-01T00:00:00Z"
        assert QualityScorer.normalize_freshness(old) == 0.2

    def test_normalize_version_empty(self):
        assert QualityScorer.normalize_version("") == 0.3
        assert QualityScorer.normalize_version(None) == 0.3

    def test_normalize_version_full(self):
        assert QualityScorer.normalize_version("1.2.3") == 1.0
        assert QualityScorer.normalize_version("v1.2.3") == 1.0

    def test_normalize_version_minor(self):
        assert QualityScorer.normalize_version("1.2") == 0.7
        assert QualityScorer.normalize_version("v1.2") == 0.7

    def test_normalize_version_major_only(self):
        assert QualityScorer.normalize_version("1") == 0.4
        assert QualityScorer.normalize_version("v1") == 0.4

    def test_normalize_local_usage_zero(self):
        assert QualityScorer.normalize_local_usage(0) == 0.0

    def test_normalize_local_usage_low(self):
        assert QualityScorer.normalize_local_usage(1) == 0.1
        assert QualityScorer.normalize_local_usage(2) == 0.1
        assert QualityScorer.normalize_local_usage(3) == 0.3
        assert QualityScorer.normalize_local_usage(9) == 0.3
        assert QualityScorer.normalize_local_usage(10) == 0.5

    def test_normalize_local_usage_high(self):
        assert QualityScorer.normalize_local_usage(50) == 0.9
        assert QualityScorer.normalize_local_usage(100) == 1.0

    def test_evaluate_verified_service(self):
        """evaluate with verified=True and zero stars still has positive score."""
        score = QualityScorer.evaluate(
            {
                "stars": 0,
                "version": "",
                "usage_count": 0,
                "metadata": {"verified": True},
            }
        )
        assert score > 0
        assert score <= 1.0

    def test_evaluate_unverified_no_data(self):
        """evaluate with no data should produce a very low but valid score."""
        score = QualityScorer.evaluate({})
        assert 0.0 <= score <= 1.0

    def test_evaluate_high_star_service(self):
        """High star count should contribute significantly to score."""
        score = QualityScorer.evaluate(
            {
                "stars": 5000,
                "version": "v2.0.0",
                "usage_count": 100,
                "metadata": {"verified": True, "updated_at": "2026-06-01T00:00:00Z"},
            }
        )
        assert score >= 0.5, f"Expected high score, got {score}"

    def test_evaluate_idle_decay(self):
        """Old last_used timestamp should reduce score via decay."""
        score_active = QualityScorer.evaluate(
            {
                "stars": 100,
                "version": "1.0.0",
                "usage_count": 10,
                "last_used": None,
                "metadata": {"verified": True, "updated_at": "2026-06-01T00:00:00Z"},
            }
        )
        score_idle = QualityScorer.evaluate(
            {
                "stars": 100,
                "version": "1.0.0",
                "usage_count": 10,
                "last_used": "2020-01-01T00:00:00Z",
                "metadata": {"verified": True, "updated_at": "2026-06-01T00:00:00Z"},
            }
        )
        # Idle decay should reduce score to 80%
        assert score_idle == pytest.approx(score_active * 0.8, rel=0.01), (
            f"Idle decay failed: active={score_active}, idle={score_idle}"
        )


# ══════════════════════════════════════════════════════════════════════
# Test 8: search_all Source Merging
# ══════════════════════════════════════════════════════════════════════


class TestSearchAllSourceMerging:
    """search_all with multiple sources, deduplication, and scoring."""

    @pytest.mark.asyncio
    async def test_search_all_with_registry_only(self, registry_path, monkeypatch):
        """search_all with only local registry source."""
        monkeypatch.setattr(
            "agora.mcp_registry.sources.search_github",
            AsyncMock(return_value=[]),
        )

        # Use the real search_registry but with local file URL
        async def _local_registry():
            return await search_registry(f"file://{registry_path}")

        monkeypatch.setattr(
            "agora.mcp_registry.sources.search_registry",
            _local_registry,
        )

        results = await search_all(query="mcp-server", sources=["github", "registry"])
        assert len(results) >= 30

        # All results should be scored
        for r in results:
            assert "quality_score" in r

        # Should be sorted by quality_score descending
        scores = [r["quality_score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_search_all_empty_sources(self):
        """search_all with empty sources list returns [].

        We just need to trigger the "no valid sources" warning path.
        Giving an empty sources list means no tasks run.
        """
        results = await search_all(query="test", sources=[])
        assert results == []

    @pytest.mark.asyncio
    async def test_search_all_with_mocked_registry(self, monkeypatch):
        """search_all with a small mocked registry to test merge logic."""
        mock_source = [
            {
                "name": "tool-alpha",
                "description": "Alpha tool",
                "stars": 10,
                "source": "registry",
                "tags": [],
                "metadata": {"verified": True},
            },
            {
                "name": "tool-beta",
                "description": "Beta tool",
                "stars": 500,
                "source": "registry",
                "tags": [],
                "metadata": {"verified": True},
            },
        ]

        monkeypatch.setattr(
            "agora.mcp_registry.sources.search_github",
            AsyncMock(return_value=[]),
        )
        monkeypatch.setattr(
            "agora.mcp_registry.sources.search_registry",
            AsyncMock(return_value=mock_source),
        )

        results = await search_all(query="test")
        assert len(results) == 2

        # beta has more stars (500 → 0.8 vs alpha's 10 → 0.4), should score higher
        assert results[0]["name"] == "tool-beta"
        assert results[1]["name"] == "tool-alpha"


# ══════════════════════════════════════════════════════════════════════
# Test 9: Router with Direct and Auto Modes
# ══════════════════════════════════════════════════════════════════════


class TestRouterModes:
    """SmartRouter — direct, recommend, auto modes."""

    @pytest.mark.asyncio
    async def test_route_direct_found_loaded(self, catalog):
        """Direct mode finds a loaded tool."""
        catalog.add_tool(dict(_KNOWN_SERVICE, id="kronos", name="kronos"))
        catalog.update_status("kronos", "loaded")

        router = SmartRouter(catalog=catalog)
        result = await router.route("kronos", mode="direct")

        assert result["status"] == "ok"
        assert result["mode"] == "direct"
        assert result["action"] == "call"
        assert result["tool"]["name"] == "kronos"

    @pytest.mark.asyncio
    async def test_route_direct_found_not_loaded(self, catalog):
        """Direct mode finds an unloaded tool and returns load_and_call."""
        catalog.add_tool(dict(_KNOWN_SERVICE, id="kronos", name="kronos"))
        catalog.update_status("kronos", "installed")

        router = SmartRouter(catalog=catalog)
        result = await router.route("kronos", mode="direct")

        assert result["status"] == "ok"
        assert result["action"] == "load_and_call"

    @pytest.mark.asyncio
    async def test_route_direct_not_found(self, catalog):
        """Direct mode returns no_match when tool not found."""
        router = SmartRouter(catalog=catalog)
        result = await router.route("nonexistent-tool", mode="direct")

        assert result["status"] == "ok"
        assert result["action"] == "no_match"
        assert result["tool"] is None

    @pytest.mark.asyncio
    async def test_route_recommend_keyword_fallback(self, catalog):
        """Recommend mode falls back to keyword search when no embeddings."""
        catalog.add_tool(dict(_KNOWN_SERVICE, id="kronos", name="kronos", description="Knowledge ingestion pipeline"))
        catalog.add_tool(
            dict(_KNOWN_SERVICE, id="codeanalyze", name="codeanalyze", description="Code analysis and review tool")
        )

        router = SmartRouter(catalog=catalog, embeddings=None)
        result = await router.route("code analysis", mode="recommend")

        assert result["status"] == "ok"
        assert result["action"] in ("select", "no_match")
        if result.get("tools"):
            tool_names = [t["name"] for t in result["tools"]]
            assert any("codeanalyz" in t.lower() for t in tool_names)

    @pytest.mark.asyncio
    async def test_route_auto_direct_first(self, catalog):
        """Auto mode tries direct first."""
        catalog.add_tool(dict(_KNOWN_SERVICE, id="kronos", name="kronos"))
        catalog.update_status("kronos", "loaded")

        router = SmartRouter(catalog=catalog)
        result = await router.route("kronos do something", mode="auto")

        assert result["status"] == "ok"
        assert "direct" in result.get("mode", "")

    @pytest.mark.asyncio
    async def test_route_auto_recommend_fallback(self, catalog):
        """Auto mode falls back to recommend when direct fails."""
        catalog.add_tool(dict(_KNOWN_SERVICE, id="codeanalyze", name="codeanalyze", description="Code analysis tool"))
        catalog.update_status("codeanalyze", "loaded")

        router = SmartRouter(catalog=catalog)
        result = await router.route("find a tool for code review", mode="auto")

        assert result["status"] == "ok"
        # Should have found something via recommend fallback
        if result.get("tools"):
            assert len(result["tools"]) >= 1

    @pytest.mark.asyncio
    async def test_router_empty_catalog_no_match(self, catalog):
        """Router with empty catalog returns action=no_match (not error)."""
        router = SmartRouter(catalog=catalog)
        result = await router.route("anything", mode="recommend")

        assert result["status"] == "ok"
        assert result.get("action") == "no_match"

    @pytest.mark.asyncio
    async def test_router_status(self, catalog):
        """router.status() returns correct fields."""
        router = SmartRouter(catalog=catalog)
        status = router.status()

        assert status["mode"] == "smart_router"
        assert "llm_available" in status
        assert "embeddings_available" in status
        assert "lifecycle_available" in status
        assert "orchestrator_available" in status

    @pytest.mark.asyncio
    async def test_router_with_orchestrator_but_no_auto_discover(self, catalog):
        """Router with orchestrator but empty catalog returns no_match (doesn't auto-discover without call)."""
        orchestra = MagicMock()
        router = SmartRouter(catalog=catalog, orchestrator=orchestra)

        result = await router.route("anything", mode="recommend")
        assert result["status"] == "ok"
        assert result.get("action") == "no_match"


# ══════════════════════════════════════════════════════════════════════
# Test 10: EmbeddingStore Extended
# ══════════════════════════════════════════════════════════════════════


class TestEmbeddingStoreExtended:
    """Extended EmbeddingStore operations."""

    @pytest.mark.asyncio
    async def test_rebuild_all_empty_catalog(self, embeddings, catalog):
        """rebuild_all with empty catalog returns 0 (no crash)."""
        saved = embeddings.rebuild_all(catalog)
        assert saved == 0

    @pytest.mark.asyncio
    async def test_save_and_search_similar(self, embeddings):
        """Save and search similar with direct embedding vectors."""
        # Save a fake 384-dim embedding for a tool
        dim = 384
        vec = [0.1] * dim
        ok = embeddings.save_embedding("test-tool", vec)
        assert ok, "Failed to save embedding"

        # Search with a query vector (same direction => high similarity)
        similar = embeddings.search_similar("something", top_k=5)
        # Without model, compute_embedding returns None, so search returns []
        if not embeddings.available:
            assert similar == []
        else:
            assert len(similar) >= 1

    @pytest.mark.asyncio
    async def test_save_text_embedding(self, embeddings):
        """save_text_embedding computes and saves embedding (if model available)."""
        ok = embeddings.save_text_embedding("test-tool", "some text to embed")
        if embeddings.available:
            assert ok
        else:
            assert not ok

    @pytest.mark.asyncio
    async def test_available_property(self, embeddings):
        """available property returns bool without raising."""
        assert isinstance(embeddings.available, bool)

    @pytest.mark.asyncio
    async def test_rebuild_all_from_catalog(self, registry_path, embeddings):
        """rebuild_all from populated catalog (may be 0 if model unavailable)."""
        c = ToolCatalog(db_path=":memory:")
        results = await search_registry(f"file://{registry_path}")
        for svc in results:
            c.add_tool(svc)

        saved = embeddings.rebuild_all(c)
        assert isinstance(saved, int)
        if not embeddings.available:
            assert saved == 0
        c.close()


# ══════════════════════════════════════════════════════════════════════
# Test 11: Cleanup and Shutdown
# ══════════════════════════════════════════════════════════════════════


class TestCleanupShutdown:
    """Proper cleanup of orchestrator, lifecycle, and catalog resources."""

    @pytest.mark.asyncio
    async def test_lifecycle_close_unloads_all(self, catalog, mock_proxy_manager):
        """LifecycleManager.close unloads all loaded tools."""
        lm = LifecycleManager(catalog=catalog, proxy_manager=mock_proxy_manager)
        catalog.add_tool(dict(_KNOWN_SERVICE, id="tool-1", name="tool-1"))
        catalog.add_tool(dict(_KNOWN_SERVICE, id="tool-2", name="tool-2"))

        await lm.load_tool("tool-1")
        await lm.load_tool("tool-2")

        await lm.close()

        # Both tools should now be idle
        t1 = catalog.get_tool("tool-1")
        t2 = catalog.get_tool("tool-2")
        assert t1["status"] == "idle"
        assert t2["status"] == "idle"

        # Watchers should be stopped
        assert lm._idle_watch_task is None
        assert lm._health_watch_task is None

    @pytest.mark.asyncio
    async def test_orchestrator_close_cleanup(self, catalog, mock_proxy_manager):
        """Orchestrator.close cleans up lifecycle and catalog."""
        lm = LifecycleManager(catalog=catalog, proxy_manager=mock_proxy_manager)

        catalog.add_tool(_KNOWN_SERVICE)
        await lm.load_tool("test-tool")

        # Capture status before close
        tool_before = catalog.get_tool("test-tool")
        assert tool_before["status"] == "loaded"

        orch = Orchestrator(catalog=catalog, lifecycle=lm)
        await orch.close()

        # After close, catalog connection is closed (:memory: db)
        # But we can verify the lifecycle unloaded everything by checking
        # that remove_service was called and no loaded tools remain
        mock_proxy_manager.remove_service.assert_awaited_with("test-tool")
        assert lm._idle_watch_task is None
        assert lm._health_watch_task is None

    @pytest.mark.asyncio
    async def test_orchestrator_close_no_lifecycle(self, catalog):
        """Orchestrator.close without lifecycle only closes catalog."""
        orch = Orchestrator(catalog=catalog, lifecycle=None)
        # Should not raise
        await orch.close()

    @pytest.mark.asyncio
    async def test_lifecycle_close_no_proxy(self, catalog):
        """LifecycleManager.close without proxy works."""
        lm = LifecycleManager(catalog=catalog, proxy_manager=None)
        # Should not raise
        await lm.close()


# ══════════════════════════════════════════════════════════════════════
# Test 12: Orchestrator — Usage Recording
# ══════════════════════════════════════════════════════════════════════


class TestOrchestratorUsageRecording:
    """Usage recording through orchestrator with and without lifecycle."""

    @pytest.mark.asyncio
    async def test_record_usage_with_lifecycle(self, catalog, orchestrator):
        """record_usage with lifecycle should update usage count."""
        catalog.add_tool(_KNOWN_SERVICE)

        await orchestrator.record_usage("test-tool")
        tool = catalog.get_tool("test-tool")
        assert tool["usage_count"] == 1

    @pytest.mark.asyncio
    async def test_record_usage_without_lifecycle(self, catalog, orchestrator_no_lifecycle):
        """record_usage without lifecycle should still update catalog."""
        catalog.add_tool(_KNOWN_SERVICE)

        await orchestrator_no_lifecycle.record_usage("test-tool")
        tool = catalog.get_tool("test-tool")
        assert tool["usage_count"] == 1


# ══════════════════════════════════════════════════════════════════════
# Test 13: Orchestrator — Batch Load/Unload
# ══════════════════════════════════════════════════════════════════════


class TestOrchestratorBatchOperations:
    """Batch load/unload operations through orchestrator."""

    @pytest.mark.asyncio
    async def test_load_all_idle(self, catalog, mock_proxy_manager):
        """load_all_idle loads all idle tools."""
        lm = LifecycleManager(catalog=catalog, proxy_manager=mock_proxy_manager)
        orch = Orchestrator(catalog=catalog, lifecycle=lm)

        svc1 = dict(_KNOWN_SERVICE, id="tool-1", name="tool-1")
        svc2 = dict(_KNOWN_SERVICE, id="tool-2", name="tool-2")
        catalog.add_tool(svc1)
        catalog.add_tool(svc2)
        catalog.update_status("tool-1", "idle")
        catalog.update_status("tool-2", "idle")

        count = await orch.load_all_idle()
        assert count == 2

        await orch.close()

    @pytest.mark.asyncio
    async def test_unload_all_loaded(self, catalog, mock_proxy_manager):
        """unload_all_loaded unloads all loaded tools."""
        lm = LifecycleManager(catalog=catalog, proxy_manager=mock_proxy_manager)
        orch = Orchestrator(catalog=catalog, lifecycle=lm)

        svc1 = dict(_KNOWN_SERVICE, id="tool-1", name="tool-1")
        svc2 = dict(_KNOWN_SERVICE, id="tool-2", name="tool-2")
        catalog.add_tool(svc1)
        catalog.add_tool(svc2)

        await lm.load_tool("tool-1")
        await lm.load_tool("tool-2")

        count = await orch.unload_all_loaded()
        assert count == 2

        await orch.close()

    @pytest.mark.asyncio
    async def test_batch_operations_no_lifecycle(self, catalog, orchestrator_no_lifecycle):
        """Batch operations without lifecycle return 0 without error."""
        count = await orchestrator_no_lifecycle.load_all_idle()
        assert count == 0

        count = await orchestrator_no_lifecycle.unload_all_loaded()
        assert count == 0
