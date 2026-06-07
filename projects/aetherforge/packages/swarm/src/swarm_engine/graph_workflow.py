"""GraphWorkflow — 图工作流引擎 (vs LangGraph StateGraph).

有向图工作流，节点 = 执行步骤 (LLM/函数/条件)，边 = 状态转移。

Usage::

    from swarm_engine.graph_workflow import GraphWorkflow, NodeResult

    wf = GraphWorkflow()
    wf.add_node("research", lambda ctx: {"result": "..."})
    wf.add_node("write", lambda ctx: f"Based on research: {ctx.get('result', '')}")
    wf.add_edge("research", "write")
    wf.set_entry("research")

    state = wf.run({"topic": "AI"})
    print(state["write"])  # output of write node
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .synapse_gateway import GatewaySynapse

_log = logging.getLogger(__name__)

# A node function receives the shared state and returns an update dict
NodeFn = Callable[[dict[str, Any]], dict[str, Any]]
# A condition function receives state and returns the next node name (or None to stop)
ConditionFn = Callable[[dict[str, Any]], str | None]


@dataclass
class GraphNode:
    """A node in the workflow graph."""

    name: str = ""
    fn: NodeFn | None = None
    """The function to execute at this node. Receives state, returns update."""
    description: str = ""
    """Human-readable description of what this node does."""


@dataclass
class GraphEdge:
    """A directed edge between two nodes."""

    from_node: str = ""
    to_node: str = ""
    condition: ConditionFn | None = None
    """Optional condition: if set, only traverse when condition(state) == to_node."""


class GraphWorkflow:
    """Directed graph workflow engine.

    Supports:
      - Function nodes (arbitrary Python functions)
      - LLM nodes (prompt-based generation)
      - Conditional branching
      - Shared state across all nodes
      - Cycle detection

    Usage::

        wf = GraphWorkflow()

        @wf.node("research")
        def research(state):
            return {"findings": "..."}

        wf.add_llm_node("write", "Write based on: {findings}")
        wf.add_edge("research", "write")
        wf.set_entry("research")

        state = wf.run({"topic": "..."})
    """

    def __init__(self, synapse: GatewaySynapse | None = None) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []
        self._entry: str = ""
        self._synapse = synapse or GatewaySynapse()

    # ── Node registration ────────────────────────────────────────────────────

    def add_node(self, name: str, fn: NodeFn, description: str = "") -> GraphNode:
        """Register a function node."""
        node = GraphNode(name=name, fn=fn, description=description)
        self._nodes[name] = node
        return node

    def node(self, name: str, description: str = ""):
        """Decorator: register a function as a workflow node.

        Usage::

            @wf.node("process")
            def process(state):
                return {"result": state["input"] * 2}
        """
        def decorator(fn: NodeFn) -> NodeFn:
            self.add_node(name, fn, description)
            return fn
        return decorator

    def add_llm_node(
        self,
        name: str,
        prompt_template: str,
        system_prompt: str = "",
        description: str = "",
    ) -> GraphNode:
        """Register an LLM node that generates text via the gateway.

        The *prompt_template* can reference state variables with
        ``{variable_name}`` syntax.
        """
        def llm_fn(state: dict[str, Any]) -> dict[str, Any]:
            prompt = prompt_template.format(**state)
            resp = self._synapse.generate(
                model="",
                prompt=prompt,
                system=system_prompt,
                options={"max_tokens": 2048},
            )
            content = resp.get("response", "") if resp.get("status") == "success" else ""
            return {name: content}
        return self.add_node(name, llm_fn, description)

    # ── Edge registration ────────────────────────────────────────────────────

    def add_edge(
        self,
        from_node: str,
        to_node: str,
        condition: ConditionFn | None = None,
    ) -> None:
        """Add a directed edge.

        If *condition* is set, the edge is only taken when
        ``condition(state) == to_node``.
        """
        self._edges.append(GraphEdge(
            from_node=from_node, to_node=to_node, condition=condition,
        ))

    def set_entry(self, node: str) -> None:
        """Set the entry point node."""
        self._entry = node

    # ── Execution ────────────────────────────────────────────────────────────

    def run(self, initial_state: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute the workflow graph.

        Args:
            initial_state: Starting state dict.

        Returns:
            The final state after all reachable nodes have executed.
        """
        state = dict(initial_state or {})
        state["_history"] = []
        state["_errors"] = []

        if not self._entry or self._entry not in self._nodes:
            raise ValueError(f"Entry node '{self._entry}' not found")

        current = self._entry
        visited: set[str] = set()
        max_steps = len(self._nodes) * 3  # safety limit

        for _ in range(max_steps):
            if current is None:
                break
            if current in visited:
                _log.warning("Cycle detected at node '%s', stopping", current)
                break

            node = self._nodes.get(current)
            if node is None:
                _log.warning("Node '%s' not found, stopping", current)
                break

            visited.add(current)

            # Execute
            try:
                if node.fn:
                    update = node.fn(state)
                    state.update(update)
                    state["_history"].append({"node": current, "status": "ok"})
            except Exception as e:
                _log.error("Node '%s' failed: %s", current, e)
                state["_errors"].append({"node": current, "error": str(e)})
                state["_history"].append({"node": current, "status": "error", "error": str(e)})
                break

            # Find next node
            next_node: str | None = None
            for edge in self._edges:
                if edge.from_node == current:
                    if edge.condition:
                        result = edge.condition(state)
                        if result == edge.to_node:
                            next_node = edge.to_node
                            break
                    else:
                        next_node = edge.to_node

            current = next_node

        return state

    # ── Inspection ───────────────────────────────────────────────────────────

    def get_nodes(self) -> list[str]:
        return list(self._nodes.keys())

    def get_edges(self) -> list[tuple[str, str]]:
        return [(e.from_node, e.to_node) for e in self._edges]

    def visualize(self) -> str:
        """Return a simple ASCII graph visualization."""
        lines = ["GraphWorkflow:"]
        lines.append(f"  Entry: {self._entry}")
        for n in self._nodes:
            lines.append(f"  [{n}]")
            for e in self._edges:
                if e.from_node == n:
                    cond = f" ? {e.condition.__name__}" if e.condition else ""
                    lines.append(f"    -> {e.to_node}{cond}")
        return "\n".join(lines)
