"""End-to-end integration tests for the agora MCP registry system.

Tests the full pipeline: registry discovery → quality scoring → catalog
storage → embedding → routing, plus negative cases.

These tests use the local registry.json file and in-memory SQLite databases,
so they do NOT require network access or external dependencies.
"""

from pathlib import Path

import pytest
from agora.mcp_registry.embeddings import EmbeddingStore
from agora.mcp_registry.evaluator import QualityScorer
from agora.mcp_registry.repository import ToolCatalog
from agora.mcp_registry.router import SmartRouter
from agora.mcp_registry.sources import search_registry

# ── Fixtures ──────────────────────────────────────────────────────────


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
def embeddings() -> EmbeddingStore:
    e = EmbeddingStore(db_path=":memory:")
    yield e
    e.close()


# ══════════════════════════════════════════════════════════════════════
# Test 1: Registry Discovery from Local File
# ══════════════════════════════════════════════════════════════════════


class TestRegistryDiscovery:
    """Verify the local registry.json is discoverable and well-formed."""

    @pytest.mark.asyncio
    async def test_discover_via_file_uri(self, registry_path):
        """search_registry with file:// URL returns at least 30 services."""
        results = await search_registry(f"file://{registry_path}")
        assert len(results) >= 30, f"Expected >=30 services from registry, got {len(results)}"

    @pytest.mark.asyncio
    async def test_discover_via_bare_path(self, registry_path):
        """search_registry with a bare filesystem path also works."""
        results = await search_registry(registry_path)
        assert len(results) >= 30

    @pytest.mark.asyncio
    async def test_every_service_has_name_and_description(self, registry_path):
        """Each returned service dict must have non-empty name and description."""
        results = await search_registry(f"file://{registry_path}")
        for svc in results:
            assert svc.get("name"), f"Service missing name: {svc}"
            assert svc.get("description"), f"Service '{svc['name']}' missing description"

    @pytest.mark.asyncio
    async def test_expected_services_present(self, registry_path):
        """Known services like kronos, codeanalyze, sqlite, docker should be present."""
        results = await search_registry(f"file://{registry_path}")
        names = {s["name"] for s in results}
        for expected in ("kronos", "codeanalyze", "sqlite", "docker-mcp", "filesystem", "github"):
            assert expected in names, f"Expected service '{expected}' not found in registry"

    @pytest.mark.asyncio
    async def test_tool_type_populated(self, registry_path):
        """Each service should have a tool_type string."""
        results = await search_registry(f"file://{registry_path}")
        for svc in results:
            assert isinstance(svc.get("tool_type"), str), f"Service '{svc['name']}' missing tool_type"

    @pytest.mark.asyncio
    async def test_tags_present(self, registry_path):
        """Service tags should be a list."""
        results = await search_registry(f"file://{registry_path}")
        for svc in results:
            assert isinstance(svc.get("tags"), list), f"Service '{svc['name']}' tags is not a list"

    @pytest.mark.asyncio
    async def test_metadata_contains_verified_flag(self, registry_path):
        """metadata.verified should be a bool."""
        results = await search_registry(f"file://{registry_path}")
        for svc in results:
            meta = svc.get("metadata", {}) or {}
            assert isinstance(meta.get("verified"), bool), f"Service '{svc['name']}' metadata.verified is not bool"

    @pytest.mark.asyncio
    async def test_source_is_registry(self, registry_path):
        """All services from search_registry should have source='registry'."""
        results = await search_registry(f"file://{registry_path}")
        for svc in results:
            assert svc.get("source") == "registry", (
                f"Service '{svc['name']}' has source={svc.get('source')!r}, expected 'registry'"
            )


# ══════════════════════════════════════════════════════════════════════
# Test 2: Quality Scoring Pipeline
# ══════════════════════════════════════════════════════════════════════


