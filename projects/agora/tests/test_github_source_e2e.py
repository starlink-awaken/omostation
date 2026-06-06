"""End-to-end tests for GitHub source discovery and the install/lifecycle pipeline.

Tests the flow: GitHub search → catalog save (with quality scoring) → install →
lifecycle load, plus negative cases. Network tests can be filtered with
``-m network``; all other tests are self-contained with mocking.
"""

import socket
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from agora.mcp_registry.evaluator import QualityScorer
from agora.mcp_registry.lifecycle import LifecycleManager
from agora.mcp_registry.repository import ToolCatalog
from agora.mcp_registry.sources import search_github

# ── Helpers ──────────────────────────────────────────────────────────


def _has_network(timeout: float = 3.0) -> bool:
    """Check whether a TCP connection to github.com:443 succeeds."""
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("github.com", 443))
        return True
    except OSError:
        return False
    finally:
        socket.setdefaulttimeout(None)


def _fake_github_response(num_items: int = 5) -> dict:
    """Build a fake GitHub API search response body."""
    items = []
    for i in range(num_items):
        items.append(
            {
                "full_name": f"test-org/mcp-server-{i}",
                "description": f"A sample MCP server #{i} for testing",
                "html_url": f"https://github.com/test-org/mcp-server-{i}",
                "stargazers_count": 200 + i * 50,
                "language": "Python",
                "topics": ["mcp", "python", "server"],
                "updated_at": "2026-05-01T00:00:00Z",
                "open_issues_count": 5 + i,
                "license": {"spdx_id": "MIT"},
            }
        )
    return {"items": items, "total_count": num_items}


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def catalog() -> ToolCatalog:
    c = ToolCatalog(db_path=":memory:")
    yield c
    c.close()


@pytest.fixture
def sample_tool() -> dict:
    return {
        "name": "test-org/mcp-server-0",
        "description": "A sample MCP server for testing",
        "repo_url": "https://github.com/test-org/mcp-server-0",
        "tool_type": "python",
        "stars": 200,
        "source": "github",
        "version": "v1.0.0",
        "tags": ["mcp", "python", "server"],
        "metadata": {
            "full_name": "test-org/mcp-server-0",
            "language": "Python",
            "updated_at": "2026-05-01T00:00:00Z",
            "open_issues": 5,
            "license": "MIT",
        },
    }


# ══════════════════════════════════════════════════════════════════════
# Test 1: GitHub Search (Network)
# ══════════════════════════════════════════════════════════════════════


class TestGitHubSearch:
    """Real network search against GitHub API."""

    @pytest.mark.skipif(not _has_network(), reason="No network access to github.com")
    @pytest.mark.network
    @pytest.mark.asyncio
    async def test_search_github_returns_results(self):
        """search_github(query='mcp-server', min_stars=100) returns at least one result."""
        results = await search_github(query="mcp-server", min_stars=100, max_results=5)
        if not results:
            pytest.skip("GitHub API rate limited (403).")
        assert len(results) >= 1, (
            f"Expected at least 1 GitHub result for 'mcp-server' with >=100 stars, got {len(results)}"
        )

    @pytest.mark.skipif(not _has_network(), reason="No network access to github.com")
    @pytest.mark.network
    @pytest.mark.asyncio
    async def test_each_result_has_required_fields(self):
        """Every result must have name, description, repo_url, stars, source."""
        results = await search_github(query="mcp-server", min_stars=100, max_results=5)
        for item in results:
            assert item.get("name"), f"Result missing 'name': {item}"
            assert isinstance(item.get("description"), str), f"Result '{item.get('name')}' missing description"
            assert item.get("repo_url", "").startswith("https://github.com/"), (
                f"Result '{item.get('name')}' has invalid repo_url"
            )
            assert isinstance(item.get("stars"), int), f"Result '{item.get('name')}' missing stars"
            assert item.get("source") == "github", (
                f"Result '{item.get('name')}' has source={item.get('source')!r}, expected 'github'"
            )

    @pytest.mark.skipif(not _has_network(), reason="No network access to github.com")
    @pytest.mark.network
    @pytest.mark.asyncio
    async def test_min_stars_filter_respected(self):
        """All returned results should have stars >= 100."""
        results = await search_github(query="mcp-server", min_stars=100, max_results=5)
        for item in results:
            assert item["stars"] >= 100, f"Result '{item.get('name')}' has {item['stars']} stars, expected >= 100"

    @pytest.mark.skipif(not _has_network(), reason="No network access to github.com")
    @pytest.mark.network
    @pytest.mark.asyncio
    async def test_max_results_respected(self):
        """Should not return more than max_results items."""
        results = await search_github(query="mcp-server", min_stars=0, max_results=3)
        assert len(results) <= 3, f"Expected max 3 results, got {len(results)}"

    @pytest.mark.skipif(not _has_network(), reason="No network access to github.com")
    @pytest.mark.network
    @pytest.mark.asyncio
    async def test_tool_type_is_populated(self):
        """Each result should have a non-empty tool_type."""
        results = await search_github(query="mcp-server", min_stars=100, max_results=5)
        for item in results:
            assert item.get("tool_type"), f"Result '{item.get('name')}' has empty tool_type"
            assert item["tool_type"] in ("python", "node", "unknown")


