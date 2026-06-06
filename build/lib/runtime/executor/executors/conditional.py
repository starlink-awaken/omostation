from __future__ import annotations

from typing import Any

from runtime.executor.dsl_types import (
    ConditionalBranch,
    DSLExpression,
    DSLNode,
    DSLNodeType,
    ExecutionContext,
    ExecutionResult,
)
from runtime.executor.step_executor import ExecutionDependencies


class IExpressionEvaluator:
    def evaluate(self, expr: DSLExpression, context: ExecutionContext) -> Any:
        raise NotImplementedError


class IStepExecutor:
    async def execute_step(self, step: DSLNode, context: ExecutionContext) -> ExecutionContext:
        raise NotImplementedError


class ConditionStepExecutor:
    """Executes if-elif-else conditional branches for DSL workflow steps."""

    def __init__(self, dependencies: ExecutionDependencies, step_executor: IStepExecutor, expression_evaluator: IExpressionEvaluator | None = None) -> None:
        self._deps = dependencies
        self._step_exec = step_executor
        self._expr_eval = expression_evaluator or DefaultExpressionEvaluator()

    async def execute_step(self, step: DSLNode, context: ExecutionContext) -> ExecutionResult:
        step_name = getattr(step, "name", None) or "conditional"
        branches: list[ConditionalBranch] = getattr(step, "branches", [])
        inputs: dict[str, DSLExpression] = getattr(step, "inputs", {})
        outputs: dict[str, str] = getattr(step, "outputs", {})
        resolved = self._resolve_inputs(inputs, context)
        enriched = self._enrich_context(context, resolved)
        for branch in branches:
            if branch.else_call is not None:
                return await self._exec_call(branch.else_call, resolved, outputs, step, enriched)  # type: ignore[arg-type]
            if branch.if_expr and branch.then_call and self._is_truthy(self._expr_eval.evaluate(branch.if_expr, enriched)):
                return await self._exec_call(branch.then_call, resolved, outputs, step, enriched)  # type: ignore[arg-type]
        self._log_error(step, f"No matching branch in conditional step '{step_name}'", context)
        return ExecutionResult(success=False, value=None, trace=[], errors=[Exception(f"No matching branch in conditional step '{step_name}'")], outputs={})

    def _resolve_inputs(self, inputs: dict[str, DSLExpression], context: ExecutionContext) -> dict[str, Any]:
        return {k: self._expr_eval.evaluate(v, context) for k, v in inputs.items()}

    def _enrich_context(self, context: ExecutionContext, resolved: dict[str, Any]) -> ExecutionContext:
        enriched = ExecutionContext(
            input=context.input.copy(), locals=context.locals.copy(), results=context.results.copy(),
            trace_id=context.trace_id, depth=context.depth, trace=context.trace.copy(), parent=context.parent, options=context.options,
        )
        enriched.locals.update(resolved)
        return enriched

    async def _exec_call(self, call: DSLNode, resolved: dict[str, Any], outputs: dict[str, str], step: DSLNode, context: ExecutionContext) -> ExecutionResult:
        from runtime.executor.dsl_types import DSLCall, DSLLiteral, DSLStep

        call_type = getattr(call, "type", "agent")
        target = getattr(call, "name", step) if call_type in ("agent", "tool") else getattr(call, "skill_id", step)
        temp_call = DSLCall(type=call_type, name=getattr(call, "name", ""), skill_id=getattr(call, "skill_id", ""))
        temp_inputs = {k: DSLLiteral(value=v) for k, v in resolved.items()}
        temp_step = DSLStep(name=str(target), call=temp_call, inputs=temp_inputs, outputs=outputs)  # type: ignore[arg-type]
        try:
            updated = await self._step_exec.execute_step(temp_step, context)
            collected = {v: updated.locals[v] for v in outputs if v in updated.locals}
            return ExecutionResult(success=True, value=None, trace=[], errors=[], outputs=collected)
        except Exception as e:
            return ExecutionResult(success=False, value=None, trace=[], errors=[e], outputs={})

    def _is_truthy(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return len(value) > 0
        if isinstance(value, (list, tuple, set)):
            return len(value) > 0
        if isinstance(value, dict):
            return len(value) > 0
        return True

    def _log_error(self, step: DSLNode, message: str, context: ExecutionContext) -> None:
        logger = getattr(self._deps, "logger", None)
        if logger and hasattr(logger, "error"):
            try:
                logger.error(f"Conditional step '{getattr(step, 'name', 'unknown')}' failed: {message}")
            except Exception:
                pass


class DefaultExpressionEvaluator(IExpressionEvaluator):
    """Full DSL expression evaluator supporting literals, variables, binary/unary ops, etc."""

    def evaluate(self, expr: DSLExpression, context: ExecutionContext) -> Any:
        if expr.type == DSLNodeType.LITERAL:
            return getattr(expr, "value", None)
        if expr.type == DSLNodeType.VARIABLE:
            return self._eval_var(getattr(expr, "name", ""), context)
        if expr.type == DSLNodeType.BINARY_OP:
            left, right = self.evaluate(getattr(expr, "left"), context), self.evaluate(getattr(expr, "right"), context)
            return self._bin_op(getattr(expr, "operator", ""), left, right, context)
        if expr.type == DSLNodeType.UNARY_OP:
            op, operand = getattr(expr, "operator", ""), self.evaluate(getattr(expr, "operand"), context)
            return {"!": lambda: not self._is_truthy(operand), "-": lambda: -operand, "+": lambda: +operand}[op]()
        if expr.type == DSLNodeType.PROPERTY_ACCESS:
            obj = self.evaluate(getattr(expr, "object"), context)
            prop = getattr(expr, "property", "")
            if obj is None:
                raise ValueError(f"Cannot access property '{prop}' on None")
            if not isinstance(obj, dict):
                raise ValueError(f"Cannot access property '{prop}' on non-dict")
            if prop not in obj:
                raise ValueError(f"Property '{prop}' not found")
            return obj[prop]
        if expr.type == DSLNodeType.CONDITIONAL_EXPRESSION:
            test = self.evaluate(getattr(expr, "test"), context)
            return self.evaluate(getattr(expr, "consequent"), context) if self._is_truthy(test) else self.evaluate(getattr(expr, "alternate"), context)
        raise ValueError(f"Unsupported expression type: {expr.type}")

    def _eval_var(self, name: str, ctx: ExecutionContext) -> Any:
        cur: ExecutionContext | None = ctx
        while cur:
            if name in cur.locals:
                return cur.locals[name]
            if name in cur.input:
                return cur.input[name]
            cur = cur.parent
        raise ValueError(f"Undefined variable: {name}")

    def _bin_op(self, op: str, left: Any, right: Any, ctx: ExecutionContext) -> Any:
        if op == "+":
            return left + right if isinstance(left, (int, float)) and isinstance(right, (int, float)) else str(left) + str(right)
        tables = {"-": lambda: left - right, "*": lambda: left * right, "/": lambda: left / right, "%": lambda: left % right, "==": lambda: left == right, "!=": lambda: left != right, "<": lambda: left < right, ">": lambda: left > right, "<=": lambda: left <= right, ">=": lambda: left >= right, "&&": lambda: self._is_truthy(left) and self._is_truthy(right), "||": lambda: self._is_truthy(left) or self._is_truthy(right)}
        fn = tables.get(op)
        if fn is None:
            raise ValueError(f"Unknown binary operator: {op}")
        return fn()

    def _is_truthy(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return len(value) > 0
        if isinstance(value, (list, tuple, set)):
            return len(value) > 0
        if isinstance(value, dict):
            return len(value) > 0
        return True
