from __future__ import annotations

import asyncio
import random
import time
from typing import Any

from runtime.executor.dsl_types import CallConfig, CallResult, ExecutionContext, RetryConfig
from runtime.executor.step_executor import ExecutionDependencies, ICallExecutor

DEFAULT_TIMEOUT_MS = 300000
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY_MS = 1000
DEFAULT_MAX_DELAY_MS = 30000
DEFAULT_BACKOFF_MULTIPLIER = 2.0
DEFAULT_JITTER = True


class AgentCallError(Exception):
    pass


def _calc_agent_backoff(attempt: int, config: RetryConfig) -> int:
    base = config.base_delay_ms or DEFAULT_BASE_DELAY_MS
    max_delay = config.max_delay_ms or DEFAULT_MAX_DELAY_MS
    mult = config.backoff_multiplier or DEFAULT_BACKOFF_MULTIPLIER
    jitter = config.jitter if config.jitter is not None else DEFAULT_JITTER
    delay = min(base * (mult**attempt), max_delay)
    if jitter:
        jitter_range = delay * 0.25
        delay = delay - jitter_range + random.random() * jitter_range * 2  # noqa: S311
    return max(0, int(delay))


async def _agent_with_timeout(coro, timeout_ms: int, name: str):
    try:
        return await asyncio.wait_for(coro, timeout=timeout_ms / 1000)
    except TimeoutError as exc:
        raise AgentCallError(f"Agent '{name}' timed out after {timeout_ms}ms") from exc


class AgentCallExecutor(ICallExecutor):
    """Executes agent calls via AgentRunner with timeout, retry, and result mapping."""

    def __init__(self, dependencies: ExecutionDependencies) -> None:
        self._agent_runner = dependencies.agent_runner
        self._tracer = dependencies.tracer
        self._logger = dependencies.logger

    async def execute(self, config: CallConfig, context: ExecutionContext) -> CallResult:
        errors = self.validate(config)
        if errors:
            raise AgentCallError(f"Validation failed: {', '.join(errors)}")
        start_time = time.time()
        rc = config.retry or RetryConfig()
        max_retries = rc.max_retries if rc.max_retries is not None else DEFAULT_MAX_RETRIES
        agent_def = await self._get_agent(config.name)
        resolved_inputs = await self._resolve_inputs(config.inputs, context)
        task_str = f"Execute agent: {config.name}\nInputs: {resolved_inputs}"
        for attempt in range(max_retries + 1):
            try:
                timeout = config.timeout or DEFAULT_TIMEOUT_MS
                agent_state = await _agent_with_timeout(self._agent_runner.run_agent(agent_def, task_str, ""), timeout, config.name)
                outputs = self._process_outputs(config.outputs, agent_state)
                duration_ms = (time.time() - start_time) * 1000
                result = CallResult(
                    success=getattr(agent_state, "status", "") in ("completed", "COMPLETED"),
                    data=getattr(agent_state, "output", None),
                    duration_ms=duration_ms,
                    tokens_used=getattr(agent_state, "token_usage", 0) or 0,
                    retry_count=attempt,
                    outputs=outputs,
                )
                context.results[config.name] = result.data
                context.stats.agent_calls += 1
                context.stats.total_tokens += result.tokens_used
                context.stats.total_duration_ms += result.duration_ms
                if result.success:
                    context.stats.successful_calls += 1
                return result
            except AgentCallError:
                raise
            except Exception as exc:
                if attempt >= max_retries:
                    raise AgentCallError(f"Agent '{config.name}' failed after {max_retries} retries") from exc
                await asyncio.sleep(_calc_agent_backoff(attempt, rc) / 1000)
        raise AgentCallError(f"Agent '{config.name}' failed: unknown error")

    def validate(self, config: CallConfig) -> list[str]:
        errors: list[str] = []
        if not config.name or not isinstance(config.name, str):
            errors.append("Agent name must be a non-empty string")
        return errors

    async def _get_agent(self, name: str) -> Any:
        pool = getattr(self._agent_runner, "get_pool", lambda: None)()
        if pool:
            agent = getattr(pool, "get_agent", lambda n: None)(name)
            if agent:
                return agent
        raise AgentCallError(f"Agent '{name}' not found")

    async def _resolve_inputs(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        resolved: dict[str, Any] = {}
        for key, value in inputs.items():
            if isinstance(value, str) and value.startswith("$"):
                try:
                    resolved[key] = self._resolve_var(value[1:], context)
                except (ValueError, KeyError):
                    resolved[key] = value
            else:
                resolved[key] = value
        return resolved

    def _resolve_var(self, name: str, context: ExecutionContext) -> Any:
        if name in context.locals:
            return context.locals[name]
        if name in context.results:
            return context.results[name]
        if name in context.input:
            return context.input[name]
        if context.parent:
            return self._resolve_var(name, context.parent)
        raise ValueError(f"Undefined variable: {name}")

    def _process_outputs(self, outputs: dict[str, str] | None, state: Any) -> dict[str, Any]:
        result: dict[str, Any] = {}
        output = getattr(state, "output", None) if not isinstance(state, dict) else state.get("output")
        if not outputs:
            result["output"] = output
            return result
        for target_key, source_path in outputs.items():
            if source_path in ("output", "."):
                result[target_key] = output
            elif source_path.startswith("output."):
                result[target_key] = self._get_prop(output, source_path[7:])
            else:
                result[target_key] = self._get_prop(state, source_path)
        return result

    def _get_prop(self, obj: Any, path: str) -> Any:
        for part in path.split("."):
            if isinstance(obj, dict) and part in obj:
                obj = obj[part]
            elif hasattr(obj, part):
                obj = getattr(obj, part)
            else:
                return None
        return obj
