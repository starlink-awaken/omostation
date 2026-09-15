"""Tests for CostGuard budget management."""

import os
import tempfile


class TestCostGuard:
    """Tests for the cost guard."""

    def test_check_under_budget(self):
        """Test that spending under budget is allowed."""
        from minerva.executor.executor import CostGuard

        path = os.path.join(tempfile.gettempdir(), f"cost_guard_test_1_{os.getpid()}.jsonl")
        guard = CostGuard(monthly_budget=50.0, ledger_path=path)
        assert guard.check(10.0) is True
        assert guard.check(30.0) is True  # 40 total, still under 50

    def test_check_exceeded(self):
        """Test that exceeding budget is blocked."""
        from minerva.executor.executor import CostGuard

        path = os.path.join(tempfile.gettempdir(), f"cost_guard_test_2_{os.getpid()}.jsonl")
        guard = CostGuard(monthly_budget=50.0, ledger_path=path)
        guard.record(45.0)
        assert guard.check(10.0) is False

    def test_warn_threshold(self):
        """Test that warning threshold is reported correctly."""
        from minerva.executor.executor import CostGuard

        path = os.path.join(tempfile.gettempdir(), f"cost_guard_test_3_{os.getpid()}.jsonl")
        guard = CostGuard(monthly_budget=50.0, warn_pct=0.80, ledger_path=path)
        guard.record(42.0)  # 84% used
        status = guard.get_status()
        assert status["current_spend"] == 42.0
        assert status["remaining"] == 8.0
        assert status["pct_used"] == 84.0