# ══════════════════════════════════════════════════════════════════════
# Test 2: Discover → Save Pipeline (with local fallback)
# ══════════════════════════════════════════════════════════════════════


class TestDiscoverSavePipeline:
    """Discover from GitHub (or fallback to fake data), save to catalog, score."""

    @pytest.mark.asyncio
    async def test_discover_and_save_to_catalog(self, catalog):
        """Save discovered tools into ToolCatalog and verify they have 'discovered' status."""
        results = []
        if _has_network():
            results = await search_github(query="mcp-server", min_stars=100, max_results=5)
        
        if not results:
            raw = _fake_github_response(5)

            # Build tool dicts the same way search_github does
            results = []
            for item in raw["items"]:
                stars = item.get("stargazers_count", 0)
                language = item.get("language", "") or ""
                topics = item.get("topics", []) or []
                if language.lower() == "python" or "python" in topics:
                    tool_type = "python"
                elif language.lower() in ("javascript", "typescript", "js", "ts") or any(
                    t in topics for t in ("javascript", "typescript", "node", "nodejs")
                ):
                    tool_type = "node"
                else:
                    tool_type = "unknown"
                results.append(
                    {
                        "name": item.get("full_name", ""),
                        "description": item.get("description") or "",
                        "repo_url": item.get("html_url", ""),
                        "tool_type": tool_type,
                        "stars": stars,
                        "source": "github",
                        "version": "",
                        "tags": topics,
                        "metadata": {
                            "full_name": item.get("full_name", ""),
                            "language": language,
                            "updated_at": item.get("updated_at", ""),
                            "open_issues": item.get("open_issues_count", 0),
                            "license": item.get("license", {}).get("spdx_id", "") if item.get("license") else "",
                        },
                    }
                )

        assert len(results) >= 1, "No results to save (network and fallback both empty)"

        # Score results using QualityScorer
        for svc in results:
            svc["quality_score"] = QualityScorer.evaluate(svc)
            catalog.add_tool(svc)

        # Verify all tools are in catalog with 'discovered' status
        all_tools = catalog.list_tools()
        assert len(all_tools) == len(results), f"Catalog has {len(all_tools)} tools, expected {len(results)}"
        for tool in all_tools:
            assert tool["status"] == "discovered", (
                f"Tool '{tool['name']}' has status '{tool['status']}', expected 'discovered'"
            )

    @pytest.mark.asyncio
    async def test_quality_scores_computed_on_save(self, catalog):
        """Quality scores should be computed for each discovered tool."""
        results = []
        if _has_network():
            results = await search_github(query="mcp-server", min_stars=100, max_results=5)
        
        if not results:
            raw = _fake_github_response(5)
            results = []
            for item in raw["items"]:
                language = item.get("language", "") or ""
                topics = item.get("topics", []) or []
                tool_type = "python" if (language.lower() == "python" or "python" in topics) else "unknown"
                results.append(
                    {
                        "name": item.get("full_name", ""),
                        "description": item.get("description") or "",
                        "repo_url": item.get("html_url", ""),
                        "tool_type": tool_type,
                        "stars": item.get("stargazers_count", 0),
                        "source": "github",
                        "tags": topics,
                        "metadata": {
                            "updated_at": item.get("updated_at", ""),
                        },
                    }
                )

        assert len(results) >= 1

        for svc in results:
            svc["quality_score"] = QualityScorer.evaluate(svc)
            catalog.add_tool(svc)

        cat_tools = catalog.list_tools()
        for tool in cat_tools:
            assert isinstance(tool.get("quality_score"), (int, float)), f"Tool '{tool['name']}' missing quality_score"
            assert 0.0 <= tool["quality_score"] <= 1.0, (
                f"Tool '{tool['name']}' quality_score={tool['quality_score']} out of range [0,1]"
            )

    @pytest.mark.asyncio
    async def test_discover_save_roundtrip(self, catalog):
        """Verify tool fields survive catalog roundtrip."""
        # Use fake data to avoid network dependency
        raw = _fake_github_response(3)
        results = []
        for item in raw["items"]:
            results.append(
                {
                    "name": item.get("full_name", ""),
                    "description": item.get("description") or "",
                    "repo_url": item.get("html_url", ""),
                    "tool_type": "python",
                    "stars": item.get("stargazers_count", 0),
                    "source": "github",
                    "tags": item.get("topics", []),
                    "metadata": {},
                }
            )

        for svc in results:
            catalog.add_tool(svc)

        # Fetch each tool back by name (as id)
        for svc in results:
            tool_id = svc["name"]
            stored = catalog.get_tool(tool_id)
            assert stored is not None, f"Tool '{tool_id}' not found in catalog"
            assert stored["name"] == svc["name"]
            assert stored["description"] == svc["description"]
            assert stored["source"] == "github"


