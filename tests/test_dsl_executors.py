"""Tests for DSL executors — safe_eval and step execution.

Verifies:
- _safe_eval accepts valid expressions
- _safe_eval rejects dangerous expressions
- DSLExecutors.conditional routes correctly
- DSLExecutors.loop iterates correctly
"""

from __future__ import annotations

import pytest

from runtime.executor.dsl_executors import (
    DSLExecutors,
    ExecutorContext,
    _safe_eval,
)


class TestSafeEval:
    """_safe_eval should accept safe expressions and reject dangerous ones."""

    def test_literal_true(self):
        assert _safe_eval("True", {}) is True

    def test_literal_false(self):
        assert _safe_eval("False", {}) is False

    def test_literal_none(self):
        assert _safe_eval("None", {}) is None

    def test_literal_number(self):
        assert _safe_eval("42", {}) == 42

    def test_literal_string(self):
        assert _safe_eval("'hello'", {}) == "hello"

    def test_variable_lookup(self):
        assert _safe_eval("x", {"x": 10}) == 10

    def test_eq_comparison(self):
        assert _safe_eval("x == 10", {"x": 10}) is True

    def test_neq_comparison(self):
        assert _safe_eval("x != 10", {"x": 5}) is True

    def test_lt_comparison(self):
        assert _safe_eval("x < 10", {"x": 5}) is True

    def test_gt_comparison(self):
        assert _safe_eval("x > 10", {"x": 15}) is True

    def test_lte_comparison(self):
        assert _safe_eval("x <= 10", {"x": 10}) is True

    def test_gte_comparison(self):
        assert _safe_eval("x >= 10", {"x": 10}) is True

    def test_and_operator(self):
        assert _safe_eval("x > 0 and y < 100", {"x": 5, "y": 50}) is True

    def test_or_operator(self):
        assert _safe_eval("x > 0 or y > 100", {"x": 0, "y": 50}) is False

    def test_and_operator_true(self):
        assert _safe_eval("x > 0 and y < 100", {"x": 5, "y": 50}) is True

    def test_or_operator_true(self):
        assert _safe_eval("x > 0 or y > 100", {"x": 5, "y": 50}) is True

    def test_not_operator(self):
        assert _safe_eval("not x", {"x": False}) is True

    def test_chain_comparison(self):
        assert _safe_eval("0 < x < 100", {"x": 50}) is True

    def test_mixed_expression(self):
        assert _safe_eval("x == 1 and y == 2", {"x": 1, "y": 2}) is True

    def test_rejects_function_call(self):
        with pytest.raises(ValueError):
            _safe_eval("__import__('os')", {})

    def test_rejects_attribute_access(self):
        with pytest.raises(ValueError):
            _safe_eval("x.y", {"x": {}})

    def test_rejects_subscript(self):
        with pytest.raises(ValueError):
            _safe_eval("x[0]", {"x": [1, 2, 3]})

    def test_rejects_arithmetic(self):
        with pytest.raises(ValueError):
            _safe_eval("x + 1", {"x": 1})

    def test_rejects_list_literal(self):
        with pytest.raises(ValueError):
            _safe_eval("[1, 2, 3]", {})

    def test_rejects_dict_literal(self):
        with pytest.raises(ValueError):
            _safe_eval("{'a': 1}", {})


class TestDSLExecutorsConditional:
    """DSLExecutors.conditional should route based on condition."""

    @pytest.mark.asyncio
    async def test_condition_true_routes_to_true_step(self):
        executors = DSLExecutors()
        ctx = ExecutorContext(globals={"x": 10})
        result = await executors.conditional(
            ctx, "x > 5", true_step="next_a", false_step="next_b"
        )
        assert result.success is True
        assert result.output is True
        assert result.next_step == "next_a"

    @pytest.mark.asyncio
    async def test_condition_false_routes_to_false_step(self):
        executors = DSLExecutors()
        ctx = ExecutorContext(globals={"x": 1})
        result = await executors.conditional(
            ctx, "x > 5", true_step="next_a", false_step="next_b"
        )
        assert result.success is True
        assert result.output is False
        assert result.next_step == "next_b"

    @pytest.mark.asyncio
    async def test_condition_with_results_context(self):
        executors = DSLExecutors()
        ctx = ExecutorContext(results={"count": 3})
        result = await executors.conditional(
            ctx, "count > 0", true_step="proceed", false_step="stop"
        )
        assert result.success is True
        assert result.next_step == "proceed"

    @pytest.mark.asyncio
    async def test_invalid_condition_returns_error(self):
        executors = DSLExecutors()
        ctx = ExecutorContext(globals={"x": 1})
        result = await executors.conditional(
            ctx, "x + 1", true_step="a", false_step="b"
        )
        assert result.success is False
        assert "Unsupported" in result.error


class TestDSLExecutorsLoop:
    """DSLExecutors.loop should iterate until condition is met."""

    @pytest.mark.asyncio
    async def test_loop_with_counter_condition(self):
        executors = DSLExecutors()
        ctx = ExecutorContext(globals={"counter": 0})
        sub_steps = [
            {"id": "inc", "type": "agent_call", "target": "increment", "params": {}}
        ]

        # Mock the agent call to increment counter
        async def mock_agent(ctx2):
            ctx2.globals["counter"] = ctx2.globals.get("counter", 0) + 1
            from runtime.executor.dsl_executors import ExecutorResult

            return ExecutorResult(success=True, output=ctx2.globals["counter"])

        executors.register_agent("increment", mock_agent)
        result = await executors.loop(
            ctx, sub_steps, max_iterations=5, condition="counter < 3"
        )
        assert result.success is True
        assert ctx.globals["counter"] == 3

    @pytest.mark.asyncio
    async def test_loop_respects_max_iterations(self):
        executors = DSLExecutors()
        ctx = ExecutorContext(globals={"counter": 0})

        async def mock_agent(ctx2):
            ctx2.globals["counter"] = ctx2.globals.get("counter", 0) + 1
            from runtime.executor.dsl_executors import ExecutorResult

            return ExecutorResult(success=True, output=ctx2.globals["counter"])

        executors.register_agent("increment", mock_agent)
        result = await executors.loop(
            ctx,
            [{"id": "inc", "type": "agent_call", "target": "increment", "params": {}}],
            max_iterations=3,
        )
        assert result.success is True
        assert ctx.globals["counter"] == 3
