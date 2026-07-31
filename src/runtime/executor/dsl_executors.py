"""DSL Executors — execute each step type in agent workflows."""

import ast
import asyncio
import operator
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


_ALLOWED_NODES = frozenset(
    {
        ast.Expression,
        ast.Compare,
        ast.BoolOp,
        ast.UnaryOp,
        ast.Not,
        ast.Name,
        ast.Constant,
        ast.Load,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.And,
        ast.Or,
        ast.Not,
        ast.USub,
    }
)

_CMP_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


def _safe_eval(condition: str, context: dict[str, Any]) -> Any:
    """Safely evaluate a boolean condition expression.

    Whitelist-based AST evaluator that only permits:
      - Comparisons (==, !=, <, >, <=, >=)
      - Boolean logic (and, or, not)
      - Variable lookups (Name nodes)
      - Literals (numbers, strings, booleans, None)

    Rejects: function calls, attribute access, subscript, arithmetic, etc.
    """
    tree = ast.parse(condition, mode="eval")
    return _eval_node(tree.body, context)


def _eval_node(node: ast.AST, context: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        if node.id in context:
            return context[node.id]
        raise NameError(f"Name '{node.id}' is not defined")

    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            return not _eval_node(node.operand, context)
        if isinstance(node.op, ast.USub):
            val = _eval_node(node.operand, context)
            if not isinstance(val, (int, float)):
                raise TypeError(f"Unary '-' not supported for {type(val).__name__}")
            return -val
        raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")

    if isinstance(node, ast.BoolOp):
        values = [_eval_node(v, context) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        if isinstance(node.op, ast.Or):
            return any(values)
        raise ValueError(f"Unsupported boolean operator: {type(node.op).__name__}")

    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, context)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator, context)
            op_cls = type(op)
            if op_cls not in _CMP_OPS:
                raise ValueError(f"Unsupported comparison operator: {op_cls.__name__}")
            if not _CMP_OPS[op_cls](left, right):
                return False
            left = right
        return True

    raise ValueError(f"Unsupported expression: {type(node).__name__}")


@dataclass
class ExecutorContext:
    """Context passed to step executors."""

    workflow_id: str = ""
    step_id: str = ""
    params: dict = field(default_factory=dict)
    results: dict = field(default_factory=dict)
    globals: dict = field(default_factory=dict)


@dataclass
class ExecutorResult:
    success: bool
    output: Any = None
    error: str = ""
    next_step: str = ""


