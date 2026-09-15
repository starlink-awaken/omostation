"""Tests for ResearchExecutor — immediate/scheduled/watch modes, cost guard."""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestResearchExecutor:
    """Tests for ResearchExecutor with mocked dependencies."""

    @pytest.fixture
    def mock_router(self):
        router = MagicMock()
        router.classify = AsyncMock()
        return router

    @pytest.fixture
    def mock_pipeline(self):
        pipeline = MagicMock()
        pipeline.run = AsyncMock()
        return pipeline

    @pytest.fixture
    def mock_kb(self):
        kb = MagicMock()
        kb.search = AsyncMock(return_value=[])
        kb.ingest = AsyncMock(return_value={})
        return kb

    @pytest.fixture
    def mock_cost_guard(self):
        from minerva.executor.executor import CostGuard

        return CostGuard(monthly_budget=50.0, ledger_path="/tmp/test_exec_cg.jsonl")

    def test_cost_guard_check_under_budget(self):
        """Test cost guard allows spend within budget."""
        from minerva.executor.executor import CostGuard

        cg = CostGuard(monthly_budget=50.0, ledger_path="/tmp/test_cg1.jsonl")
        assert cg.check(1.0) is True
        assert cg.check(10.0) is True

    def test_cost_guard_check_exceeded(self):
        """Test cost guard blocks spend over budget."""
        from minerva.executor.executor import CostGuard

        cg = CostGuard(monthly_budget=50.0, ledger_path="/tmp/test_cg2.jsonl")
        assert cg.check(60.0) is False

    def test_cost_guard_record_increments_spend(self):
        """Test recording actual cost increments current spend."""
        import os
        import tempfile

        from minerva.executor.executor import CostGuard

        path = os.path.join(tempfile.gettempdir(), f"test_cg_{os.getpid()}_3.jsonl")
        cg = CostGuard(monthly_budget=50.0, ledger_path=path)
        cg.record(15.0)
        assert cg.current_spend == 15.0
        cg.record(5.0)
        assert cg.current_spend == 20.0

    def test_cost_guard_get_status(self):
        """Test get_status returns correct budget info."""
        import os
        import tempfile

        from minerva.executor.executor import CostGuard

        path = os.path.join(tempfile.gettempdir(), f"test_cg_{os.getpid()}_4.jsonl")
        cg = CostGuard(monthly_budget=100.0, ledger_path=path)
        cg.record(30.0)
        status = cg.get_status()
        assert status["monthly_budget"] == 100.0
        assert status["current_spend"] == 30.0
        assert status["remaining"] == 70.0
        assert status["pct_used"] == 30.0

    @pytest.mark.asyncio
    async def test_executor_creates_with_deps(self, mock_router, mock_pipeline, mock_kb, mock_cost_guard):
        """Test ResearchExecutor initializes without errors."""
        from minerva.executor.executor import ResearchExecutor

        executor = ResearchExecutor(
            triage_router=mock_router,
            pipeline=mock_pipeline,
            knowledge_store=mock_kb,
            cost_guard=mock_cost_guard,
            state_dir="/tmp/minerva-test-state",
        )
        assert executor is not None
        assert executor.router is mock_router
        assert executor.pipeline is mock_pipeline

    @pytest.mark.asyncio
    async def test_executor_task_dataclasses(self):
        """Test ResearchTask and ResearchResult dataclass creation."""
        from minerva.executor.executor import (
            ExecutionMode,
            ResearchResult,
            ResearchTask,
            TaskStatus,
        )
        from minerva.pipeline.engine import ResearchContext
        from minerva.triage.router import ResearchLevel, TriageResult

        task = ResearchTask(
            id="test-001",
            query="What is MoE?",
            mode=ExecutionMode.IMMEDIATE,
            level="L2",
            max_cost=1.0,
        )
        assert task.id == "test-001"
        assert task.query == "What is MoE?"
        assert task.mode == ExecutionMode.IMMEDIATE

        ctx = ResearchContext(
            query="test",
            level=ResearchLevel.L2,
            triage=TriageResult(
                level=ResearchLevel.L2,
                scores={"goal": 0.9, "constraints": 0.8, "criteria": 0.7},  # type: ignore[arg-type]
                cost_estimate=0.3,
                model_plan={},  # type: ignore[arg-type]
                search_plan={},  # type: ignore[arg-type]
                total_score=0.8,
            ),
        )
        result = ResearchResult(
            task_id="test-001",
            context=ctx,
            summary="Test summary",
            report_path="/tmp/report.md",
            cost=0.3,
            completed_at="2026-01-01T00:00:00Z",
        )
        assert result.task_id == "test-001"
        assert result.cost == 0.3

        ts = TaskStatus(
            task_id="test-001",
            status="running",
            mode=ExecutionMode.IMMEDIATE,
            query="test",
            level="L2",
            cost=0.0,
            started_at=None,
            completed_at=None,
        )
        assert ts.status == "running"


class TestBudgetExceededError:
    """Tests for BudgetExceededError."""

    def test_budget_error_is_exception(self):
        """Test BudgetExceededError is a proper Exception subclass."""
        from minerva.executor.executor import BudgetExceededError

        with pytest.raises(BudgetExceededError):
            raise BudgetExceededError("Test budget exceeded")
