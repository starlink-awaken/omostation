"""HierarchicalProcess — Manager→Worker 层级编排引擎.

借鉴 CrewAI 的 hierarchical process 模式:
  - **Manager Agent**: 接收复杂任务，分解为子任务，分配给 Worker
  - **Worker Agents**: 执行具体子任务，返回结果
  - **Manager Agent**: 汇总所有子任务结果为最终输出

依赖: GatewaySynapse (LLM 调用) + auctioneer (任务分配) + DAG (依赖编排)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from .synapse_gateway import GatewaySynapse

_log = logging.getLogger(__name__)


@dataclass
class SubTask:
    """A task within a hierarchical process."""

    id: str = ""
    """Unique subtask identifier."""
    description: str = ""
    """What this subtask should accomplish."""
    agent_role: str = ""
    """Role of the agent that should execute this (e.g. ``"researcher"``)."""
    depends_on: list[str] = field(default_factory=list)
    """IDs of subtasks that must complete before this one."""
    result: str = ""
    """Output from the worker agent."""
    status: str = "pending"
    """``pending``, ``running``, ``completed``, ``failed``."""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HierarchicalResult:
    """Result of a hierarchical process run."""

    success: bool = False
    final_output: str = ""
    subtasks: list[SubTask] = field(default_factory=list)
    total_tokens: int = 0
    total_cost: float = 0.0
    elapsed_ms: float = 0.0
    error: str = ""


class HierarchicalProcess:
    """Manager→Worker hierarchical task execution.

    Usage::

        process = HierarchicalProcess()
        result = process.run(
            manager_prompt="Plan a 3-day Beijing itinerary",
            worker_roles=["researcher", "writer"],
        )
        print(result.final_output)
    """

    def __init__(self, synapse: GatewaySynapse | None = None) -> None:
        self._synapse = synapse or GatewaySynapse()

    # ── Public API ───────────────────────────────────────────────────────────

    def run(
        self,
        manager_prompt: str,
        worker_roles: list[str] | None = None,
        *,
        context: str = "",
        max_subtasks: int = 8,
    ) -> HierarchicalResult:
        """Execute a hierarchical process.

        Args:
            manager_prompt: The high-level task description for the manager.
            worker_roles: Optional list of worker roles (e.g. ``["researcher",
                "writer"]``). If empty, the manager decides roles.
            context: Optional background context for all agents.
            max_subtasks: Maximum number of subtasks to decompose into.

        Returns:
            A ``HierarchicalResult`` with the final output.
        """
        start = time.time()
        result = HierarchicalResult()

        # Phase 1: Manager decomposes the task
        subtasks = self._decompose(manager_prompt, worker_roles or [], context, max_subtasks)
        if not subtasks:
            result.error = "Failed to decompose task"
            return result
        result.subtasks = subtasks

        # Phase 2: Execute subtasks respecting dependencies
        self._execute_subtasks(subtasks, context)

        # Phase 3: Manager synthesizes results
        final = self._synthesize(manager_prompt, subtasks, context)
        result.final_output = final
        result.success = True
        result.elapsed_ms = (time.time() - start) * 1000
        return result

    # ── Phase 1: Decompose ───────────────────────────────────────────────────

    def _decompose(
        self,
        prompt: str,
        worker_roles: list[str],
        context: str,
        max_subtasks: int,
    ) -> list[SubTask]:
        """Ask the manager LLM to decompose the task into subtasks."""
        roles_hint = f" Available roles: {', '.join(worker_roles)}." if worker_roles else ""
        ctx_hint = f"\nContext: {context}" if context else ""

        system = (
            "You are a task decomposition manager. Break the user's request into "
            f"concrete subtasks (max {max_subtasks}). "
            "Output ONLY a JSON array of subtasks, each with: "
            '{"id": "step-1", "description": "...", '
            '"agent_role": "researcher|writer|analyst|critic", '
            '"depends_on": []}\n'
            "No markdown, no explanation, no code fences."
        )

        user_msg = f"Task: {prompt}{roles_hint}{ctx_hint}"

        resp = self._synapse.generate(
            model="",
            prompt=user_msg,
            system=system,
            options={"max_tokens": 2048, "temperature": 0.3},
        )

        if resp.get("status") != "success":
            _log.warning("Decomposition failed: %s", resp.get("message"))
            return []

        return self._parse_subtasks(resp.get("response", ""))

    def _parse_subtasks(self, text: str) -> list[SubTask]:
        """Parse JSON array of subtasks from LLM response."""
        # Strip code fences if present
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            text = text.rsplit("```", 1)[0]

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON array from the text
            import re
            match = re.search(r"\[.*?\]", text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    _log.error("Failed to parse subtask JSON")
                    return []
            else:
                _log.error("No JSON array found in decomposition response")
                return []

        subtasks = []
        for i, item in enumerate(data):
            subtasks.append(SubTask(
                id=item.get("id", f"step-{i + 1}"),
                description=item.get("description", ""),
                agent_role=item.get("agent_role", "worker"),
                depends_on=item.get("depends_on", []),
            ))
        return subtasks

    # ── Phase 2: Execute ─────────────────────────────────────────────────────

    def _execute_subtasks(self, subtasks: list[SubTask], context: str) -> None:
        """Execute subtasks in topological order respecting dependencies."""
        executed: set[str] = set()
        remaining = {s.id for s in subtasks}
        lookup = {s.id: s for s in subtasks}

        max_iter = len(subtasks) * 2
        for _ in range(max_iter):
            if not remaining:
                break

            for s in subtasks:
                if s.id not in remaining:
                    continue
                # Check if all dependencies are met
                if all(dep in executed for dep in s.depends_on):
                    s.status = "running"
                    _log.info("Executing subtask: %s (%s)", s.id, s.description[:60])
                    result = self._execute_single(s, context)
                    s.result = result
                    s.status = "completed" if result else "failed"
                    executed.add(s.id)
                    remaining.discard(s.id)

    def _execute_single(self, subtask: SubTask, context: str) -> str:
        """Execute a single subtask via the LLM."""
        system = (
            f"You are a {subtask.agent_role} agent. "
            "Complete your assigned subtask concisely and thoroughly."
        )
        user_msg = f"Task: {subtask.description}"
        if context:
            user_msg = f"Context: {context}\n\n{user_msg}"
        if subtask.depends_on:
            deps_context = "\n".join(
                f"Input from {dep}: {s.result[:200]}"
                for dep in subtask.depends_on
                if (s := next((x for x in [subtask] if x.id == dep), None))
            )
            if deps_context:
                user_msg = f"{deps_context}\n\n{user_msg}"

        resp = self._synapse.generate(
            model="",
            prompt=user_msg,
            system=system,
            options={"max_tokens": 2048, "temperature": 0.7},
        )

        return resp.get("response", "") if resp.get("status") == "success" else ""

    # ── Phase 3: Synthesize ──────────────────────────────────────────────────

    def _synthesize(self, prompt: str, subtasks: list[SubTask], context: str) -> str:
        """Ask the manager to synthesize subtask results into a final answer."""
        results_text = "\n\n".join(
            f"### {s.id} ({s.agent_role}): {s.description}\n{s.result[:500]}"
            for s in subtasks
            if s.result
        )

        ctx_hint = f"\nContext: {context}" if context else ""

        system = (
            "You are a synthesis manager. Combine the subtask results into "
            "a coherent, complete response to the original request."
        )
        user_msg = (
            f"Original request: {prompt}{ctx_hint}\n\n"
            f"Subtask results:\n\n{results_text}\n\n"
            "Provide the final synthesized output."
        )

        resp = self._synapse.generate(
            model="",
            prompt=user_msg,
            system=system,
            options={"max_tokens": 4096, "temperature": 0.5},
        )

        return resp.get("response", "") if resp.get("status") == "success" else ""