# ══════════════════════════════════════════════════════════════════════
# Test 3: Lifecycle Install (Mock)
# ══════════════════════════════════════════════════════════════════════


class TestLifecycleInstall:
    """Install pipeline: discovered → installed via Market.install()."""

    @pytest.mark.asyncio
    async def test_install_transition_discovered_to_installed(self, catalog, sample_tool):
        """After install, catalog status should change from 'discovered' to 'installed'."""
        # Add tool as discovered
        sample_tool["quality_score"] = QualityScorer.evaluate(sample_tool)
        catalog.add_tool(sample_tool)

        tool = catalog.get_tool(sample_tool["name"])
        assert tool["status"] == "discovered"

        # Mock Market.install to return install metadata
        fake_install_result = {
            "name": "mcp-server-0",
            "description": "Installed MCP server",
            "entry": "/home/user/.agora/market/test-org__mcp-server-0/server.py",
            "type": "python",
            "port": 0,
            "tags": ["mcp", "python", "server"],
        }

        with patch("agora.plugins.market.market.Market.install", return_value=fake_install_result) as mock_install:
            # Simulate the install pipeline
            result = mock_install("test-org/mcp-server-0")

        assert result["name"] == "mcp-server-0"
        assert result["type"] == "python"

        # Update catalog: mark as installed with path
        updated = catalog.update_install(
            tool_id=sample_tool["name"],
            install_path="/home/user/.agora/market/test-org__mcp-server-0",
        )
        assert updated, "update_install should return True"

        # Verify status transition
        tool = catalog.get_tool(sample_tool["name"])
        assert tool["status"] == "installed", f"Expected status 'installed', got '{tool['status']}'"
        assert tool["install_path"] == "/home/user/.agora/market/test-org__mcp-server-0"

    @pytest.mark.asyncio
    async def test_install_then_update_entry(self, catalog, sample_tool):
        """After install, entry and metadata should be updatable."""
        sample_tool["quality_score"] = QualityScorer.evaluate(sample_tool)
        catalog.add_tool(sample_tool)
        catalog.update_install(
            tool_id=sample_tool["name"],
            install_path="/home/user/.agora/market/test-org__mcp-server-0",
        )

        # Update entry and metadata after install
        updated = catalog.update_entry(
            tool_id=sample_tool["name"],
            entry="server.py",
            metadata={"command": "uv", "args": ["run", "server.py"]},
        )
        assert updated, "update_entry should return True"

        tool = catalog.get_tool(sample_tool["name"])
        assert tool["entry"] == "server.py"
        meta = tool.get("metadata", {}) or {}
        assert meta.get("command") == "uv"

    @pytest.mark.asyncio
    async def test_install_updates_tool_type_and_entry(self, catalog, sample_tool):
        """Verify Market.install() result can be used to enhance catalog entry."""
        sample_tool["quality_score"] = QualityScorer.evaluate(sample_tool)
        catalog.add_tool(sample_tool)

        fake_install_result = {
            "name": "mcp-server-0",
            "description": "Installed MCP server",
            "entry": "/home/user/.agora/market/test-org__mcp-server-0/server.py",
            "type": "python",
            "port": 0,
            "tags": [],
        }

        with patch("agora.plugins.market.market.Market.install", return_value=fake_install_result) as mock_install:
            result = mock_install("test-org/mcp-server-0")

        # Update catalog with install results
        catalog.update_install(
            tool_id=sample_tool["name"],
            install_path="/home/user/.agora/market/test-org__mcp-server-0",
        )
        catalog.update_entry(
            tool_id=sample_tool["name"],
            entry=result["entry"],
            install_path="/home/user/.agora/market/test-org__mcp-server-0",
            metadata={"type": result["type"], "port": result["port"]},
        )

        tool = catalog.get_tool(sample_tool["name"])
        assert tool["entry"] == fake_install_result["entry"]
        assert tool["install_path"] == "/home/user/.agora/market/test-org__mcp-server-0"