class DSLExecutors:
    """Execute each DSL step type with real logic."""

    def __init__(self):
        self._agent_registry: dict[str, Callable] = {}  # type: ignore[annotation-unchecked]
        self._skill_registry: dict[str, Callable] = {}  # type: ignore[annotation-unchecked]
        self._tool_registry: dict[str, Callable] = {}  # type: ignore[annotation-unchecked]

    def register_agent(self, name: str, fn: Callable):
        self._agent_registry[name] = fn

    def register_skill(self, name: str, fn: Callable):
        self._skill_registry[name] = fn

    def register_tool(self, name: str, fn: Callable):
        self._tool_registry[name] = fn

    async def agent_call(
        self, ctx: ExecutorContext, target: str, action: str
    ) -> ExecutorResult:
        """Execute an agent call step."""
        fn = self._agent_registry.get(target)
        if not fn:
            return ExecutorResult(success=False, error=f"Agent not found: {target}")
        try:
            result = fn(ctx)
            if asyncio.iscoroutine(result):
                result = await result
            return ExecutorResult(success=True, output=result)
        except Exception as e:  # noqa: BLE001  # defensive fallback
            return ExecutorResult(success=False, error=str(e))

    async def skill_call(
        self, ctx: ExecutorContext, target: str, action: str
    ) -> ExecutorResult:
        """Execute a skill call step."""
        fn = self._skill_registry.get(target)
        if not fn:
            return ExecutorResult(success=False, error=f"Skill not found: {target}")
        try:
            result = fn(ctx)
            if asyncio.iscoroutine(result):
                result = await result
            return ExecutorResult(success=True, output=result)
        except Exception as e:  # noqa: BLE001  # defensive fallback
            return ExecutorResult(success=False, error=str(e))

    async def tool_call(
        self, ctx: ExecutorContext, target: str, action: str
    ) -> ExecutorResult:
        """Execute a tool call step."""
        fn = self._tool_registry.get(target)
        if not fn:
            return ExecutorResult(success=False, error=f"Tool not found: {target}")
        try:
            result = fn(ctx.params)
            if asyncio.iscoroutine(result):
                result = await result
            return ExecutorResult(success=True, output=result)
        except Exception as e:  # noqa: BLE001  # defensive fallback
            return ExecutorResult(success=False, error=str(e))

    async def conditional(
        self,
        ctx: ExecutorContext,
        condition: str,
        true_step: str = "",
        false_step: str = "",
    ) -> ExecutorResult:
        """Evaluate a condition and route to next step."""
        eval_ctx = {**ctx.globals, **ctx.results}
        try:
            result = _safe_eval(condition, eval_ctx)
            next_s = true_step if result else false_step
            return ExecutorResult(success=True, output=result, next_step=next_s)
        except Exception as e:  # noqa: BLE001  # defensive fallback
            return ExecutorResult(success=False, error=str(e))

    async def loop(
        self,
        ctx: ExecutorContext,
        sub_steps: list,
        max_iterations: int = 10,
        condition: str = "",
    ) -> ExecutorResult:
        """Execute sub-steps in a loop until condition is met."""
        outputs = []
        for i in range(max_iterations):
            if condition:
                eval_ctx = {**ctx.globals, **ctx.results, "loop_index": i}
                try:
                    if not _safe_eval(condition, eval_ctx):
                        break
                except Exception:  # noqa: BLE001  # defensive fallback
                    break
            for step_def in sub_steps:
                step_ctx = ExecutorContext(
                    workflow_id=ctx.workflow_id,
                    step_id=f"{step_def.get('id', 'unknown')}_iter{i}",
                    params=step_def.get("params", {}),
                    results=ctx.results,
                    globals=ctx.globals,
                )
                step_type = step_def.get("type", "agent_call")
                target = step_def.get("target", "")
                action = step_def.get("action", "")
                if step_type == "agent_call":
                    r = await self.agent_call(step_ctx, target, action)
                elif step_type == "tool_call":
                    r = await self.tool_call(step_ctx, target, action)
                else:
                    continue
                outputs.append(r.output)
                ctx.results[step_ctx.step_id] = r
                if not r.success:
                    return ExecutorResult(success=False, output=outputs, error=r.error)
        return ExecutorResult(success=True, output=outputs)

    async def parallel(self, ctx: ExecutorContext, sub_steps: list) -> ExecutorResult:
        """Execute sub-steps in parallel."""

        async def run_step(step_def):
            step_ctx = ExecutorContext(
                workflow_id=ctx.workflow_id,
                step_id=step_def.get("id", "unknown"),
                params=step_def.get("params", {}),
                results=ctx.results,
                globals=ctx.globals,
            )
            step_type = step_def.get("type", "agent_call")
            target = step_def.get("target", "")
            action = step_def.get("action", "")
            if step_type == "agent_call":
                return await self.agent_call(step_ctx, target, action)
            elif step_type == "tool_call":
                return await self.tool_call(step_ctx, target, action)
            elif step_type == "skill_call":
                return await self.skill_call(step_ctx, target, action)
            return ExecutorResult(success=False, error=f"Unknown type: {step_type}")

        tasks = [run_step(s) for s in sub_steps]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        outputs = []
        for r in results:
            if isinstance(r, ExecutorResult):
                outputs.append(r.output)
            else:
                outputs.append(str(r))
        return ExecutorResult(success=True, output=outputs)

    async def try_catch(
        self,
        ctx: ExecutorContext,
        try_step: dict,
        catch_step: dict | None = None,
        finally_step: dict | None = None,
    ) -> ExecutorResult:
        """Execute a try-catch pattern."""
        try:
            result = await self._execute_substep(ctx, try_step)
            return result
        except Exception as e:  # noqa: BLE001  # defensive fallback
            if catch_step:
                catch_ctx = ExecutorContext(
                    workflow_id=ctx.workflow_id,
                    step_id=catch_step.get("id", "catch"),
                    params=catch_step.get("params", {}),
                    results=ctx.results,
                    globals=ctx.globals,
                )
                return await self._execute_substep(catch_ctx, catch_step)
            return ExecutorResult(success=False, error=str(e))
        finally:
            if finally_step:
                fin_ctx = ExecutorContext(
                    workflow_id=ctx.workflow_id,
                    step_id=finally_step.get("id", "finally"),
                    params=finally_step.get("params", {}),
                    results=ctx.results,
                    globals=ctx.globals,
                )
                await self._execute_substep(fin_ctx, finally_step)

    async def _execute_substep(
        self, ctx: ExecutorContext, step_def: dict
    ) -> ExecutorResult:
        step_type = step_def.get("type", "agent_call")
        target = step_def.get("target", "")
        action = step_def.get("action", "")
        if step_type == "agent_call":
            return await self.agent_call(ctx, target, action)
        elif step_type == "tool_call":
            return await self.tool_call(ctx, target, action)
        elif step_type == "skill_call":
            return await self.skill_call(ctx, target, action)
        elif step_type == "conditional":
            return await self.conditional(ctx, step_def.get("condition", ""))
        return ExecutorResult(success=False, error=f"Unknown step type: {step_type}")
