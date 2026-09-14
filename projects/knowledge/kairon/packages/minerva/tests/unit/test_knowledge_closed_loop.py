"""Unit tests for KOSSaveStage, KnowledgeClosedLoop, and the MCP tool."""

from __future__ import annotations

import hashlib
import typing
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from minerva.knowledge_closed_loop import KnowledgeClosedLoop
from minerva.pipeline.engine import ResearchContext
from minerva.pipeline.stages.kos_save import KOSSaveStage, _make_entity_id
from minerva.triage.router import ResearchLevel, TriageResult

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_triage(level: ResearchLevel = ResearchLevel.L2) -> TriageResult:
    return TriageResult(
        level=level,
        scores={
            "domain_complexity": 3,
            "timeliness": 2,
            "depth_required": 4,
            "multi_source": 3,
            "privacy_sensitivity": 1,
        },
        cost_estimate=0.30,
        model_plan={"reasoner": "local"},
        search_plan=["web_search"],
    )


def _make_ctx(
    query: str = "test query",
    level: ResearchLevel = ResearchLevel.L2,
    report: str | None = "Test report content.\n\nSome findings.",
    search_results: list[dict] | None = None,
    entities: list[dict] | None = None,
    cost: float = 0.15,
) -> ResearchContext:
    ctx = ResearchContext(
        query=query,
        level=level,
        triage=_make_triage(level),
        search_results=search_results or [],
        entities=entities or [],
        cost=cost,
    )
    ctx.report = report
    return ctx


def _mock_executor(result_ctx: ResearchContext | None = None) -> MagicMock:
    """Create a mock ResearchExecutor."""
    if result_ctx is None:
        result_ctx = _make_ctx()
    mock = MagicMock()
    mock.execute_now = AsyncMock(
        return_value=MagicMock(
            task_id="test-001",
            context=result_ctx,
            summary="Test summary.",
            report_path=None,
            cost=result_ctx.cost,
            completed_at="2025-01-01T00:00:00Z",
        )
    )
    return mock


# ===================================================================
# KOSSaveStage
# ===================================================================


class TestKOSSaveStage:
    """Unit tests for the KOSSaveStage pipeline stage."""

    @pytest.mark.asyncio
    async def test_save_with_report(self):
        """Stage saves entity when report is present."""
        ctx = _make_ctx(query="What is MoE?", report="Mixture of Experts is a...")

        with (
            patch("minerva.pipeline.stages.kos_save._get_kos_store") as mock_store,
            patch("minerva.pipeline.stages.kos_save.AuditLogger") as mock_audit,
        ):
            mock_store.return_value = {
                "put_entity": MagicMock(return_value={"status": "ok", "entity_id": "RCH-abc123"}),
                "search_entities": MagicMock(return_value=[]),
                "Entity": MagicMock,
                "EntityType": MagicMock(CONCEPT="concept"),
            }
            mock_audit.return_value = MagicMock()

            stage = KOSSaveStage()
            result = await stage.execute(ctx)

            assert result is ctx
            mock_store.return_value["put_entity"].assert_called_once()  # type: ignore[reportCallIssue]

    @pytest.mark.asyncio
    async def test_skip_without_report(self):
        """Stage skips when ctx.report is None."""
        ctx = _make_ctx(report=None)

        with patch("minerva.pipeline.stages.kos_save._get_kos_store") as mock_store:
            stage = KOSSaveStage()
            result = await stage.execute(ctx)

            assert result is ctx
            mock_store.return_value["put_entity"].assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_when_kos_unavailable(self):
        """Stage skips when KOS package is not available."""
        ctx = _make_ctx()

        with patch("minerva.pipeline.stages.kos_save._get_kos_store", return_value={}):
            stage = KOSSaveStage()
            result = await stage.execute(ctx)

            assert result is ctx

    @pytest.mark.asyncio
    async def test_entity_id_deterministic(self):
        """KOS entity ID is deterministic based on query content."""
        query = "What is Mixture of Experts?"
        expected_id = "RCH-" + hashlib.sha256(query.encode()).hexdigest()[:12]

        entity_id = _make_entity_id(query)

        assert entity_id == expected_id
        assert entity_id.startswith("RCH-")

    @pytest.mark.asyncio
    async def test_metadata_structure(self):
        """Metadata includes query, level, cost, and counts."""
        ctx = _make_ctx(
            query="test query",
            level=ResearchLevel.L3,
            report="Some report content.",
            search_results=[{"url": "https://a.com"}, {"url": "https://b.com"}],
            entities=[{"name": "ent1"}],
            cost=0.42,
        )

        captured_entity = None

        def fake_put(entity):
            nonlocal captured_entity
            captured_entity = entity
            return {"status": "ok", "entity_id": entity.entity_id}

        with (
            patch("minerva.pipeline.stages.kos_save._get_kos_store") as mock_store,
            patch("minerva.pipeline.stages.kos_save.AuditLogger"),
        ):
            mock_store.return_value = {
                "put_entity": fake_put,
                "search_entities": MagicMock(),
                "Entity": MagicMock,
                "EntityType": MagicMock(CONCEPT="concept"),
            }

            stage = KOSSaveStage()
            await stage.execute(ctx)

            assert captured_entity is not None
            meta = captured_entity.metadata
            assert meta["query"] == "test query"
            assert meta["level"] == "L3"
            assert meta["cost"] == 0.42
            assert meta["search_count"] == 2
            assert meta["entity_count"] == 1

    @pytest.mark.asyncio
    async def test_audit_logged_on_success(self):
        """Audit log entry is created on successful save."""
        ctx = _make_ctx(query="audit test")

        mock_audit_instance = MagicMock()

        with (
            patch("minerva.pipeline.stages.kos_save._get_kos_store") as mock_store,
            patch("minerva.pipeline.stages.kos_save.AuditLogger") as mock_audit_cls,
        ):
            mock_store.return_value = {
                "put_entity": MagicMock(return_value={"status": "ok", "entity_id": "RCH-audit1"}),
                "search_entities": MagicMock(),
                "Entity": MagicMock,
                "EntityType": MagicMock(CONCEPT="concept"),
            }
            mock_audit_cls.return_value = mock_audit_instance

            stage = KOSSaveStage()
            await stage.execute(ctx)

            mock_audit_instance.log.assert_called_once()
            _, kwargs = mock_audit_instance.log.call_args
            assert kwargs.get("action") == "kos_save"