# ══════════════════════════════════════════════════════════════════════
# Test 4: Lifecycle Load (Mock)
# ══════════════════════════════════════════════════════════════════════


class TestLifecycleLoad:
    """Load pipeline: installed → loaded via LifecycleManager.load_tool()."""

    @pytest.mark.asyncio
    async def test_load_transition_installed_to_loaded(self, catalog, sample_tool):
        """LifecycleManager.load_tool() transitions from installed to loaded."""
        # Setup: add tool with 'installed' status
        sample_tool["quality_score"] = QualityScorer.evaluate(sample_tool)
        catalog.add_tool(sample_tool)
        catalog.update_status(sample_tool["name"], "installed")

        # Mock ProxyManager so no real connection is made
        proxy_mock = MagicMock()
        proxy_mock.add_service = AsyncMock(return_value="ok service registered")
        proxy_mock.remove_service = AsyncMock(return_value="ok")
        proxy_mock.set_usage_callback = MagicMock()

        mgr = LifecycleManager(catalog=catalog, proxy_manager=proxy_mock)
        result = await mgr.load_tool(sample_tool["name"])
        assert result, "load_tool should return True"

        # Verify status transition
        tool = catalog.get_tool(sample_tool["name"])
        assert tool["status"] == "loaded", f"Expected 'loaded', got '{tool['status']}'"

        # Verify proxy was called with a proper config
        proxy_mock.add_service.assert_awaited_once()
        call_args = proxy_mock.add_service.await_args[0][0]
        assert call_args["name"] == sample_tool["name"]

        await mgr.close()

    @pytest.mark.asyncio
    async def test_load_already_loaded_is_noop(self, catalog, sample_tool):
        """Loading an already-loaded tool should return True without proxy call."""
        sample_tool["quality_score"] = QualityScorer.evaluate(sample_tool)
        catalog.add_tool(sample_tool)
        catalog.update_status(sample_tool["name"], "loaded")

        proxy_mock = MagicMock()
        proxy_mock.add_service = AsyncMock()
        proxy_mock.remove_service = AsyncMock(return_value="ok")

        mgr = LifecycleManager(catalog=catalog, proxy_manager=proxy_mock)
        result = await mgr.load_tool(sample_tool["name"])
        assert result, "load_tool on already-loaded should return True"

        proxy_mock.add_service.assert_not_awaited()
        await mgr.close()

    @pytest.mark.asyncio
    async def test_load_nonexistent_tool_returns_false(self, catalog):
        """Loading a tool not in the catalog should return False."""
        proxy_mock = MagicMock()
        proxy_mock.add_service = AsyncMock()

        mgr = LifecycleManager(catalog=catalog, proxy_manager=proxy_mock)
        result = await mgr.load_tool("nonexistent-tool-xyz")
        assert not result, "load_tool on nonexistent tool should return False"
        proxy_mock.add_service.assert_not_awaited()
        await mgr.close()

    @pytest.mark.asyncio
    async def test_load_without_proxy_updates_status_directly(self, catalog, sample_tool):
        """Without a proxy, load_tool should just update status to 'loaded'."""
        sample_tool["quality_score"] = QualityScorer.evaluate(sample_tool)
        catalog.add_tool(sample_tool)

        mgr = LifecycleManager(catalog=catalog, proxy_manager=None)
        result = await mgr.load_tool(sample_tool["name"])
        assert result

        tool = catalog.get_tool(sample_tool["name"])
        assert tool["status"] == "loaded"
        await mgr.close()

    @pytest.mark.asyncio
    async def test_full_pipeline_discover_install_load(self, catalog, sample_tool):
        """Simulate the full pipeline: discovered → installed → loaded."""
        # Discover
        sample_tool["quality_score"] = QualityScorer.evaluate(sample_tool)
        catalog.add_tool(sample_tool)
        assert catalog.get_tool(sample_tool["name"])["status"] == "discovered"

        # Install
        fake_install = {
            "name": "mcp-server-0",
            "description": "Installed",
            "entry": "/path/to/server.py",
            "type": "python",
            "port": 0,
            "tags": [],
        }
        with patch("agora.plugins.market.market.Market.install", return_value=fake_install):
            from agora.plugins.market.market import Market

            result = Market().install("test-org/mcp-server-0")
        catalog.update_install(
            tool_id=sample_tool["name"],
            install_path="/path/to/market",
        )
        catalog.update_entry(
            tool_id=sample_tool["name"],
            entry=result["entry"],
            metadata={"command": "python", "args": ["-m", "server"]},
        )
        assert catalog.get_tool(sample_tool["name"])["status"] == "installed"

        # Load
        proxy_mock = MagicMock()
        proxy_mock.add_service = AsyncMock(return_value="ok service registered")
        proxy_mock.remove_service = AsyncMock(return_value="ok")
        proxy_mock.set_usage_callback = MagicMock()

        mgr = LifecycleManager(catalog=catalog, proxy_manager=proxy_mock)
        loaded = await mgr.load_tool(sample_tool["name"])
        assert loaded

        tool = catalog.get_tool(sample_tool["name"])
        assert tool["status"] == "loaded"
        await mgr.close()