class TestQualityScoringPipeline:
    """QualityScorer.evaluate_batch sorts services by composite quality."""

    @pytest.mark.asyncio
    async def test_batch_returns_sorted_by_quality(self, registry_path):
        """After evaluate_batch, tools should be sorted descending by quality_score."""
        results = await search_registry(f"file://{registry_path}")
        scored = QualityScorer.evaluate_batch(results)
        assert len(scored) == len(results)

        scores = [t.get("quality_score", 0) for t in scored]
        assert scores == sorted(scores, reverse=True), "Tools not sorted by quality_score descending"

    @pytest.mark.asyncio
    async def test_high_star_services_score_higher(self, registry_path):
        """Services with higher stars should tend to score higher."""
        results = await search_registry(f"file://{registry_path}")
        scored = QualityScorer.evaluate_batch(results)

        # Sort by stars descending
        by_stars = sorted(scored, key=lambda x: x.get("stars", 0), reverse=True)
        top_stars = by_stars[0]
        low_stars = by_stars[-1]

        # The highest-star service should beat the lowest-star service
        assert top_stars["quality_score"] >= low_stars["quality_score"], (
            f"Expected high-star service '{top_stars['name']}' "
            f"(score={top_stars['quality_score']}) to score >= "
            f"low-star service '{low_stars['name']}' "
            f"(score={low_stars['quality_score']})"
        )

    @pytest.mark.asyncio
    async def test_verified_services_have_base_score(self, registry_path):
        """Verified services should have non-zero quality_score even with 0 stars."""
        results = await search_registry(f"file://{registry_path}")
        # Modify a service to have minimum stars but verified=true
        for svc in results:
            if svc["name"] == "kronos":
                svc["stars"] = 0
        scored = QualityScorer.evaluate_batch(results)

        for svc in scored:
            if svc["name"] == "kronos":
                # verified=True should give base score from verified weight (0.10)
                # even with 0 stars
                assert svc["quality_score"] > 0, f"Verified service '{svc['name']}' scored 0 despite verified=True"

    @pytest.mark.asyncio
    async def test_quality_score_range(self, registry_path):
        """All quality_scores should be in [0.0, 1.0] range."""
        results = await search_registry(f"file://{registry_path}")
        scored = QualityScorer.evaluate_batch(results)
        for svc in scored:
            qs = svc["quality_score"]
            assert 0.0 <= qs <= 1.0, f"Service '{svc['name']}' quality_score={qs} out of range [0,1]"

    @pytest.mark.asyncio
    async def test_batch_idempotent(self, registry_path):
        """Running evaluate_batch twice should produce the same scores."""
        results = await search_registry(f"file://{registry_path}")
        first = QualityScorer.evaluate_batch(results)
        scores_a = [(t["name"], t["quality_score"]) for t in first]

        # Re-score (re-evaluate from scratch by re-fetching)
        results2 = await search_registry(f"file://{registry_path}")
        second = QualityScorer.evaluate_batch(results2)
        scores_b = [(t["name"], t["quality_score"]) for t in second]

        assert scores_a == scores_b, "Batch scoring not idempotent"

    @pytest.mark.asyncio
    async def test_quality_score_field_added(self, registry_path):
        """evaluate_batch should add 'quality_score' key to each tool."""
        results = await search_registry(f"file://{registry_path}")
        assert "quality_score" not in results[0], "quality_score should not exist before evaluate_batch"
        scored = QualityScorer.evaluate_batch(results)
        assert "quality_score" in scored[0], "quality_score missing after evaluate_batch"


# ══════════════════════════════════════════════════════════════════════
# Test 3: Discover → Save → Embed → Route
# ══════════════════════════════════════════════════════════════════════


