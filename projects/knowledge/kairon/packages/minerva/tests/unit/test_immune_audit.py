"""Tests for ImmuneAuditStage pipeline stage."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from minerva.pipeline.engine import ResearchContext
from minerva.triage.router import ResearchLevel, TriageResult


def _make_ctx(
    query: str = "test query", search_results: list | None = None, entities: list | None = None
) -> ResearchContext:
    """Create a ResearchContext with given data for testing."""
    return ResearchContext(
        query=query,
        level=ResearchLevel.L2,
        triage=TriageResult(
            level=ResearchLevel.L2,
            scores={"domain": 3, "timeliness": 3, "depth": 3, "multi_source": 3, "privacy": 3},
            cost_estimate=0.5,
            model_plan={"agent_model": "local", "reasoning_model": "local", "writer_model": "local"},
            search_plan=["searxng", "ddg", "scholar"],
        ),
        search_results=search_results or [],
        entities=entities or [],
    )


class TestImmuneAuditStage:
    """Tests for ImmuneAuditStage."""

    @pytest.mark.asyncio
    async def test_skips_when_no_content(self):
        """Stage skips audit when context has no search results or entities."""
        from minerva.pipeline.immune_audit import ImmuneAuditStage

        stage = ImmuneAuditStage()
        ctx = _make_ctx()
        result = await stage.execute(ctx)
        assert result is ctx
        assert "immune_review_required" not in ctx.metadata

    @pytest.mark.asyncio
    async def test_audits_search_results(self):
        """Stage audits search results from the context."""
        from minerva.pipeline.immune_audit import ImmuneAuditStage

        stage = ImmuneAuditStage()

        ctx = _make_ctx(
            search_results=[
                {"title": "Safe Result", "snippet": "normal content", "source": "arxiv"},
            ]
        )

        with patch.object(stage, "_audit", return_value={"risk": "LOW"}) as mock_audit:
            result = await stage.execute(ctx)

        assert result is ctx
        mock_audit.assert_called_once()
        assert mock_audit.call_args[0][0]["title"] == "Safe Result"

    @pytest.mark.asyncio
    async def test_flags_high_risk_content(self):
        """Stage flags context when audit returns HIGH risk."""
        from minerva.pipeline.immune_audit import ImmuneAuditStage

        stage = ImmuneAuditStage()

        ctx = _make_ctx(
            search_results=[
                {"title": "Risky Result", "snippet": "dangerous content", "source": "web"},
            ]
        )

        with patch.object(stage, "_audit", return_value={"risk": "HIGH"}):
            result = await stage.execute(ctx)

        assert result.metadata.get("immune_review_required") is True
        assert result.metadata.get("immune_high_risk_count") == 1

    @pytest.mark.asyncio
    async def test_audits_entities(self):
        """Stage audits entities from the context."""
        from minerva.pipeline.immune_audit import ImmuneAuditStage

        stage = ImmuneAuditStage()

        ctx = _make_ctx(
            entities=[
                {"label": "Test Entity", "description": "entity desc", "source": "entity_extraction"},
            ]
        )

        with patch.object(stage, "_audit", return_value={"risk": "LOW"}) as mock_audit:
            result = await stage.execute(ctx)

        assert result is ctx
        mock_audit.assert_called_once()

    @pytest.mark.asyncio
    async def test_audit_failure_does_not_block(self):
        """Stage handles audit failure gracefully."""
        from minerva.pipeline.immune_audit import ImmuneAuditStage

        stage = ImmuneAuditStage()

        ctx = _make_ctx(
            search_results=[
                {"title": "T1", "snippet": "content", "source": "arxiv"},
            ]
        )

        with patch.object(stage, "_audit", side_effect=Exception("Connection error")):
            result = await stage.execute(ctx)

        assert result is ctx
        assert "immune_review_required" not in ctx.metadata

    @pytest.mark.asyncio
    async def test_high_risk_count_accumulates(self):
        """Multiple HIGH risk items accumulate in the count."""
        from minerva.pipeline.immune_audit import ImmuneAuditStage

        stage = ImmuneAuditStage()

        ctx = _make_ctx(
            search_results=[
                {"title": "R1", "snippet": "bad1", "source": "web"},
                {"title": "R2", "snippet": "bad2", "source": "web"},
                {"title": "R3", "snippet": "good", "source": "arxiv"},
            ]
        )

        audit_results = [
            {"risk": "HIGH"},
            {"risk": "HIGH"},
            {"risk": "LOW"},
        ]

        with patch.object(stage, "_audit", side_effect=audit_results):
            result = await stage.execute(ctx)

        assert result.metadata.get("immune_high_risk_count") == 2

    @pytest.mark.asyncio
    async def test_name_is_correct(self):
        """Stage has the correct name attribute."""
        from minerva.pipeline.immune_audit import ImmuneAuditStage

        stage = ImmuneAuditStage()
        assert stage.name == "immune_audit"

    @pytest.mark.asyncio
    async def test_unknown_risk_not_flagged(self):
        """UNKNOWN risk from audit should not be flagged as HIGH."""
        from minerva.pipeline.immune_audit import ImmuneAuditStage

        stage = ImmuneAuditStage()

        ctx = _make_ctx(
            search_results=[
                {"title": "Unknown", "snippet": "content", "source": "web"},
            ]
        )

        with patch.object(stage, "_audit", return_value={"risk": "UNKNOWN"}):
            await stage.execute(ctx)

        assert "immune_review_required" not in ctx.metadata