# ===================================================================
# KnowledgeClosedLoop
# ===================================================================


class TestKnowledgeClosedLoop:
    """Unit tests for the KnowledgeClosedLoop orchestrator."""

    # ── full_flow ────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_full_flow_cache_miss(self):
        """Orchestrator runs pipeline and returns result on cache miss."""
        executor = _mock_executor()

        with (
            patch.object(KnowledgeClosedLoop, "_check_kos_cache", return_value=None),
            patch("minerva.knowledge_closed_loop.AuditLogger") as mock_audit,
        ):
            mock_audit.return_value = MagicMock()
            loop = KnowledgeClosedLoop(executor)
            result = await loop.search("test query")

            assert result["status"] == "ok"
            assert result["action"] == "completed"
            assert result["query"] == "test query"
            assert result["entity_id"].startswith("RCH-")
            executor.execute_now.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """Orchestrator returns cached result without running pipeline."""
        executor = _mock_executor()

        with (
            patch.object(KnowledgeClosedLoop, "_check_kos_cache") as mock_cache,
            patch("minerva.knowledge_closed_loop.AuditLogger"),
        ):
            mock_cache.return_value = {
                "entity_id": "RCH-cached1",
                "label": "Test Query",
                "description": "Cached result.",
            }
            loop = KnowledgeClosedLoop(executor)
            result = await loop.search("Test Query")

            assert result["status"] == "ok"
            assert result["action"] == "cache_hit"
            assert result["entity_id"] == "RCH-cached1"
            executor.execute_now.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fresh_overrides_cache(self):
        """fresh=True bypasses KOS cache and runs pipeline."""
        executor = _mock_executor()

        with (
            patch.object(KnowledgeClosedLoop, "_check_kos_cache") as mock_cache,
            patch("minerva.knowledge_closed_loop.AuditLogger"),
        ):
            mock_cache.return_value = {
                "entity_id": "RCH-cached1",
                "label": "Test Query",
                "description": "Cached result.",
            }
            loop = KnowledgeClosedLoop(executor)
            result = await loop.search("Test Query", fresh=True)

            assert result["status"] == "ok"
            assert result["action"] == "completed"
            executor.execute_now.assert_awaited_once()
            mock_cache.assert_not_called()

    @pytest.mark.asyncio
    async def test_pipeline_error(self):
        """Orchestrator returns error on pipeline failure."""
        executor = _mock_executor()
        executor.execute_now = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

        with (
            patch.object(KnowledgeClosedLoop, "_check_kos_cache", return_value=None),
            patch("minerva.knowledge_closed_loop.AuditLogger"),
        ):
            loop = KnowledgeClosedLoop(executor)
            result = await loop.search("test query")

            assert result["status"] == "error"
            assert "LLM unavailable" in result["error"]

    @pytest.mark.asyncio
    async def test_batch_confirmed(self):
        """L2 batch with confirmed=True proceeds."""
        executor = _mock_executor()

        with (
            patch.object(KnowledgeClosedLoop, "_check_kos_cache", return_value=None),
            patch("minerva.knowledge_closed_loop.AuditLogger"),
        ):
            loop = KnowledgeClosedLoop(executor)
            result = await loop.search("batch test", level="batch", confirmed=True)

            assert result["status"] == "ok"
            executor.execute_now.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_batch_denied(self):
        """L2 batch without confirmed returns error."""
        executor = _mock_executor()

        with (
            patch.object(KnowledgeClosedLoop, "_check_kos_cache", return_value=None),
            patch("minerva.knowledge_closed_loop.AuditLogger"),
        ):
            loop = KnowledgeClosedLoop(executor)
            result = await loop.search("batch test", level="batch", confirmed=False)

            assert result["status"] == "error"
            assert "confirmed=True" in result["error"]
            executor.execute_now.assert_not_awaited()


