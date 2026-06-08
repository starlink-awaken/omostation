"""Agent Execution Runner -- lifecycle management, retry, state tracking.

Maps to TS source: agentmesh/packages/engine/src/agent-runner.ts

Supports:
  - Agent definition registration and lifecycle (spawn, monitor, terminate)
  - Task execution with retry logic and exponential backoff
  - Capability matching for agent selection
  - Simulation mode for testing
  - LLM integration path for real API calls
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_RETRIES = 3
BASE_BACKOFF_MS = 1000


# ---------------------------------------------------------------------------
# Enums & Types
# ---------------------------------------------------------------------------


class AgentStatus(StrEnum):
    """Lifecycle status of an agent execution."""

    PENDING = "pending"
    RUNNING = "running"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ComplexityLevel(StrEnum):
    """Project complexity levels controlling which agent layers are activated."""

    SIMPLE = "simple"
    STANDARD = "standard"
    ADVANCED = "advanced"
    ENTERPRISE = "enterprise"


class AgentLayer(StrEnum):
    """Architectural layer an agent belongs to."""

    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"
    GOVERNANCE = "governance"


@dataclass
class GovernanceConfig:
    """Embedded governance configuration for an agent."""

    first_principles_check: bool = True
    red_team_threshold: str = "medium"
    quality_gate_enabled: bool = True
    max_retries: int = MAX_RETRIES
    token_budget: int = 100_000


@dataclass
class AgentDefinition:
    """Full agent definition parsed from Markdown frontmatter."""

    name: str
    description: str
    layer: AgentLayer = AgentLayer.L3
    agent_type: str = "worker"
    capabilities: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    prompt_path: str = ""
    prompt_body: str = ""
    governance: GovernanceConfig = field(default_factory=GovernanceConfig)


@dataclass
class AgentState:
    """Runtime state of an agent execution."""

    agent_name: str
    status: AgentStatus = AgentStatus.PENDING
    current_task: str = ""
    output: str | None = None
    error: str | None = None
    retry_count: int = 0
    token_usage: int = 0
    started_at: float = 0.0
    completed_at: float | None = None


# ---------------------------------------------------------------------------
# AgentRunner
# ---------------------------------------------------------------------------


class AgentRunner:
    """Manages agent lifecycle: spawn, execute, monitor, and terminate."""

    def __init__(self) -> None:
        self._states: dict[str, AgentState] = {}
        self._definitions: dict[str, AgentDefinition] = {}
        self._llm_client: Any = None

    # -- Configuration -------------------------------------------------------

    def set_llm_client(self, client: Any) -> None:
        """Set an LLM client for real API calls (replaces simulation)."""
        self._llm_client = client

    def register_definition(self, definition: AgentDefinition) -> None:
        """Register an agent definition for capability matching."""
        self._definitions[definition.name] = definition

    def get_definition(self, name: str) -> AgentDefinition | None:
        """Get a registered agent definition by name."""
        return self._definitions.get(name)

    # -- Capability matching -------------------------------------------------

    def find_agent(self, required_capabilities: list[str]) -> AgentDefinition | None:
        """Find an agent whose capabilities best match the required set."""
        best: AgentDefinition | None = None
        best_score = -1
        for definition in self._definitions.values():
            score = sum(1 for c in required_capabilities if c in definition.capabilities)
            if score > best_score:
                best_score = score
                best = definition
        return best if best_score >= 0 else None

    def list_by_capability(self, capability: str) -> list[AgentDefinition]:
        """List agents that have a specific capability."""
        return [d for d in self._definitions.values() if capability in d.capabilities]

    # -- Execution -----------------------------------------------------------

    async def run_agent(
        self,
        definition: AgentDefinition,
        task: str,
        context: str | None = None,
    ) -> AgentState:
        """Execute an agent with retry logic and error recovery.

        Supports two modes:
        - Simulation (default when no LLM client is set).
        - Real LLM API (when ``set_llm_client`` has been called).
        """
        state = AgentState(
            agent_name=definition.name,
            status=AgentStatus.RUNNING,
            current_task=task,
            started_at=time.time(),
        )
        self._states[definition.name] = state

        max_retries = definition.governance.max_retries

        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    state.status = AgentStatus.RETRYING
                    state.retry_count = attempt
                    delay_ms = BASE_BACKOFF_MS * (2 ** (attempt - 1))
                    await asyncio.sleep(delay_ms / 1000)

                if self._llm_client is not None:
                    result = await self._call_llm(definition, task, context)
                else:
                    result = self._simulate(definition, task, context)

                state.output = result["output"]
                state.token_usage = result["tokens"]
                state.status = AgentStatus.COMPLETED
                state.completed_at = time.time()
                state.error = None
                self._states[definition.name] = state
                return state

            except Exception as exc:
                state.error = str(exc)
                if attempt >= max_retries:
                    state.status = AgentStatus.FAILED
                    state.completed_at = time.time()
                    self._states[definition.name] = state
                    return state

        # Defensive fallback
        state.status = AgentStatus.FAILED
        state.completed_at = time.time()
        self._states[definition.name] = state
        return state

    # -- State access --------------------------------------------------------

    def get_agent_state(self, agent_name: str) -> AgentState | None:
        """Retrieve runtime state of an agent by name."""
        return self._states.get(agent_name)

    def list_agent_states(self) -> list[AgentState]:
        """List all agent runtime states."""
        return list(self._states.values())

    def cancel_agent(self, agent_name: str) -> bool:
        """Cancel a running or retrying agent."""
        state = self._states.get(agent_name)
        if state is None or state.status not in (AgentStatus.RUNNING, AgentStatus.RETRYING):
            return False
        state.status = AgentStatus.CANCELLED
        state.completed_at = time.time()
        return True

    # -- Internal: simulation ------------------------------------------------

    def _simulate(
        self,
        definition: AgentDefinition,
        task: str,
        context: str | None = None,
    ) -> dict[str, Any]:
        """Simulate agent execution for testing."""
        context_note = f" | context_length={len(context)}" if context else ""
        lines = [
            f'[Simulated] Agent "{definition.name}" ({definition.layer.value}) executed.',
            f"Task: {task}",
            f"Tools: {', '.join(definition.tools) if definition.tools else 'none'}",
            f"Context provided: {'yes' + context_note if context else 'no'}",
            "Status: completed (simulation)",
        ]
        estimated_tokens = (len(task) + (len(context) if context else 0)) // 4 + 50
        return {"output": "\n".join(lines), "tokens": estimated_tokens}

    # -- Internal: LLM call --------------------------------------------------

    async def _call_llm(
        self,
        definition: AgentDefinition,
        task: str,
        context: str | None = None,
    ) -> dict[str, Any]:
        """Execute agent via LLM API (requires external LLM client)."""
        self._build_prompt(definition, task, context)
        msg = f"LLM client set but real integration not implemented for {definition.name}"
        raise NotImplementedError(msg)

    @staticmethod
    def _build_prompt(
        definition: AgentDefinition,
        task: str,
        context: str | None = None,
    ) -> str:
        """Build the full prompt from definition, task, and context."""
        parts: list[str] = [definition.prompt_body or definition.description]
        if context:
            parts.append(f"## Context\n{context}")
        parts.append(f"## Task\n{task}")
        return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# AgentPool
# ---------------------------------------------------------------------------


class AgentPool:
    """Manage a collection of agent definitions with layer/complexity queries."""

    def __init__(self) -> None:
        self._definitions: dict[str, AgentDefinition] = {}
        self._runner = AgentRunner()

    # -- Registration --------------------------------------------------------

    def register(self, definition: AgentDefinition) -> None:
        """Register an agent definition."""
        self._definitions[definition.name] = definition
        self._runner.register_definition(definition)

    def register_many(self, definitions: list[AgentDefinition]) -> None:
        """Register multiple agent definitions at once."""
        for definition in definitions:
            self.register(definition)

    # -- Querying ------------------------------------------------------------

    def get(self, name: str) -> AgentDefinition | None:
        """Get an agent definition by name."""
        return self._definitions.get(name)

    def list_all(self) -> list[AgentDefinition]:
        """List all registered agent definitions."""
        return list(self._definitions.values())

    def list_by_layer(self, layer: AgentLayer) -> list[AgentDefinition]:
        """Get agents belonging to a specific architectural layer."""
        return [d for d in self._definitions.values() if d.layer == layer]

    def list_by_type(self, agent_type: str) -> list[AgentDefinition]:
        """Get agents of a specific type."""
        return [d for d in self._definitions.values() if d.agent_type == agent_type]

    def find_by_capability(self, capability: str) -> list[AgentDefinition]:
        """Find agents with a given capability."""
        return self._runner.list_by_capability(capability)

    def get_active_agents(self, complexity: ComplexityLevel) -> list[AgentDefinition]:
        """Return agents to activate for a given complexity level.

        - simple:     L3 (execution) + L4 (feedback)
        - standard:   L2 (decision) + L3 + L4
        - advanced:   all layers
        - enterprise: all layers
        """
        all_agents = list(self._definitions.values())
        if complexity == ComplexityLevel.SIMPLE:
            return [a for a in all_agents if a.layer in (AgentLayer.L3, AgentLayer.L4)]
        if complexity == ComplexityLevel.STANDARD:
            return [
                a
                for a in all_agents
                if a.layer in (AgentLayer.L2, AgentLayer.L3, AgentLayer.L4)
            ]
        return all_agents

    # -- Capability matching -------------------------------------------------

    def match_agent(self, required_capabilities: list[str]) -> AgentDefinition | None:
        """Find the best agent for a set of required capabilities."""
        return self._runner.find_agent(required_capabilities)

    # -- Execution delegation ------------------------------------------------

    def get_runner(self) -> AgentRunner:
        """Access the underlying AgentRunner for direct execution."""
        return self._runner

    async def execute(
        self,
        agent_name: str,
        task: str,
        context: str | None = None,
    ) -> AgentState:
        """Execute a named agent via the runner."""
        definition = self._definitions.get(agent_name)
        if definition is None:
            raise ValueError(f"Agent not found: {agent_name}")
        return await self._runner.run_agent(definition, task, context)