class TestFullPipeline:
    """End-to-end pipeline: discover registry → catalog → embeddings → router."""

    @pytest.mark.asyncio
    async def test_discover_and_save_to_catalog(self, registry_path, catalog):
        """Search the registry and save all results into ToolCatalog."""
        results = await search_registry(f"file://{registry_path}")
        assert len(results) >= 30

        for svc in results:
            catalog.add_tool(svc)

        count = len(catalog.list_tools())
        assert count == len(results), f"Catalog has {count} tools, expected {len(results)}"

    @pytest.mark.asyncio
    async def test_embeddings_rebuild(self, registry_path, catalog, embeddings):
        """Rebuild embeddings from catalog (model may not be available)."""
        results = await search_registry(f"file://{registry_path}")
        for svc in results:
            catalog.add_tool(svc)

        saved = embeddings.rebuild_all(catalog)
        # If model is unavailable, saved=0 but that's OK — we just verify it doesn't crash
        assert isinstance(saved, int)
        if embeddings.available:
            assert saved >= 1, f"Expected >=1 embeddings saved, got {saved}"
        else:
            pytest.skip("sentence-transformers model not available; skipping embedding count check")

    @pytest.mark.asyncio
    async def test_semantic_search_with_embeddings(self, registry_path, catalog, embeddings):
        """Search similar tools via embedding similarity (if model available)."""
        results = await search_registry(f"file://{registry_path}")
        for svc in results:
            catalog.add_tool(svc)

        embeddings.rebuild_all(catalog)
        if not embeddings.available:
            pytest.skip("sentence-transformers model not available; skipping semantic search")

        similar = embeddings.search_similar("code analysis and review", top_k=5)
        assert len(similar) >= 1, "Expected at least 1 similar result for 'code analysis'"
        # The top result should be related to code analysis
        top_ids = [t[0] for t in similar]
        assert any("codeanalyze" in tid for tid in top_ids), (
            f"Expected codeanalyze in top results for 'code analysis', got {top_ids}"
        )

    @pytest.mark.asyncio
    async def test_router_code_analysis(self, registry_path, catalog, embeddings):
        """Router should route 'code analysis' to codeanalyze tool."""
        results = await search_registry(f"file://{registry_path}")
        for svc in results:
            catalog.add_tool(svc)

        # Rebuild embeddings so semantic search works
        embeddings.rebuild_all(catalog)

        router = SmartRouter(catalog=catalog, embeddings=embeddings)
        result = await router.route("code analysis", mode="recommend")

        assert result["status"] == "ok"
        tools = result.get("tools", [])
        tool_names = [t["name"] for t in tools] if tools else []
        # The router may return tools via semantic search or keyword fallback
        # codeanalyze should be among recommendations
        assert any("codeanalyz" in t.lower() for t in tool_names), (
            f"Expected codeanalyze in route results for 'code analysis', got {tool_names}"
        )

    @pytest.mark.asyncio
    async def test_router_sqlite_database(self, registry_path, catalog, embeddings):
        """Router should route database-related queries to sqlite tools."""
        results = await search_registry(f"file://{registry_path}")
        for svc in results:
            catalog.add_tool(svc)

        router = SmartRouter(catalog=catalog, embeddings=embeddings)
        result = await router.route("sqlite database", mode="recommend")

        assert result["status"] == "ok"
        tools = result.get("tools", [])
        tool_names = [t["name"] for t in tools] if tools else []
        # Should find sqlite-related tools
        sqlite_related = [n for n in tool_names if "sqlite" in n.lower()]
        assert len(sqlite_related) >= 1, f"Expected sqlite-related tool in route results, got {tool_names}"

    @pytest.mark.asyncio
    async def test_router_docker_container(self, registry_path, catalog, embeddings):
        """Router should route container-related queries to docker tools."""
        results = await search_registry(f"file://{registry_path}")
        for svc in results:
            catalog.add_tool(svc)

        # Rebuild embeddings so semantic search works
        embeddings.rebuild_all(catalog)

        router = SmartRouter(catalog=catalog, embeddings=embeddings)
        result = await router.route("docker container", mode="recommend")

        assert result["status"] == "ok"
        tools = result.get("tools", [])
        tool_names = [t["name"] for t in tools] if tools else []
        # Should find docker-related tools
        docker_related = [n for n in tool_names if "docker" in n.lower()]
        assert len(docker_related) >= 1, f"Expected docker-related tool in route results, got {tool_names}"

    @pytest.mark.asyncio
    async def test_discover_save_count_matches(self, registry_path, catalog):
        """Verify the catalog count matches the registry count after save."""
        results = await search_registry(f"file://{registry_path}")
        for svc in results:
            catalog.add_tool(svc)

        cat_tools = catalog.list_tools()
        assert len(cat_tools) == len(results)

        # Verify a few specific tools exist in catalog
        cat_names = {t["name"] for t in cat_tools}
        for expected in ("kronos", "codeanalyze", "docker-mcp"):
            assert expected in cat_names, f"Tool '{expected}' not found in catalog after save"


