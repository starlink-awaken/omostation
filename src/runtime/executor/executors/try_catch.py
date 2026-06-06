from __future__ import annotations

import time
from typing import Any

from runtime.executor.dsl_types import DSLTryCatch, ExecutionContext, ExecutionResult, TraceEntry
from runtime.executor.step_executor import ExecutionDependencies

DEFAULT_MAX_NESTING = 100
DEFAULT_ENABLE_TRACING = True


class IStatementExecutor:
    """Interface for executing nested DSL statements."""

    async def execute_statement(self, stmt: Any, context: ExecutionContext) -> ExecutionResult:
        raise NotImplementedError


class TryCatchExecutor:
    """Executes try-catch-finally blocks for DSL workflow error handling."""

    def __init__(
        self,
        dependencies: ExecutionDependencies,
        statement_executor: IStatementExecutor,
        max_nesting_depth: int = DEFAULT_MAX_NESTING,
        enable_tracing: bool = DEFAULT_ENABLE_TRACING,
    ) -> None:
        self._deps = dependencies
        self._stmt_exec = statement_executor
        self._max_nesting = max_nesting_depth
        self._enable_tracing = enable_tracing

    async def execute(self, stmt: DSLTryCatch, context: ExecutionContext) -> ExecutionResult:
        errors: list[Exception] = []
        trace: list[TraceEntry] = []
        caught_error: Exception | None = None

        child_ctx = ExecutionContext(
            input=context.input.copy(),
            locals={},
            results={},
            trace_id=context.trace_id,
            parent=context,
            depth=(context.depth or 0) + 1,
            options=context.options,
            trace=[],
        )

        if child_ctx.depth >= self._max_nesting:
            err = ValueError(f"Max nesting depth ({self._max_nesting}) exceeded")
            return ExecutionResult(success=False, value=None, trace=[], errors=[err])

        # 1. Execute try_block
        try:
            for try_stmt in stmt.try_block:
                result = await self._stmt_exec.execute_statement(try_stmt, child_ctx)
                trace.extend(getattr(result, "trace", []) or [])
                errors.extend(getattr(result, "errors", []) or [])
        except Exception as exc:
            caught_error = exc
            errors.append(caught_error)
            if self._enable_tracing:
                trace.append(TraceEntry(
                    timestamp=time.time(), statement_type="try_catch", status="failure",
                    data={"phase": "try", "has_catch": bool(stmt.catch_block), "has_finally": bool(stmt.finally_block)},
                ))

        # 2. Execute catch_block
        if stmt.catch_block:
            if stmt.catch_variable:
                child_ctx.locals[stmt.catch_variable] = caught_error
            for catch_stmt in stmt.catch_block:
                try:
                    result = await self._stmt_exec.execute_statement(catch_stmt, child_ctx)
                    trace.extend(getattr(result, "trace", []) or [])
                    errors.extend(getattr(result, "errors", []) or [])
                except Exception as exc:
                    errors.append(exc)

        # 3. Execute finally_block
        finally_error: Exception | None = None
        if stmt.finally_block:
            for finally_stmt in stmt.finally_block:
                try:
                    result = await self._stmt_exec.execute_statement(finally_stmt, child_ctx)
                    trace.extend(getattr(result, "trace", []) or [])
                    errors.extend(getattr(result, "errors", []) or [])
                except Exception as exc:
                    errors.append(exc)
                    finally_error = exc

        # Determine success
        if stmt.catch_block:
            if caught_error and caught_error in errors:
                errors.remove(caught_error)
            success = not finally_error
        else:
            success = not caught_error and not finally_error

        if self._enable_tracing:
            trace.append(TraceEntry(
                timestamp=time.time(), statement_type="try_catch", status="success" if success else "failure",
                data={"caught": caught_error is not None, "has_catch": bool(stmt.catch_block), "has_finally": bool(stmt.finally_block)},
            ))

        return ExecutionResult(success=success, value=None, trace=trace, errors=errors if errors else [])