# ===================================================================
# MCP Tool Registration
# ===================================================================


class TestKnowledgeClosedLoopMCP:
    """Verify the MCP tool is properly registered and importable."""

    def test_import_knowledge_closed_loop(self):
        """Verify KnowledgeClosedLoop can be imported from the orchestator module."""
        from minerva.knowledge_closed_loop import KnowledgeClosedLoop as KCL  # noqa: N817

        assert KCL is not None

    def test_tool_function_exists(self):
        """Verify knowledge_closed_loop tool is exposed in the server module."""
        from minerva.mcp_server.server import knowledge_closed_loop

        assert callable(knowledge_closed_loop)

    def test_tool_parameters(self):
        """Verify tool function accepts expected parameters."""
        from minerva.mcp_server.server import knowledge_closed_loop

        hints = typing.get_type_hints(knowledge_closed_loop)

        assert "query" in hints
        assert hints["query"] is str
        assert "level" in hints
        assert "confirmed" in hints
        assert hints["confirmed"] is bool
        assert "fresh" in hints
        assert hints["fresh"] is bool

    @pytest.mark.asyncio
    async def test_tool_routes_to_loop(self):
        """Verify tool delegates to KnowledgeClosedLoop.search."""
        from minerva.mcp_server.server import knowledge_closed_loop

        mock_loop = AsyncMock()
        mock_loop.search.return_value = {"status": "ok", "format_version": "minerva-v1"}

        with (
            patch("minerva.mcp_server.server._ensure_executor"),
            patch("minerva.knowledge_closed_loop.KnowledgeClosedLoop", return_value=mock_loop),
        ):
            result = await knowledge_closed_loop(query="test", level="auto")

            assert result["status"] == "ok"
            mock_loop.search.assert_awaited_once_with(query="test", level="auto", confirmed=False, fresh=False)


# ===================================================================
# Integration-style tests
# ===================================================================


class TestKOSSaveStageIntegration:
    """Tests that verify KOS entity creation using mocked stores."""

    @pytest.mark.asyncio
    async def test_search_result_references_in_entity(self):
        """KOS entity references field contains search result URLs."""
        ctx = _make_ctx(
            query="test refs",
            report="Report with refs.",
            search_results=[
                {"url": "https://example.com/1"},
                {"url": "https://example.com/2"},
            ],
        )

        captured = {}

        def fake_put(entity):
            captured["entity"] = entity
            return {"status": "ok", "entity_id": entity.entity_id}

        with (
            patch("minerva.pipeline.stages.kos_save._get_kos_store") as mock_store,
            patch("minerva.pipeline.stages.kos_save.AuditLogger"),
        ):
            mock_store.return_value = {
                "put_entity": fake_put,
                "search_entities": MagicMock(),
                "Entity": MagicMock,
                "EntityType": MagicMock(CONCEPT="concept"),
            }

            stage = KOSSaveStage()
            await stage.execute(ctx)

            entity = captured["entity"]
            assert "https://example.com/1" in entity.references
            assert "https://example.com/2" in entity.references

    @pytest.mark.asyncio
    async def test_kos_cache_search(self):
        """KnowledgeClosedLoop._check_kos_cache queries KOS zone=minerva_research."""
        executor = _mock_executor()

        with (
            patch.object(KnowledgeClosedLoop, "_get_kos") as mock_get_kos,
            patch("minerva.knowledge_closed_loop.AuditLogger"),
        ):
            mock_search = MagicMock(return_value=[])
            mock_get_kos.return_value = {
                "search_entities": mock_search,
                "Entity": MagicMock,
                "EntityType": MagicMock(CONCEPT="concept"),
            }

            loop = KnowledgeClosedLoop(executor)
            result = loop._check_kos_cache("test query")

            assert result is None
            mock_search.assert_called_once_with("test query", zone="minerva_research", limit=3)