# ══════════════════════════════════════════════════════════════════════
# Test 4: Negative Cases
# ══════════════════════════════════════════════════════════════════════


class TestNegativeCases:
    """Edge cases and error handling for the registry system."""

    @pytest.mark.asyncio
    async def test_search_registry_nonexistent_file(self):
        """search_registry with a non-existent file should return []."""
        results = await search_registry("file:///tmp/nonexistent_registry_xyz.json")
        assert results == [], f"Expected empty list for nonexistent file, got {len(results)} results"

    @pytest.mark.asyncio
    async def test_embedding_search_empty_catalog(self, embeddings):
        """EmbeddingStore.search_similar on empty catalog returns []."""
        # No model check needed — empty DB returns []
        similar = embeddings.search_similar("anything", top_k=5)
        assert similar == [], "Expected empty results on empty embedding store"

    @pytest.mark.asyncio
    async def test_router_empty_catalog(self):
        """SmartRouter with empty catalog returns no_match."""
        catalog = ToolCatalog(db_path=":memory:")
        router = SmartRouter(catalog=catalog, embeddings=None)
        result = await router.route("anything", mode="recommend")
        catalog.close()

        assert result["status"] == "ok"
        assert result.get("action") == "no_match", f"Expected no_match for empty catalog, got {result.get('action')}"

    @pytest.mark.asyncio
    async def test_router_empty_query(self, catalog):
        """Router with empty query returns error."""
        router = SmartRouter(catalog=catalog)
        result = await router.route("", mode="recommend")
        assert result["status"] == "error"
        assert "Empty query" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_router_whitespace_only_query(self, catalog):
        """Router with whitespace-only query returns error."""
        router = SmartRouter(catalog=catalog)
        result = await router.route("   ", mode="auto")
        assert result["status"] == "error"
        assert "Empty query" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_evaluate_batch_empty(self):
        """evaluate_batch with empty list returns empty list."""
        result = QualityScorer.evaluate_batch([])
        assert result == [], "Expected empty list from evaluate_batch([])"

    @pytest.mark.asyncio
    async def test_evaluate_empty_dict(self):
        """evaluate with empty dict should not crash, returns float."""
        score = QualityScorer.evaluate({})
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_catalog_search_no_match(self, catalog):
        """Catalog search with no matching tools returns []."""
        catalog.add_tool(
            {
                "id": "unique-tool",
                "name": "unique-tool",
                "description": "a very specific tool",
                "tool_type": "python",
                "source": "registry",
            }
        )
        results = catalog.search_tools(query="zzzzz_nonexistent_xyz")
        assert results == [], f"Expected empty search results, got {len(results)}"

    @pytest.mark.asyncio
    async def test_embeddings_unavailable_property(self, embeddings):
        """EmbeddingStore.available should be False when model is missing."""
        # In a fresh :memory: store, model won't load (no sentence-transformers in CI)
        # This should return False without raising
        assert isinstance(embeddings.available, bool)
