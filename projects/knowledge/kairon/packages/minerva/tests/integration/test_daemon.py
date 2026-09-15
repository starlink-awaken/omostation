"""Integration tests for daemon — scheduled + watch execution loop."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


class TestDaemonIntegration:
    """Tests for daemon lifecycle: start → schedule → execute → stop."""

    @pytest.mark.asyncio
    async def test_schedule_persistence_roundtrip(self):
        """Scheduled task persisted to disk, loaded on restart."""
        from minerva.executor.executor import CostGuard, ResearchExecutor

        state_dir = Path(tempfile.mkdtemp()) / "state"
        state_dir.mkdir(parents=True)

        config = [{"id": "test-task-1", "cron": "0 8 * * *"}]
        (state_dir / "scheduled_tasks.json").write_text(json.dumps(config))

        executor = ResearchExecutor(
            triage_router=MagicMock(),
            pipeline=MagicMock(),
            knowledge_store=MagicMock(),
            cost_guard=CostGuard(50.0, ledger_path="/tmp/test-daemon-cost.jsonl"),
            state_dir=str(state_dir),
        )
        result = executor.restore_state()
        assert result["scheduled"] == 1
        assert result["watch"] == 0

    @pytest.mark.asyncio
    async def test_scheduled_task_creation(self):
        """schedule() creates an APScheduler job and persists config."""
        from minerva.executor.executor import (
            CostGuard,
            ExecutionMode,
            ResearchExecutor,
            ResearchTask,
        )

        executor = ResearchExecutor(
            triage_router=MagicMock(),
            pipeline=MagicMock(),
            knowledge_store=MagicMock(),
            cost_guard=CostGuard(50.0, ledger_path="/tmp/test-daemon-sched.jsonl"),
            state_dir="/tmp/test-daemon-sched-state",
        )
        task = ResearchTask(
            id="cron-test-1",
            query="Daily AI news",
            mode=ExecutionMode.SCHEDULED,
            level="L1",
            max_cost=0.0,
            cron_expr="0 8 * * *",
        )
        task_id = await executor.schedule(task)
        assert task_id == "cron-test-1"
        status = executor.health_check()
        assert status["scheduled"] == 1

    @pytest.mark.asyncio
    async def test_daemon_health_check(self):
        """health_check() returns correct structure."""
        from minerva.executor.executor import CostGuard, ResearchExecutor

        executor = ResearchExecutor(
            triage_router=MagicMock(),
            pipeline=MagicMock(),
            knowledge_store=MagicMock(),
            cost_guard=CostGuard(50.0, ledger_path="/tmp/test-daemon-hc.jsonl"),
            state_dir="/tmp/test-daemon-hc-state",
        )
        status = executor.health_check()
        assert status["scheduled"] == 0
        assert status["watch"] == 0
        assert status["budget_used"] >= 0
        assert "budget_limit" in status

    @pytest.mark.asyncio
    async def test_cost_guard_persists_across_restarts(self):
        """CostGuard ledger survives daemon restart."""
        import tempfile as tmp

        with tmp.NamedTemporaryFile(suffix=".jsonl", delete=False) as ledger_file:
            ledger = ledger_file.name

        from minerva.executor.executor import CostGuard

        try:
            cg1 = CostGuard(50.0, ledger_path=ledger)
            cg1.record(15.0)
            assert cg1.current_spend == 15.0

            cg2 = CostGuard(50.0, ledger_path=ledger)
            assert cg2.current_spend == 15.0  # Should persist
        finally:
            Path(ledger).unlink(missing_ok=True)
