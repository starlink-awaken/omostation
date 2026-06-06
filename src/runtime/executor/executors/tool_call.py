from __future__ import annotations

import asyncio
import random
import time
from typing import Any

from runtime.executor.dsl_types import (
    CallConfig,
    CallResult,
    DSLExpression,
    DSLNodeType,
    ExecutionContext,
    RetryConfig,
)
from runtime.executor.step_executor import ICallExecutor

DEFAULT_TIMEOUT_MS = 30000
DEFAULT_RETRY: RetryConfig = RetryConfig(max_retries=3, base_delay_ms=1000, max_delay_ms=10000, backoff_multiplier=2.0, jitter=True)
MAX_DEPTH = 100


def _calc_tool_backoff(attempt: int, rc: RetryConfig) -> int:
    base = rc.base_delay_ms or DEFAULT_RETRY.base_delay_ms
    max_delay = rc.max_delay_ms or DEFAULT_RETRY.max_delay_ms
    mult = rc.backoff_multiplier or DEFAULT_RETRY.backoff_multiplier
    jitter = rc.jitter if rc.jitter is not None else DEFAULT_RETRY.jitter
    delay = min(base * (mult**attempt), max_delay)
    if jitter:
        jitter_range = delay * 0.25
        delay = delay - jitter_range + random.random() * jitter_range * 2  # noqa: S311
    return int(delay)


async def _tool_with_timeout(coro, timeout_ms: int, tool_name: str):
    try:
        return await asyncio.wait_for(coro, timeout=timeout_ms / 1000)
    except TimeoutError as exc:
        raise TimeoutError(f"Tool '{tool_name}' timed out after {timeout_ms}ms") from exc


def _eval_expr(expr: DSLExpression, ctx: ExecutionContext) -> Any:
    if expr.type == DSLNodeType.LITERAL:
        return expr.value  # type: ignore[attr-defined]
    if expr.type == DSLNodeType.VARIABLE:
        name = expr.name  # type: ignore[attr-defined]
        cur: ExecutionContext | None = ctx
        while cur:
            if name in cur.locals:
                return cur.locals[name]
            if name in cur.results:
                return cur.results[name]
            if name in cur.input:
                return cur.input[name]
            cur = cur.parent
        raise ValueError(f"Undefined variable: {name}")
    if expr.type == DSLNodeType.BINARY_OP:
        lv, rv = _eval_expr(expr.left, ctx), _eval_expr(expr.right, ctx)  # type: ignore[attr-defined]
        ops = {"+": lambda: lv + rv, "-": lambda: lv - rv, "*": lambda: lv * rv, "/": lambda: lv / rv, "%": lambda: lv % rv, "==": lambda: lv == rv, "!=": lambda: lv != rv, "<": lambda: lv < rv, ">": lambda: lv > rv, "<=": lambda: lv <= rv, ">=": lambda: lv >= rv, "&&": lambda: bool(lv and rv), "||": lambda: lv or rv}
        return ops[expr.operator]()  # type: ignore[attr-defined]
    if expr.type == DSLNodeType.UNARY_OP:
        o = _eval_expr(expr.operand, ctx)  # type: ignore[attr-defined]
        return {"!": lambda: not o, "-": lambda: -o, "+": lambda: +o}[expr.operator]()  # type: ignore[attr-defined]
    if expr.type == DSLNodeType.PROPERTY_ACCESS:
        obj = _eval_expr(expr.object, ctx)  # type: ignore[attr-defined]
        if isinstance(obj, dict):
            return obj.get(expr.property)  # type: ignore[attr-defined]
        return getattr(obj, expr.property, None)  # type: ignore[attr-defined]
    if expr.type == DSLNodeType.ARRAY_LITERAL:
        return [_eval_expr(e, ctx) for e in expr.elements]  # type: ignore[attr-defined]
    if expr.type == DSLNodeType.TEMPLATE_STRING:
        return "".join(str(_eval_expr(p, ctx)) if not isinstance(p, str) else p for p in expr.parts)  # type: ignore[attr-defined]
    if expr.type == DSLNodeType.CONDITIONAL_EXPRESSION:
        return _eval_expr(expr.consequent, ctx) if _eval_expr(expr.test, ctx) else _eval_expr(expr.alternate, ctx)  # type: ignore[attr-defined]
    raise ValueError(f"Unsupported expression type: {expr.type}")