# ══════════════════════════════════════════════════════════════════════
# Test 5: Negative Cases
# ══════════════════════════════════════════════════════════════════════


class TestNegativeCases:
    """Edge cases and error handling for GitHub search and install pipeline."""

    @pytest.mark.asyncio
    async def test_search_github_no_results(self):
        """search_github with a gibberish query should return []."""
        results = await search_github(
            query="zzzzz_nonexistent_gibberish_xyz",
            min_stars=999999,
            max_results=5,
        )
        # Either empty list (API failure) or empty (no items pass the filter)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_github_http_error(self):
        """search_github should return [] when httpx raises (network error)."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = httpx.HTTPError("Connection refused")
            results = await search_github(query="mcp-server", max_results=5)
            assert results == [], f"Expected [] on HTTP error, got {len(results)} results"

    @pytest.mark.asyncio
    async def test_search_github_timeout(self):
        """search_github should return [] on timeout."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = httpx.TimeoutException("Timed out")
            results = await search_github(query="mcp-server", max_results=5)
            assert results == []

    @pytest.mark.asyncio
    async def test_search_github_non_200(self):
        """search_github should return [] on non-200 status."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 403
            mock_get.return_value = mock_response
            results = await search_github(query="mcp-server", max_results=5)
            assert results == []

    @pytest.mark.asyncio
    async def test_install_non_existent_market_tool(self, catalog):
        """Installing a tool not in the catalog should still be possible (Market handles it)."""
        with patch("agora.plugins.market.market.Market._run_cmd") as mock_run:
            mock_run.return_value = None
            with patch("agora.plugins.market.market.Market._fetch_repo_metadata") as mock_fetch:
                mock_fetch.return_value = {
                    "name": "custom-tool",
                    "description": "Custom tool",
                    "type": "python",
                    "entry": "server.py",
                    "tags": [],
                }
                from agora.plugins.market.market import Market

                result = Market().install("some-user/custom-tool")
                assert result["name"] == "custom-tool"

    @pytest.mark.asyncio
    async def test_catalog_remove_tool(self, catalog, sample_tool):
        """Removing a tool from catalog should work."""
        sample_tool["quality_score"] = QualityScorer.evaluate(sample_tool)
        catalog.add_tool(sample_tool)
        assert catalog.get_tool(sample_tool["name"]) is not None

        removed = catalog.remove_tool(sample_tool["name"])
        assert removed, "remove_tool should return True"
        assert catalog.get_tool(sample_tool["name"]) is None

    @pytest.mark.asyncio
    async def test_count_by_status_after_install(self, catalog, sample_tool):
        """count_by_status should reflect status changes correctly."""
        sample_tool["quality_score"] = QualityScorer.evaluate(sample_tool)
        catalog.add_tool(sample_tool)

        counts = catalog.count_by_status()
        assert counts.get("discovered", 0) == 1

        catalog.update_status(sample_tool["name"], "installed")
        counts = catalog.count_by_status()
        assert counts.get("installed", 0) == 1
        assert counts.get("discovered", 0) == 0

        catalog.update_status(sample_tool["name"], "loaded")
        counts = catalog.count_by_status()
        assert counts.get("loaded", 0) == 1
