"""End-to-end tests for SmartRouter LLM integration.

Tests prompt building, mock LLM selection, circuit breaker fallback,
recommend mode, optional real Ollama, and edge cases.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from agora.mcp_registry.repository import ToolCatalog
from agora.mcp_registry.router import SmartRouter

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_tool(
    name: str,
    description: str = "",
    tags: list[str] | None = None,
    quality_score: float = 0.5,
    status: str = "loaded",
) -> dict:
    """Create a minimal tool dict for tests."""
    return {
        "id": name,
        "name": name,
        "description": description,
        "tags": tags or [],
        "quality_score": quality_score,
        "status": status,
    }


CANDIDATES = [
    _make_tool("codeanalyze", "Analyze Python code quality", ["python", "static-analysis"], 0.95),
    _make_tool("dbquery", "Query SQL databases", ["sql", "database"], 0.80),
    _make_tool("dockerps", "List Docker containers", ["docker", "containers"], 0.70, "discovered"),
    _make_tool("deploy", "Deploy services to kubernetes", ["k8s", "deploy"], 0.60, "discovered"),
    _make_tool("monitor", "Monitor system metrics", ["metrics", "monitoring"], 0.50),
]

CANDIDATES_SHORT = CANDIDATES[:3]


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def catalog():
    """Return an empty ToolCatalog backed by :memory:."""
    cat = ToolCatalog(db_path=":memory:")
    # Seed some tools so search_tools returns results
    for t in CANDIDATES:
        cat.add_tool(t)
    return cat


@pytest.fixture
def router(catalog):
    """SmartRouter with a populated catalog but no LLM / embeddings."""
    return SmartRouter(catalog=catalog)


@pytest.fixture
def mock_llm():
    """Create a mock LLM client that returns a valid tool name."""
    client = MagicMock()
    client.generate = AsyncMock(return_value="codeanalyze")
    return client


@pytest.fixture
def router_with_llm(router, mock_llm):
    """SmartRouter with its _llm slot pre-set to a working mock."""
    router._llm = mock_llm
    return router


# ═══════════════════════════════════════════════════════════════════════════════
# Test 1: Prompt Building
# ═══════════════════════════════════════════════════════════════════════════════


class TestPromptBuilding:
    """_build_selection_prompt() output verification."""

    def test_prompt_contains_tool_names_and_descriptions(self, router):
        """Prompt should list every candidate with name and description."""
        prompt = router._build_selection_prompt("analyze my code", CANDIDATES[:3])
        assert "codeanalyze" in prompt
        assert "dbquery" in prompt
        assert "dockerps" in prompt
        assert "Analyze Python code quality" in prompt
        assert "Query SQL databases" in prompt
        assert "List Docker containers" in prompt

    def test_prompt_contains_user_query(self, router):
        """Prompt should embed the original user request."""
        prompt = router._build_selection_prompt("deploy to production", CANDIDATES_SHORT)
        assert "deploy to production" in prompt or "deploy to production" in prompt

    def test_prompt_includes_quality_scores(self, router):
        """Prompt should show quality scores for ranking context."""
        prompt = router._build_selection_prompt("test", CANDIDATES[:2])
        assert "0.95" in prompt
        assert "0.80" in prompt

    def test_prompt_includes_tags(self, router):
        """Prompt should include up to 5 tags per tool."""
        tool = _make_tool("multitag", tags=["tag_a", "tag_b", "tag_c", "tag_d", "tag_e", "tag_f"])
        prompt = router._build_selection_prompt("test", [tool])
        assert "tag_a, tag_b, tag_c, tag_d, tag_e" in prompt
        assert "tag_f" not in prompt  # only first 5 tags

    def test_prompt_includes_selection_instruction(self, router):
        """Prompt should ask LLM to respond with ONLY the tool name."""
        prompt = router._build_selection_prompt("test", CANDIDATES_SHORT)
        assert "Respond with ONLY the tool name" in prompt

    def test_prompt_handles_none_tool_name(self, router):
        """Prompt should include 'none' option when no tool matches."""
        prompt = router._build_selection_prompt("test", CANDIDATES_SHORT)
        assert "none" in prompt

    def test_prompt_with_single_tool(self, router):
        """Single candidate should still produce valid prompt."""
        prompt = router._build_selection_prompt("analyze", [CANDIDATES[0]])
        assert prompt.count("codeanalyze") == 1

    def test_prompt_with_no_candidates(self, router):
        """Empty candidates list should produce minimal prompt."""
        prompt = router._build_selection_prompt("hello", [])
        assert "Available tools" in prompt
        assert "Respond with ONLY the tool name" in prompt

    def test_prompt_max_candidates_respected(self, router):
        """At most 10 candidates should be listed."""
        many = [_make_tool(f"tool_{i}", quality_score=0.5) for i in range(15)]
        prompt = router._build_selection_prompt("test", many)
        # Count numbered entries — should be 10
        [l for l in prompt.splitlines() if l.strip().startswith(tuple(str(i) + "." for i in range(1, 11)))]  # noqa: E741
        # A simpler check: "Available tools" section should have at most 10 entries
        entries = [
            l
            for l in prompt.splitlines()  # noqa: E741
            if l.strip().startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "10."))
        ]
        assert len(entries) <= 10


# ═══════════════════════════════════════════════════════════════════════════════
# Test 2: LLM Tool Selection (Mocked)
# ═══════════════════════════════════════════════════════════════════════════════


class TestLLMSelectTool:
    """_llm_select_tool() with a mock LLM client."""

    @pytest.mark.asyncio
    async def test_selects_correct_tool(self, router_with_llm):
        """Happy path — LLM returns a valid tool name."""
        result = await router_with_llm._llm_select_tool("analyze code", CANDIDATES)
        assert result["status"] == "ok"
        assert result["mode"] == "llm_selected"
        assert result["tool"]["name"] == "codeanalyze"
        assert result["action"] in ("call", "load_and_call")

    @pytest.mark.asyncio
    async def test_tool_not_in_candidates(self, router_with_llm):
        """LLM returns a name not in the candidates list → mode llm_no_match."""
        router_with_llm._llm.generate = AsyncMock(return_value="nonexistent_tool")
        result = await router_with_llm._llm_select_tool("analyze code", CANDIDATES)
        assert result["status"] == "ok"
        assert result["mode"] == "llm_no_match"
        assert "tool" not in result  # no single tool selected
        assert "tools" in result  # fallback list

    @pytest.mark.asyncio
    async def test_llm_returns_none(self, router_with_llm):
        """LLM responds with 'none' → mode llm_no_match."""
        router_with_llm._llm.generate = AsyncMock(return_value="none")
        result = await router_with_llm._llm_select_tool("analyze code", CANDIDATES)
        assert result["status"] == "ok"
        assert result["mode"] == "llm_no_match"
        assert len(result["tools"]) <= 5

    @pytest.mark.asyncio
    async def test_llm_raises_exception(self, router_with_llm):
        """LLM.generate() raises an error → fallback to quality sort."""
        router_with_llm._llm.generate = AsyncMock(side_effect=RuntimeError("LLM timeout"))
        result = await router_with_llm._llm_select_tool("analyze code", CANDIDATES)
        assert result["status"] == "ok"
        assert result["mode"] == "llm_fallback"
        assert len(result["tools"]) <= 5

    @pytest.mark.asyncio
    async def test_case_insensitive_matching(self, router_with_llm):
        """Tool name matching should be case-insensitive."""
        router_with_llm._llm.generate = AsyncMock(return_value="CodeAnalyze")
        result = await router_with_llm._llm_select_tool("analyze code", CANDIDATES)
        assert result["status"] == "ok"
        assert result["mode"] == "llm_selected"
        assert result["tool"]["name"] == "codeanalyze"

    @pytest.mark.asyncio
    async def test_partial_name_matching(self, router_with_llm):
        """LLM returns a substring that matches a tool name."""
        router_with_llm._llm.generate = AsyncMock(return_value="code")
        result = await router_with_llm._llm_select_tool("analyze code", CANDIDATES)
        assert result["status"] == "ok"
        assert result["mode"] == "llm_selected"
        assert result["tool"]["name"] == "codeanalyze"

    @pytest.mark.asyncio
    async def test_strips_whitespace_and_punctuation(self, router_with_llm):
        """LLM response should be stripped and lowered before matching."""
        router_with_llm._llm.generate = AsyncMock(return_value="  dbquery  ")
        result = await router_with_llm._llm_select_tool("query database", CANDIDATES)
        assert result["status"] == "ok"
        assert result["mode"] == "llm_selected"
        assert result["tool"]["name"] == "dbquery"

    @pytest.mark.asyncio
    async def test_action_loaded_tool_is_call(self, router_with_llm):
        """A tool with status 'loaded' should have action 'call'."""
        router_with_llm._llm.generate = AsyncMock(return_value="monitor")
        result = await router_with_llm._llm_select_tool("monitor system", CANDIDATES)
        assert result["status"] == "ok"
        assert result["tool"]["name"] == "monitor"
        assert result["action"] == "call"

    @pytest.mark.asyncio
    async def test_action_unloaded_tool_is_load_and_call(self, router_with_llm):
        """A tool with status != 'loaded' should have action 'load_and_call'."""
        router_with_llm._llm.generate = AsyncMock(return_value="dockerps")
        result = await router_with_llm._llm_select_tool("list containers", CANDIDATES)
        assert result["status"] == "ok"
        assert result["tool"]["name"] == "dockerps"
        assert result["action"] == "load_and_call"


# ═══════════════════════════════════════════════════════════════════════════════
# Test 3: LLM Circuit Breaker Integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestLLMCircuitBreaker:
    """Fallback behavior when LLM is unreliable."""

    @pytest.mark.asyncio
    async def test_falls_back_on_llm_exception(self, catalog):
        """When LLM.generate() raises, _route_recommend returns quality-sorted fallback."""
        router = SmartRouter(catalog=catalog)
        router._llm = MagicMock()
        router._llm.generate = AsyncMock(side_effect=ConnectionError("LLM unreachable"))

        result = await router._route_recommend("codeanalyze")
        assert result["status"] == "ok"
        assert result["mode"] == "llm_fallback"
        assert len(result["tools"]) <= 5

    @pytest.mark.asyncio
    async def test_fallback_tools_are_quality_sorted(self, catalog):
        """Fallback tools should be ordered by quality_score descending."""
        router = SmartRouter(catalog=catalog)
        router._llm = MagicMock()
        router._llm.generate = AsyncMock(side_effect=RuntimeError("fail"))

        result = await router._route_recommend("codeanalyze")
        tools = result["tools"]
        if len(tools) > 1:
            scores = [t.get("quality_score", 0) for t in tools]
            assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_llm_unavailable_no_crash(self, catalog):
        """When LLM was never initialized, _route_recommend doesn't crash."""
        router = SmartRouter(catalog=catalog)
        # Ensure _init_llm returns None
        router._init_llm = MagicMock(return_value=None)

        result = await router._route_recommend("analyze code")
        assert result["status"] == "ok"
        assert result["mode"] == "recommend"
        assert len(result["tools"]) <= 5

    @pytest.mark.asyncio
    async def test_llm_unavailable_uses_keyword_fallback(self, catalog):
        """When LLM and embeddings are unavailable, keyword search is used as fallback."""
        router = SmartRouter(catalog=catalog)

        # Disable LLM and embeddings
        router._init_llm = MagicMock(return_value=None)
        router._embeddings = None  # No embeddings → _semantic_search returns []

        result = await router._route_recommend("codeanalyze")
        assert result["status"] == "ok"
        assert len(result["tools"]) > 0
        # Keyword search should find "codeanalyze" by name
        assert any(t["name"] == "codeanalyze" for t in result["tools"])

    @pytest.mark.asyncio
    async def test_no_candidates_returns_no_match(self, router):
        """When no tools match at all, return no_match action."""
        router._catalog.search_tools = MagicMock(return_value=[])
        result = await router._route_recommend("zzzz_tool_does_not_exist")
        assert result["status"] == "ok"
        assert result["action"] == "no_match"
        assert result["tools"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# Test 4: Mode "recommend" with LLM
# ═══════════════════════════════════════════════════════════════════════════════


class TestRouteRecommend:
    """route(query, mode='recommend') end-to-end."""

    @pytest.mark.asyncio
    async def test_recommend_mode_with_llm(self, router_with_llm):
        """mode='recommend' with LLM should return llm_selected result."""
        result = await router_with_llm.route("analyze Python code", mode="recommend")
        assert result["status"] == "ok"
        assert result["mode"] == "llm_selected"
        assert result["tool"]["name"] == "codeanalyze"

    @pytest.mark.asyncio
    async def test_recommend_mode_without_llm(self, catalog):
        """mode='recommend' without LLM falls back to quality-sorted tools."""
        router = SmartRouter(catalog=catalog)
        result = await router.route("analyze code", mode="recommend")
        assert result["status"] == "ok"
        assert result["mode"] == "recommend"
        assert len(result["tools"]) <= 5

    @pytest.mark.asyncio
    async def test_recommend_mode_llm_fails_fallback(self, catalog):
        """mode='recommend' with failing LLM falls back gracefully."""
        router = SmartRouter(catalog=catalog)
        router._llm = MagicMock()
        router._llm.generate = AsyncMock(side_effect=TimeoutError("LLM timeout"))

        result = await router.route("codeanalyze", mode="recommend")
        assert result["status"] == "ok"
        assert result["mode"] == "llm_fallback"
        assert len(result["tools"]) <= 5

    @pytest.mark.asyncio
    async def test_recommend_no_tools_found(self, router):
        """mode='recommend' with no matching tools returns no_match."""
        router._catalog.search_tools = MagicMock(return_value=[])
        result = await router.route("zzzz_unknown_tool", mode="recommend")
        assert result["status"] == "ok"
        assert result["action"] == "no_match"
        assert result["tools"] == []

    @pytest.mark.asyncio
    async def test_recommend_llm_init_failure(self, catalog):
        """LLM init failure should not prevent recommend mode from working."""
        router = SmartRouter(catalog=catalog)
        # Simulate init that raises
        router._init_llm = MagicMock(side_effect=ImportError("minerva not found"))
        result = await router.route("analyze code", mode="recommend")
        assert result["status"] == "ok"
        assert len(result["tools"]) <= 5


# ═══════════════════════════════════════════════════════════════════════════════
# Test 5: Real LLM (Optional — skip if Ollama unavailable)
# ═══════════════════════════════════════════════════════════════════════════════


def _real_llm_available() -> bool:
    """Check if both minerva package and local Ollama are available."""
    try:
        import minerva  # noqa: F401
    except ImportError:
        return False
    try:
        import urllib.request

        req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:  # noqa: S310
            return resp.status == 200
    except Exception:
        return False


@pytest.mark.skipif(not _real_llm_available(), reason="minerva package or local Ollama not available")
@pytest.mark.asyncio
async def test_real_llm_selects_tool():
    """Integration test with actual Ollama — validates real LLM output format."""
    from minerva.llm.client import OpenAICompatibleClient

    client = OpenAICompatibleClient(
        base_url="http://localhost:11434/v1",
        api_key="ollama",
        model="qwen3:30b-a3b",
        timeout=30,
    )

    router = SmartRouter(catalog=ToolCatalog(db_path=":memory:"))
    router._llm = client

    candidates = [
        _make_tool("codeanalyze", "Analyze Python code for quality issues", ["python"], 0.95),
        _make_tool("dbquery", "Execute SQL queries against a database", ["sql"], 0.80),
    ]
    # Seed catalog so route_recommend can find them
    for c in candidates:
        router._catalog.add_tool(c)

    # Use a query that matches via keyword search (no embeddings available)
    result = await router._route_recommend("codeanalyze")

    assert result["status"] == "ok"
    # Real LLM may return llm_selected or llm_no_match — either is acceptable
    assert result["mode"] in ("llm_selected", "llm_fallback", "llm_no_match")
    assert "tools" in result or "tool" in result


# ═══════════════════════════════════════════════════════════════════════════════
# Test 6: Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Boundary conditions and error paths for SmartRouter.route()."""

    def test_empty_query(self, router):
        """Empty query should immediately return an error."""
        result = asyncio_run(router.route("", mode="recommend"))
        assert result["status"] == "error"
        assert "Empty query" in result.get("error", "")

    def test_whitespace_only_query(self, router):
        """Whitespace-only query should be treated as empty."""
        result = asyncio_run(router.route("   ", mode="recommend"))
        assert result["status"] == "error"
        assert "Empty query" in result.get("error", "")

    def test_unknown_mode(self, router):
        """Unknown mode should use 'auto' logic."""
        result = asyncio_run(router.route("analyze code", mode="unknown_mode"))
        # Should not crash — falls into 'auto' path
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_embeddings_unavailable_uses_keyword(self, catalog):
        """When EmbeddingStore is available=False, fall back to keyword search."""
        router = SmartRouter(catalog=catalog)
        mock_emb = MagicMock()
        mock_emb.available = False
        router._embeddings = mock_emb

        result = await router._route_recommend("codeanalyze")
        assert result["status"] == "ok"
        assert len(result["tools"]) > 0

    @pytest.mark.asyncio
    async def test_embeddings_available_no_results_falls_to_keyword(self, catalog):
        """When embeddings return nothing, fall back to catalog keyword search."""
        router = SmartRouter(catalog=catalog)
        mock_emb = MagicMock()
        mock_emb.available = True
        mock_emb.search_similar = MagicMock(return_value=[])
        router._embeddings = mock_emb

        result = await router._route_recommend("codeanalyze")
        assert result["status"] == "ok"
        assert len(result["tools"]) > 0

    @pytest.mark.asyncio
    async def test_status_method(self, router):
        """status() should return correct metadata."""
        s = router.status()
        assert s["mode"] == "smart_router"
        assert "llm_available" in s
        assert "embeddings_available" in s
        assert "lifecycle_available" in s
        assert "orchestrator_available" in s

    @pytest.mark.asyncio
    async def test_llm_available_property(self, router_with_llm):
        """llm_available property should reflect pre-set _llm."""
        assert router_with_llm.llm_available is True

    def test_llm_available_false(self, router):
        """llm_available should be False when _llm sentinel is False."""
        router._llm = False  # Force the "failed init" sentinel
        assert router.llm_available is False


class TestRouteAutoMode:
    """Test route() auto mode cascade: direct → recommend → auto_discover.

    These test the SmartRouter.route() method with mode='auto',
    which is the default mode used by agora_execute().
    Unlike existing tests that call _route_recommend() directly,
    these exercise the full 3-phase cascade through the public API.
    """

    @pytest.mark.asyncio
    async def test_auto_direct_match(self, catalog, router):
        """Auto mode Phase 1: direct match returns immediately."""
        result = await router.route("codeanalyze", mode="auto")
        assert result["status"] == "ok"
        assert result["mode"] == "auto(direct)"
        assert result["tool"]["name"] == "codeanalyze"

    @pytest.mark.asyncio
    async def test_auto_direct_no_match_no_tool(self, catalog):
        """Auto mode Phase 1: no direct match, but no tool found."""
        router = SmartRouter(catalog=catalog)
        result = await router.route("nonexistent_tool_xyz", mode="auto")
        assert result["status"] == "ok"
        assert result["action"] == "no_match"

    @pytest.mark.asyncio
    async def test_auto_recommend_with_llm(self, catalog):
        """Auto mode Phase 2: recommend succeeds with LLM when direct fails.

        Phase 1: first word 'zzz' doesn't match any tool → fails.
        Phase 2: _semantic_search returns candidates via mock embeddings,
                 then LLM selects one → auto(recommend).
        """
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value="codeanalyze")
        mock_emb = MagicMock()
        mock_emb.available = True
        # search_similar returns list of (tool_id, score) tuples
        mock_emb.search_similar.return_value = [
            ("codeanalyze", 0.95),
            ("dbquery", 0.80),
            ("monitor", 0.50),
            ("dockerps", 0.70),
            ("deploy", 0.60),
        ]

        router = SmartRouter(catalog=catalog)
        router._llm = mock_llm
        router._embeddings = mock_emb
        result = await router.route("zzz analyze python code", mode="auto")
        assert result["status"] == "ok"
        assert result["mode"] == "auto(recommend)"

    @pytest.mark.asyncio
    async def test_auto_recommend_quality_fallback(self, catalog):
        """Auto mode Phase 2: recommend falls back to quality scoring without LLM.

        Phase 1: first word 'zzz' doesn't match any tool → fails.
        Phase 2: _semantic_search returns candidates via mock embeddings,
                 no LLM → quality sort fallback → auto(recommend).
        """
        mock_emb = MagicMock()
        mock_emb.available = True
        # search_similar returns list of (tool_id, score) tuples
        mock_emb.search_similar.return_value = [
            ("codeanalyze", 0.95),
            ("dbquery", 0.80),
            ("monitor", 0.50),
            ("dockerps", 0.70),
            ("deploy", 0.60),
        ]

        router = SmartRouter(catalog=catalog)
        router._embeddings = mock_emb
        result = await router.route("zzz analyze python code", mode="auto")
        assert result["status"] == "ok"
        assert result["mode"] == "auto(recommend)"
        assert len(result.get("tools", [])) > 0
        # First tool should be highest quality (codeanalyze @ 0.95)
        assert result["tools"][0]["name"] == "codeanalyze"

    @pytest.mark.asyncio
    async def test_auto_recommend_empty_catalog(self):
        """Auto mode Phase 2: empty catalog returns no_match."""
        empty_catalog = ToolCatalog(db_path=":memory:")
        router = SmartRouter(catalog=empty_catalog)
        result = await router.route("anything", mode="auto")
        assert result["status"] == "ok"
        assert result["action"] == "no_match"


# ── Sync helper ──────────────────────────────────────────────────────────────


def asyncio_run(coro):
    """Run an async coroutine synchronously (for non-async tests)."""
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Already in an event loop — create new one in a thread
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor() as pool:
        return pool.submit(asyncio.run, coro).result()