def _apply_tool_output(raw: Any, outputs: dict[str, str] | None) -> dict[str, Any]:
    if not outputs:
        return {"result": raw}
    if raw is None:
        return {k: None for k in outputs}
    if not isinstance(raw, dict):
        return {k: raw for k in outputs}
    mapped: dict[str, Any] = {}
    for target_key, source_path in outputs.items():
        if not source_path:
            mapped[target_key] = raw
        else:
            value: Any = raw
            for part in source_path.split("."):
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    value = None
                    break
            mapped[target_key] = value
    return mapped


class ToolCallExecutor(ICallExecutor):
    """Executes tool calls via skills system with timeout, retry, and expression resolution."""

    def __init__(self, agent_runner: Any, default_timeout: int = DEFAULT_TIMEOUT_MS, verbose: bool = False) -> None:
        self._agent_runner = agent_runner
        self._default_timeout = default_timeout
        self._verbose = verbose

    async def execute(self, config: CallConfig, context: ExecutionContext) -> CallResult:  # type: ignore[return]
        if config.type != "tool":
            return CallResult(success=False, error=f"Expected 'tool', got '{config.type}'", duration_ms=0.0, retry_count=0)
        if context.depth >= MAX_DEPTH:
            return CallResult(success=False, error=f"Max depth ({MAX_DEPTH}) exceeded", duration_ms=0.0, retry_count=0)
        start_time = time.time()
        rc = config.retry or DEFAULT_RETRY
        max_retries = rc.max_retries or DEFAULT_RETRY.max_retries
        resolved = self._resolve_inputs(config.inputs, context)
        for attempt in range(max_retries + 1):
            try:
                result = await self._execute_once(config, resolved, context)
                outputs = _apply_tool_output(result.get("output"), config.outputs)
                return CallResult(success=True, data=result.get("output"), duration_ms=(time.time() - start_time) * 1000, tokens_used=result.get("tokens_used", 0), retry_count=attempt, outputs=outputs)
            except Exception as exc:
                if attempt < max_retries and self._should_retry(exc):
                    await asyncio.sleep(_calc_tool_backoff(attempt, rc) / 1000)
                    continue
                return CallResult(success=False, error=str(exc), duration_ms=(time.time() - start_time) * 1000, retry_count=attempt)

    def validate(self, config: CallConfig) -> list[str]:
        errors: list[str] = []
        if not config.name or not isinstance(config.name, str):
            errors.append("Tool name must be a non-empty string")
        return errors

    async def _execute_once(self, config: CallConfig, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        timeout = config.timeout or self._default_timeout
        result = await _tool_with_timeout(self._agent_runner.execute_skill(skill_id=config.name, input=inputs, timeout=timeout), timeout, config.name)
        if not result.get("success"):
            raise RuntimeError(result.get("error", f"Tool '{config.name}' failed"))
        return result

    def _resolve_inputs(self, inputs: dict[str, DSLExpression], context: ExecutionContext) -> dict[str, Any]:
        resolved: dict[str, Any] = {}
        for key, expr in inputs.items():
            try:
                resolved[key] = _eval_expr(expr, context) if isinstance(expr, DSLExpression) else expr
            except Exception as e:
                raise ValueError(f"Failed to resolve input '{key}': {e}") from e
        return resolved

    def _should_retry(self, error: Exception) -> bool:
        msg = str(error).lower()
        return any(k in msg for k in ("timeout", "timed out", "econnrefused", "econnreset", "etimedout", "network", "temporary", "try again"))
