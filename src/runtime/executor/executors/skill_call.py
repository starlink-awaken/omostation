from __future__ import annotations

import asyncio
import random
import time
from typing import Any

from runtime.executor.dsl_types import CallConfig, CallResult, ExecutionContext, RetryConfig
from runtime.executor.step_executor import ExecutionDependencies, ICallExecutor

DEFAULT_TIMEOUT_MS = 30000
DEFAULT_RETRY_MAX = 3
DEFAULT_RETRY_BASE = 1000
DEFAULT_RETRY_MAX_DELAY = 10000
DEFAULT_RETRY_MULTIPLIER = 2.0
DEFAULT_JITTER = True
DEFAULT_MAX_DEPTH = 100


class SkillNotFoundError(Exception):
    def __init__(self, skill_id: str) -> None:
        self.skill_id = skill_id
        super().__init__(f"Skill not found: {skill_id}")


class SkillTimeoutError(Exception):
    def __init__(self, skill_id: str, timeout_ms: int) -> None:
        self.skill_id = skill_id
        self.timeout_ms = timeout_ms
        super().__init__(f"Skill '{skill_id}' timed out after {timeout_ms}ms")


class SkillInvalidInputError(Exception):
    def __init__(self, skill_id: str, validation_errors: list[str]) -> None:
        self.skill_id = skill_id
        self.validation_errors = validation_errors
        super().__init__(f"Invalid input for skill '{skill_id}': {', '.join(validation_errors)}")


class SkillExecutionFailedError(Exception):
    def __init__(self, skill_id: str, original_error: Exception | str) -> None:
        self.skill_id = skill_id
        self.original_error = original_error
        msg = str(original_error) if isinstance(original_error, Exception) else original_error
        super().__init__(f"Skill '{skill_id}' execution failed: {msg}")


def _calc_skill_backoff(attempt: int, retry: RetryConfig) -> int:
    base = retry.base_delay_ms or DEFAULT_RETRY_BASE
    max_delay = retry.max_delay_ms or DEFAULT_RETRY_MAX_DELAY
    mult = retry.backoff_multiplier or DEFAULT_RETRY_MULTIPLIER
    jitter = retry.jitter if retry.jitter is not None else DEFAULT_JITTER
    delay = min(base * (mult**attempt), max_delay)
    if jitter:
        delay = delay * (0.5 + random.random() * 0.5)  # noqa: S311
    return int(delay)


async def _skill_with_timeout(coro, timeout_ms: int, skill_id: str):
    try:
        return await asyncio.wait_for(coro, timeout=timeout_ms / 1000)
    except TimeoutError as exc:
        raise SkillTimeoutError(skill_id, timeout_ms) from exc


class SkillCallExecutor(ICallExecutor):
    """Executes skill calls with timeout, retry, and result mapping."""

    def __init__(self, dependencies: ExecutionDependencies, default_timeout_ms: int = DEFAULT_TIMEOUT_MS, max_depth: int = DEFAULT_MAX_DEPTH) -> None:
        self._deps = dependencies
        self._default_timeout = default_timeout_ms
        self._max_depth = max_depth

    async def execute(self, config: CallConfig, context: ExecutionContext) -> CallResult:
        if config.type != "skill":
            raise ValueError(f"Invalid config type for SkillCallExecutor: {config.type}")
        errors = self.validate(config)
        if errors:
            raise SkillInvalidInputError(config.skill_id, errors)
        if context.depth >= self._max_depth:
            raise ValueError(f"Maximum nesting depth ({self._max_depth}) exceeded")
        start_time = time.time()
        last_error: Exception | None = None
        retry_cfg = config.retry or RetryConfig()
        max_retries = retry_cfg.max_retries or DEFAULT_RETRY_MAX
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    await asyncio.sleep(_calc_skill_backoff(attempt, retry_cfg) / 1000)
                result = await self._execute_skill(config, context)
                context.stats.skill_calls += 1
                context.stats.total_duration_ms += result.duration_ms
                if result.tokens_used:
                    context.stats.total_tokens += result.tokens_used
                if result.success:
                    context.stats.successful_calls += 1
                return result
            except (SkillNotFoundError, SkillInvalidInputError):
                raise
            except Exception as exc:
                last_error = exc
                if attempt >= max_retries:
                    break
        context.stats.skill_calls += 1
        context.stats.failed_calls += 1
        context.stats.total_duration_ms += (time.time() - start_time) * 1000
        raise SkillExecutionFailedError(config.skill_id, last_error or "Execution failed after retries")

    def validate(self, config: CallConfig) -> list[str]:
        errors: list[str] = []
        if config.type != "skill":
            errors.append(f"Expected type 'skill', got '{config.type}'")
        if not config.skill_id or not isinstance(config.skill_id, str):
            errors.append("skill_id is required and must be a string")
        return errors

    async def _execute_skill(self, config: CallConfig, context: ExecutionContext) -> CallResult:
        start_time = time.time()
        mgr = self._deps.skills_manager
        if not mgr:
            raise ValueError("SkillsManager not available")
        if not await mgr.has_skill(config.skill_id):
            raise SkillNotFoundError(config.skill_id)
        resolved = await self._resolve_inputs(config.inputs, context)
        timeout_ms = config.timeout or self._default_timeout
        exec_result = await _skill_with_timeout(mgr.execute_skill(config.skill_id, resolved), timeout_ms, config.skill_id)
        duration_ms = (time.time() - start_time) * 1000
        outputs = self._apply_output_mapping(exec_result, config.outputs) if hasattr(exec_result, "output") else {}
        result = CallResult(
            success=getattr(exec_result, "status", None) == "completed",
            data=getattr(exec_result, "output", None),
            duration_ms=duration_ms,
            tokens_used=getattr(exec_result, "token_usage", 0) or 0,
            retry_count=0,
            outputs=outputs,
        )
        if not result.success and hasattr(exec_result, "error") and exec_result.error:
            result.error = str(exec_result.error)
        return result

    async def _resolve_inputs(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        resolved: dict[str, Any] = {}
        for key, value in inputs.items():
            if isinstance(value, str) and value.startswith("$"):
                var_name = value.lstrip("${").rstrip("}")
                try:
                    resolved[key] = self._resolve_variable_value(var_name, context)
                except (KeyError, ValueError):
                    resolved[key] = value
            else:
                resolved[key] = value
        return resolved

    def _apply_output_mapping(self, result: Any, output_mapping: dict[str, str] | None) -> dict[str, Any]:
        if not output_mapping:
            return {}
        output = getattr(result, "output", None) if not isinstance(result, dict) else result.get("output")
        if not isinstance(output, dict):
            return {}
        return {target: output.get(source, None) for source, target in output_mapping.items()}

    def _resolve_variable_value(self, ref: str, context: ExecutionContext) -> Any:
        if ref in context.locals:
            return context.locals[ref]
        if ref in context.results:
            return context.results[ref]
        if ref in context.input:
            return context.input[ref]
        if context.parent:
            return self._resolve_variable_value(ref, context.parent)
        raise ValueError(f"Undefined variable: {ref}")
