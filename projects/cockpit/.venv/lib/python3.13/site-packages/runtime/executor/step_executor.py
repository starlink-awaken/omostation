"""Step execution engine for DSL workflow steps."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from runtime.executor.dsl_types import (  # type: ignore[attr-defined]
    CallConfig,
    CallResult,
    CallTrace,
    ExecutionContext,
    ExecutionDependencies,
    RetryConfig,
    TraceEntry,
)


class OutputMappingFailedError(Exception):
    def __init__(
        self,
        target_variable: str,
        source_path: str,
        message: str = "",
        original_error: Exception | None = None,
    ) -> None:
        self.target_variable = target_variable
        self.source_path = source_path
        self.original_error = original_error
        super().__init__(message or f"Failed to map output '{source_path}' to '{target_variable}'")


class IExpressionEvaluator:
    def evaluate(self, expr: Any, context: ExecutionContext) -> Any:
        raise NotImplementedError


class IStepExecutor:
    async def execute_step(
        self, step: Any, context: ExecutionContext
    ) -> ExecutionContext:
        raise NotImplementedError


class ICallExecutor:
    async def execute(self, config: CallConfig, context: ExecutionContext) -> CallResult:
        raise NotImplementedError

    def validate(self, config: CallConfig) -> list[str]:
        raise NotImplementedError


class StepExecutor:
    def __init__(
        self,
        dependencies: ExecutionDependencies,
        expression_evaluator: IExpressionEvaluator,
        agent_executor: ICallExecutor,
        skill_executor: ICallExecutor,
        tool_executor: ICallExecutor | None = None,
        resolve_variable_fn: Callable | None = None,
    ) -> None:
        self._deps = dependencies
        self._expr_eval = expression_evaluator
        self._agent_exec = agent_executor
        self._skill_exec = skill_executor
        self._tool_exec = tool_executor
        self._resolve = resolve_variable_fn or self._default_resolve

    def _default_resolve(self, name: str, context: ExecutionContext) -> Any:
        if name in context.locals:
            return context.locals[name]
        if name in context.results:
            return context.results[name]
        if name in context.input:
            return context.input[name]
        if context.parent:
            return self._default_resolve(name, context.parent)
        raise ValueError(f"Undefined variable: {name}")

    async def execute_step(self, step: Any, context: ExecutionContext) -> ExecutionContext:
        step_name = getattr(step, "name", None) or "anonymous"
        start_time = time.time()

        try:
            if not step.call:
                raise ValueError(f"Step '{step_name}' has no call configuration")

            resolved_inputs = self._resolve_inputs(step, context)
            call_config = self._build_call_config(step, resolved_inputs)
            call_result = await self._execute_call(call_config, context)

            if call_result.success and hasattr(step, "outputs") and step.outputs:
                await self._map_outputs(step.outputs, call_result, context)

            self._update_context(context, call_result, step_name)
            self._record_trace(step_name, call_config, call_result, start_time, context)

            return context
        except Exception as error:
            duration_ms = (time.time() - start_time) * 1000
            call_type = getattr(step.call, "type", "agent") if step.call else "agent"
            target = self._get_call_target(step.call) if step.call else "unknown"
            CallTrace(
                trace_id=context.trace_id,
                step_name=step_name,
                call_type=call_type,
                target=target,
                start_time=start_time,
                end_time=time.time(),
                duration_ms=duration_ms,
                success=False,
                error=str(error),
                retry_count=0,
            )
            self._log_error(step, error, context)
            raise

    def _get_call_target(self, call: Any) -> str:
        if not call:
            return "unknown"
        if hasattr(call, "name") and call.name:
            return call.name
        if hasattr(call, "skill_id") and call.skill_id:
            return call.skill_id
        return "unknown"

    def _resolve_inputs(self, step: Any, context: ExecutionContext) -> dict[str, Any]:
        resolved: dict[str, Any] = {}
        inputs = getattr(step, "inputs", None) or {}
        for key, expr in inputs.items():
            try:
                resolved[key] = self._expr_eval.evaluate(expr, context)
            except Exception as e:
                raise ValueError(f"Failed to resolve input '{key}': {e}") from e
        return resolved

    def _build_call_config(self, step: Any, resolved_inputs: dict[str, Any]) -> CallConfig:
        call = step.call
        if not call:
            raise ValueError("Step has no call")
        ctype = getattr(call, "type", "agent") or "agent"
        config = CallConfig(type=ctype)
        if ctype in ("agent", "tool"):
            config.name = getattr(call, "name", "") or ""
        elif ctype == "skill":
            config.skill_id = getattr(call, "skill_id", "") or ""
        config.inputs = getattr(step, "inputs", {}) or {}
        config.outputs = getattr(step, "outputs", {}) or {}
        retry = getattr(step, "retry", None)
        if retry:
            config.retry = RetryConfig(
                max_retries=getattr(retry, "max_attempts", 3),
                base_delay_ms=getattr(retry, "backoff_ms", 1000),
            )
        return config

    async def _execute_call(self, config: CallConfig, context: ExecutionContext) -> CallResult:
        if config.type == "agent":
            return await self._agent_exec.execute(config, context)
        elif config.type == "skill":
            return await self._skill_exec.execute(config, context)
        elif config.type == "tool":
            if not self._tool_exec:
                raise ValueError("Tool executor not configured")
            return await self._tool_exec.execute(config, context)
        raise ValueError(f"Unsupported call type: {config.type}")

    async def _map_outputs(
        self, outputs: dict[str, str], call_result: CallResult, context: ExecutionContext
    ) -> None:
        if not call_result.success or call_result.data is None:
            return
        data = call_result.data if isinstance(call_result.data, dict) else {}
        for target_var, source_path in outputs.items():
            try:
                value = self._get_nested_property(data, source_path)
                context.locals[target_var] = value
                if call_result.outputs is None:
                    call_result.outputs = {}
                call_result.outputs[target_var] = value
            except Exception as e:
                raise OutputMappingFailedError(
                    target_var, source_path, str(e), e
                ) from e

    def _get_nested_property(self, obj: Any, path: str) -> Any:
        if obj is None:
            raise ValueError(f"Cannot access property '{path}' on null")
        parts = path.replace("[", ".").replace("]", "").split(".")
        parts = [p for p in parts if p]
        current = obj
        for part in parts:
            if current is None:
                raise ValueError(f"Cannot access property '{part}' on null")
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif isinstance(current, (list, tuple)):
                try:
                    idx = int(part)
                    current = current[idx]
                except (ValueError, IndexError):
                    raise ValueError(f"Invalid index '{part}'")
            else:
                raise ValueError(f"Property '{part}' not found")
        return current

    def _update_context(self, context: ExecutionContext, result: CallResult, step_name: str) -> None:
        if result.success:
            context.stats.successful_calls += 1
        else:
            context.stats.failed_calls += 1
        context.stats.total_duration_ms += result.duration_ms
        if result.tokens_used:
            context.stats.total_tokens += result.tokens_used
        context.results[step_name] = result

    def _record_trace(
        self, step_name: str, config: CallConfig, result: CallResult,
        start_time: float, context: ExecutionContext,
    ) -> None:
        _ = TraceEntry(
            timestamp=time.time(),
            statement_type="step",
            status="success" if result.success else "failure",
            data={"step": step_name, "call_type": config.type},
        )

    def _log_error(self, step: Any, error: Exception, context: ExecutionContext) -> None:
        step_name = getattr(step, "name", None) or "anonymous"
        logger = getattr(self._deps, "logger", None)
        if logger and hasattr(logger, "error"):
            try:
                self._deps.logger.error(f"Step '{step_name}' failed: {error}")
            except Exception:
                pass


class DefaultExpressionEvaluator(IExpressionEvaluator):
    def evaluate(self, expr: Any, context: ExecutionContext) -> Any:
        if expr is None:
            return None
        if isinstance(expr, (str, int, float, bool)):
            return expr
        if isinstance(expr, dict):
            expr_type = expr.get("type", "")
            if expr_type == "literal":
                return expr.get("value")
            elif expr_type == "variable":
                return self._resolve_variable(expr["name"], context)
        return expr

    def _resolve_variable(self, name: str, context: ExecutionContext) -> Any:
        if name in context.locals:
            return context.locals[name]
        if name in context.results:
            return context.results[name]
        if name in context.input:
            return context.input[name]
        if context.parent:
            return self._resolve_variable(name, context.parent)
        raise ValueError(f"Undefined variable: {name}")


class ExecutionDependencies:  # type: ignore[no-redef]  # noqa: F811
    def __init__(
        self,
        agent_runner: Any = None,
        skills_manager: Any = None,
        message_bus: Any = None,
        logger: Any = None,
        tracer: Any = None,
    ) -> None:
        self.agent_runner = agent_runner
        self.skills_manager = skills_manager
        self.message_bus = message_bus
        self.logger = logger
        self.tracer = tracer
