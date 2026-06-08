from __future__ import annotations

import asyncio
import time
from typing import Any

from runtime.executor.dsl_types import (
    DSLNode as DSLStatement,
)
from runtime.executor.dsl_types import (
    DSLParallel,
    ExecutionContext,
    ExecutionResult,
    TraceEntry,
)
from runtime.executor.step_executor import ExecutionDependencies

DEFAULT_MAX_NESTING = 100
DEFAULT_ENABLE_TRACING = True
DEFAULT_ENABLE_LOGGING = False


class IStatementExecutor:
    """Interface for executing DSL statements."""

    async def execute_statement(self, stmt: DSLStatement, context: ExecutionContext) -> ExecutionResult:
        raise NotImplementedError


class ParallelExecutor:
    """Executes parallel branches concurrently with optional concurrency limiting."""

    def __init__(
        self,
        dependencies: ExecutionDependencies,
        statement_executor: IStatementExecutor,
        max_nesting_depth: int = DEFAULT_MAX_NESTING,
        enable_tracing: bool = DEFAULT_ENABLE_TRACING,
        enable_logging: bool = DEFAULT_ENABLE_LOGGING,
    ) -> None:
        self._deps = dependencies
        self._stmt_exec = statement_executor
        self._max_nesting = max_nesting_depth
        self._enable_tracing = enable_tracing
        self._enable_logging = enable_logging

    async def execute(self, stmt: DSLParallel, context: ExecutionContext) -> ExecutionResult:
        start_time = time.time()
        errors: list[Exception] = []
        trace: list[TraceEntry] = []
        current_depth = context.depth or 0
        if current_depth >= self._max_nesting:
            err = ValueError(f"Max nesting depth ({self._max_nesting}) exceeded")
            return ExecutionResult(success=False, value=None, trace=self._make_trace(stmt, start_time, "failure", errors), errors=[err])

        max_concurrency = self._resolve_max_concurrency(stmt)
        results = await self._execute_branches(stmt.branches, context, max_concurrency, current_depth + 1)

        for result in results:
            trace.extend(getattr(result, "trace", []))
            errors.extend(getattr(result, "errors", []))

        if self._enable_tracing:
            trace.append(TraceEntry(
                timestamp=time.time(), statement_type="parallel", status="failure" if errors else "success",
                data={"branch_count": len(stmt.branches), "max_concurrency": max_concurrency, "failure_count": sum(1 for r in results if not r.success)},
            ))

        return ExecutionResult(success=len(errors) == 0, value=None, trace=trace, errors=errors)

    def _resolve_max_concurrency(self, stmt: DSLParallel) -> int | None:
        return stmt.max_concurrency

    async def _execute_branches(self, branches: list[list[DSLStatement]], parent_ctx: ExecutionContext, max_concurrency: int | None, new_depth: int) -> list[ExecutionResult]:
        if not branches:
            return [ExecutionResult(success=True, value=None, trace=[], errors=[])]

        async def _exec_branch(branch: list[DSLStatement], _index: int) -> ExecutionResult:
            ctx = ExecutionContext(
                input=parent_ctx.input.copy(), locals={}, results={}, trace_id=parent_ctx.trace_id,
                parent=parent_ctx, depth=new_depth, trace=[], options=parent_ctx.options,
            )
            branch_errors: list[Exception] = []
            branch_trace: list[TraceEntry] = []
            for stmt in branch:
                try:
                    result = await self._stmt_exec.execute_statement(stmt, ctx)
                    branch_trace.extend(getattr(result, "trace", []))
                    branch_errors.extend(getattr(result, "errors", []))
                except Exception as e:
                    branch_errors.append(e)
            return ExecutionResult(success=len(branch_errors) == 0, value=None, trace=branch_trace, errors=branch_errors)

        branch_count = len(branches)
        if max_concurrency is None or max_concurrency >= branch_count:
            settled = await asyncio.gather(*[_exec_branch(b, i) for i, b in enumerate(branches)], return_exceptions=True)
            return [
                r if isinstance(r, ExecutionResult) else ExecutionResult(success=False, value=None, trace=[], errors=[Exception(str(r))])
                for r in settled
            ]
        return await self._execute_with_limit(branches, _exec_branch, max_concurrency)

    async def _execute_with_limit(self, branches: list[list[DSLStatement]], exec_fn: Any, limit: int) -> list[ExecutionResult]:
        results: list[ExecutionResult] = [ExecutionResult(success=True, value=None, trace=[], errors=[]) for _ in branches]
        semaphore = asyncio.Semaphore(limit)

        async def _run(index: int) -> None:
            async with semaphore:
                results[index] = await exec_fn(branches[index], index)

        tasks = [asyncio.create_task(_run(i)) for i in range(len(branches))]
        await asyncio.gather(*tasks, return_exceptions=True)
        return results

    def _make_trace(self, stmt: DSLParallel, start_time: float, status: str, errors: list[Exception]) -> list[TraceEntry]:
        return [TraceEntry(timestamp=start_time, statement_type="parallel", status=status, data={"branch_count": len(stmt.branches), "max_concurrency": stmt.max_concurrency, "error_count": len(errors)})]
