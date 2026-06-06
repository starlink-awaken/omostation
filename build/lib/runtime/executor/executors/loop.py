from __future__ import annotations

import time

from runtime.executor.dsl_types import (
    DSLLoop,
    ExecutionContext,
    ExecutionResult,
    TraceEntry,
)
from runtime.executor.dsl_types import (
    DSLNode as DSLStatement,
)
from runtime.executor.step_executor import ExecutionDependencies, IExpressionEvaluator

DEFAULT_MAX_ITERATIONS = 10000
DEFAULT_MAX_NESTING = 100
DEFAULT_ENABLE_TRACING = True


class IStatementExecutor:
    """Interface for executing DSL statements (step, condition, loop, etc.)."""

    async def execute_statement(self, stmt: DSLStatement, context: ExecutionContext) -> ExecutionResult:
        raise NotImplementedError


class LoopExecutor:
    """Executes for, while, and for_each loops for DSL workflow steps."""

    def __init__(
        self,
        dependencies: ExecutionDependencies,
        expression_evaluator: IExpressionEvaluator,
        statement_executor: IStatementExecutor,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        max_nesting_depth: int = DEFAULT_MAX_NESTING,
        enable_tracing: bool = DEFAULT_ENABLE_TRACING,
    ) -> None:
        self._deps = dependencies
        self._expr_eval = expression_evaluator
        self._stmt_exec = statement_executor
        self._max_iterations = max_iterations
        self._max_nesting = max_nesting_depth
        self._enable_tracing = enable_tracing

    async def execute(self, loop: DSLLoop, context: ExecutionContext) -> ExecutionResult:
        trace: list[TraceEntry] = []
        errors: list[Exception] = []
        try:
            new_depth = self._check_nesting_depth(context)
            loop_context = self._create_loop_context(context, new_depth)
            if loop.loop_type == "while":
                return await self._execute_while(loop, loop_context, trace, errors)
            if loop.loop_type == "for_each":
                return await self._execute_for_each(loop, loop_context, trace, errors)
            if loop.loop_type == "for":
                return await self._execute_for(loop, loop_context, trace, errors)
            raise ValueError(f"Unsupported loop type: {loop.loop_type}")
        except Exception as e:
            return ExecutionResult(success=False, value=None, trace=trace, errors=[*errors, e])

    async def _execute_while(self, loop: DSLLoop, context: ExecutionContext, trace: list[TraceEntry], errors: list[Exception]) -> ExecutionResult:
        iteration_count = 0
        while True:
            if iteration_count >= self._max_iterations:
                raise ValueError(f"While loop exceeded max iterations ({self._max_iterations})")
            if not loop.test:
                raise ValueError("While loop requires a test condition")
            loop_context = self._create_loop_context(context, context.depth)
            test_result = self._expr_eval.evaluate(loop.test, loop_context)
            if not bool(test_result):
                break
            body_result = await self._execute_body(loop.body, loop_context)
            trace.extend(body_result.trace)
            errors.extend(body_result.errors)
            if any(self._is_fatal(e) for e in body_result.errors):
                break
            iteration_count += 1
        self._add_trace(trace, loop, "while", iteration_count)
        return ExecutionResult(success=len(errors) == 0, value=None, trace=trace, errors=errors)

    async def _execute_for_each(self, loop: DSLLoop, context: ExecutionContext, trace: list[TraceEntry], errors: list[Exception]) -> ExecutionResult:
        if not loop.collection:
            raise ValueError("For_each loop requires a collection expression")
        collection = self._expr_eval.evaluate(loop.collection, context)
        items = collection if isinstance(collection, (list, tuple)) else list(getattr(collection, "items", lambda: [])())
        iteration_count = 0
        for item in items:
            if iteration_count >= self._max_iterations:
                raise ValueError(f"For_each loop exceeded max iterations ({self._max_iterations})")
            loop_context = self._create_loop_context(context, context.depth)
            if loop.variable:
                loop_context.locals[loop.variable] = item
            body_result = await self._execute_body(loop.body, loop_context)
            trace.extend(body_result.trace)
            errors.extend(body_result.errors)
            if any(self._is_fatal(e) for e in body_result.errors):
                break
            iteration_count += 1
        self._add_trace(trace, loop, "for_each", iteration_count)
        return ExecutionResult(success=len(errors) == 0, value=None, trace=trace, errors=errors)

    async def _execute_for(self, loop: DSLLoop, context: ExecutionContext, trace: list[TraceEntry], errors: list[Exception]) -> ExecutionResult:
        counter_name = loop.variable or "_i"
        counter = 0
        iteration_count = 0
        limit = 10000
        while counter < limit and iteration_count < self._max_iterations:
            loop_context = self._create_loop_context(context, context.depth)
            loop_context.locals[counter_name] = counter
            if loop.test:
                test_result = self._expr_eval.evaluate(loop.test, loop_context)
                if not bool(test_result):
                    break
            body_result = await self._execute_body(loop.body, loop_context)
            trace.extend(body_result.trace)
            errors.extend(body_result.errors)
            if any(self._is_fatal(e) for e in body_result.errors):
                break
            counter += 1
            iteration_count += 1
        self._add_trace(trace, loop, "for", iteration_count)
        return ExecutionResult(success=len(errors) == 0, value=None, trace=trace, errors=errors)

    async def _execute_body(self, body: list[DSLStatement], context: ExecutionContext) -> ExecutionResult:
        trace: list[TraceEntry] = []
        errors: list[Exception] = []
        for stmt in body:
            result = await self._stmt_exec.execute_statement(stmt, context)
            trace.extend(getattr(result, "trace", []) or [])
            errors.extend(getattr(result, "errors", []) or [])
        return ExecutionResult(success=len(errors) == 0, value=None, trace=trace, errors=errors)

    def _check_nesting_depth(self, context: ExecutionContext) -> int:
        current = context.depth or 0
        if current >= self._max_nesting:
            raise ValueError(f"Max loop nesting depth ({self._max_nesting}) exceeded")
        return current + 1

    def _create_loop_context(self, parent: ExecutionContext, depth: int) -> ExecutionContext:
        stats_cls = type(parent.stats) if hasattr(parent, "stats") else dict
        return ExecutionContext(
            input=parent.input.copy(),
            locals=parent.locals.copy(),
            results=parent.results.copy(),
            trace_id=parent.trace_id,
            depth=depth,
            stats=stats_cls(),  # type: ignore[arg-type]
            trace=[],
            parent=parent,
            options=parent.options,
        )

    def _add_trace(self, trace: list[TraceEntry], loop: DSLLoop, loop_type: str, iteration_count: int) -> None:
        if self._enable_tracing:
            trace.append(TraceEntry(timestamp=time.time(), statement_type="loop", status="success", data={"iterations": iteration_count, "loop_type": loop_type}))

    def _is_fatal(self, error: Exception) -> bool:
        msg = str(error)
        return "nesting depth" in msg or "iteration limit" in msg
