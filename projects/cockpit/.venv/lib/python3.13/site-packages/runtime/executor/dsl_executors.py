# ruff: noqa: S307  # eval is intentional for condition evaluation
"""DSL Executors — execute each step type in agent workflows."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


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

    async def agent_call(self, ctx: ExecutorContext, target: str, action: str) -> ExecutorResult:
        """Execute an agent call step."""
        fn = self._agent_registry.get(target)
        if not fn:
            return ExecutorResult(success=False, error=f"Agent not found: {target}")
        try:
            result = fn(ctx)
            if asyncio.iscoroutine(result):
                result = await result
            return ExecutorResult(success=True, output=result)
        except Exception as e:
            return ExecutorResult(success=False, error=str(e))

    async def skill_call(self, ctx: ExecutorContext, target: str, action: str) -> ExecutorResult:
        """Execute a skill call step."""
        fn = self._skill_registry.get(target)
        if not fn:
            return ExecutorResult(success=False, error=f"Skill not found: {target}")
        try:
            result = fn(ctx)
            if asyncio.iscoroutine(result):
                result = await result
            return ExecutorResult(success=True, output=result)
        except Exception as e:
            return ExecutorResult(success=False, error=str(e))

    async def tool_call(self, ctx: ExecutorContext, target: str, action: str) -> ExecutorResult:
        """Execute a tool call step."""
        fn = self._tool_registry.get(target)
        if not fn:
            return ExecutorResult(success=False, error=f"Tool not found: {target}")
        try:
            result = fn(ctx.params)
            if asyncio.iscoroutine(result):
                result = await result
            return ExecutorResult(success=True, output=result)
        except Exception as e:
            return ExecutorResult(success=False, error=str(e))

    async def conditional(self, ctx: ExecutorContext, condition: str,
                           true_step: str = "", false_step: str = "") -> ExecutorResult:
        """Evaluate a condition and route to next step."""
        eval_ctx = {**ctx.globals, **ctx.results}
        try:
            result = eval(condition, {"__builtins__": {}}, eval_ctx)
            next_s = true_step if result else false_step
            return ExecutorResult(success=True, output=result, next_step=next_s)
        except Exception as e:
            return ExecutorResult(success=False, error=str(e))

    async def loop(self, ctx: ExecutorContext, sub_steps: list, max_iterations: int = 10,
                   condition: str = "") -> ExecutorResult:
        """Execute sub-steps in a loop until condition is met."""
        outputs = []
        for i in range(max_iterations):
            if condition:
                eval_ctx = {**ctx.globals, **ctx.results, "loop_index": i}
                try:
                    if not eval(condition, {"__builtins__": {}}, eval_ctx):
                        break
                except Exception:
                    break
            for step_def in sub_steps:
                step_ctx = ExecutorContext(workflow_id=ctx.workflow_id,
                    step_id=f"{step_def.get('id', 'unknown')}_iter{i}",
                    params=step_def.get("params", {}), results=ctx.results, globals=ctx.globals)
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
            step_ctx = ExecutorContext(workflow_id=ctx.workflow_id,
                step_id=step_def.get("id", "unknown"),
                params=step_def.get("params", {}), results=ctx.results, globals=ctx.globals)
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

    async def try_catch(self, ctx: ExecutorContext, try_step: dict,
                         catch_step: dict | None = None,
                         finally_step: dict | None = None) -> ExecutorResult:
        """Execute a try-catch pattern."""
        try:
            result = await self._execute_substep(ctx, try_step)
            return result
        except Exception as e:
            if catch_step:
                catch_ctx = ExecutorContext(workflow_id=ctx.workflow_id,
                    step_id=catch_step.get("id", "catch"), params=catch_step.get("params", {}),
                    results=ctx.results, globals=ctx.globals)
                return await self._execute_substep(catch_ctx, catch_step)
            return ExecutorResult(success=False, error=str(e))
        finally:
            if finally_step:
                fin_ctx = ExecutorContext(workflow_id=ctx.workflow_id,
                    step_id=finally_step.get("id", "finally"),
                    params=finally_step.get("params", {}), results=ctx.results, globals=ctx.globals)
                await self._execute_substep(fin_ctx, finally_step)

    async def _execute_substep(self, ctx: ExecutorContext, step_def: dict) -> ExecutorResult:
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
