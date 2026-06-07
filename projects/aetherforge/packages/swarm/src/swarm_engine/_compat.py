"""
_compat.py — Compatibility stubs for types migrated from SharedBrain.

These are placeholder definitions for types that were originally imported
from nucleus.Z_Microkernel / SharedBrain. Each should eventually be replaced
with a proper implementation or import once the migration is complete.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from enum import StrEnum
from typing import Any, NamedTuple

# ── Logger ────────────────────────────────────────────────────────────────

_log = logging.getLogger(__name__)

# ── Core Types ────────────────────────────────────────────────────────────


class TaskType(StrEnum):
    """Task type classification. TODO: reconcile with real enum from SharedBrain."""

    CODE_GENERATION = "CODE_GENERATION"
    CODE_REFACTOR = "CODE_REFACTOR"
    CODE_REVIEW = "CODE_REVIEW"
    SECURITY_AUDIT = "SECURITY_AUDIT"
    RESEARCH = "RESEARCH"
    ANALYSIS = "ANALYSIS"
    ORCHESTRATION = "ORCHESTRATION"
    PLANNING = "PLANNING"
    EXECUTION = "EXECUTION"
    MONITORING = "MONITORING"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    TEST_GENERATION = "TEST_GENERATION"
    DOCUMENTATION = "DOCUMENTATION"
    DATA_ANALYSIS = "DATA_ANALYSIS"
    DEPLOYMENT = "DEPLOYMENT"
    UNKNOWN = "UNKNOWN"


class WorkerState(StrEnum):
    """Worker lifecycle state."""

    HATCHING = "HATCHING"
    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    BUSY = "BUSY"
    STARVING = "STARVING"
    DRAINING = "DRAINING"
    TERMINATED = "TERMINATED"
    REAPED = "REAPED"


class Priority(StrEnum):
    """Task priority level."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class GovernanceAction(StrEnum):
    """Governance action type for lifecycle management."""

    DOWNGRADE = "DOWNGRADE"
    UPGRADE = "UPGRADE"
    TERMINATE = "TERMINATE"
    HATCH = "HATCH"
    STANDBY = "STANDBY"
    RESTORE = "RESTORE"
    FREEZE = "FREEZE"
    RECLAIM = "RECLAIM"


class GovernanceState:
    """Governance state for lifecycle with action application."""

    def __init__(self, status: str = "NORMAL") -> None:
        self.status: StrEnum = _GovernanceStatusEnum(status)

    def apply_action(self, action: GovernanceAction, *, actor_id: str, reason: str) -> GovernanceEvent:
        return GovernanceEvent(action=action, reason=reason, actor_id=actor_id)

    @classmethod
    def NORMAL(cls) -> GovernanceState:  # noqa: N802
        return cls("NORMAL")

    @classmethod
    def DEGRADED(cls) -> GovernanceState:  # noqa: N802
        return cls("DEGRADED")

    @classmethod
    def CRITICAL(cls) -> GovernanceState:  # noqa: N802
        return cls("CRITICAL")


class _GovernanceStatusEnum(StrEnum):
    NORMAL = "NORMAL"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    RECOVERY = "RECOVERY"


class GovernanceEvent:
    """Event emitted after a governance action is applied."""

    def __init__(self, action: GovernanceAction, reason: str, actor_id: str) -> None:
        self.action = action
        self.reason = reason
        self.actor_id = actor_id


# ── Data Classes ──────────────────────────────────────────────────────────


class Receipt(NamedTuple):
    """Receipt returned when a worker accepts an envelope."""

    envelope_id: str


class MessageEnvelope:
    """Message envelope for worker communication."""

    def __init__(
        self,
        id: str = "",
        task_type: str = "",
        eu_budget: float = 0.0,
        payload: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self.id = id
        self.task_type = task_type
        self.eu_budget = eu_budget
        self.payload = payload or {}
        for k, v in kwargs.items():
            setattr(self, k, v)


class SynapseAgentCard:
    """Agent card describing a synapse worker's capabilities."""

    def __init__(
        self,
        capabilities: list[str] | None = None,
        cost_class: str = "medium",
        mode: str = "active",
        max_eu_budget: float = 50.0,
        **kwargs: Any,
    ) -> None:
        self.capabilities = capabilities or []
        self.cost_class = cost_class
        self.mode = mode
        self.max_eu_budget = max_eu_budget
        for k, v in kwargs.items():
            setattr(self, k, v)


class PlannedStep:
    """A single planned step from the local planner."""

    def __init__(
        self,
        task_type: TaskType = TaskType.UNKNOWN,
        description: str = "",
        priority: Priority = Priority.MEDIUM,
        step_id: str = "",
        dependencies: list[str] | None = None,
        estimated_eu: float = 1.0,
        suggested_capability: str = "generic",
        rollback_plan: str = "",
        depends_on: list[str] | None = None,
    ) -> None:
        self.task_type = task_type
        self.description = description
        self.priority = priority
        self.step_id = step_id
        self.dependencies = dependencies or []
        self.estimated_eu = estimated_eu
        self.suggested_capability = suggested_capability
        self.rollback_plan = rollback_plan


class ExecutionPlan:
    """Execution plan containing multiple planned steps."""

    def __init__(
        self,
        steps: list[PlannedStep] | None = None,
        plan_id: str = "",
        original_intent: str = "",
        estimated_total_eu: float = 0.0,
        estimated_duration: float = 0.0,
        can_parallelize: list[str] | None = None,
        confidence: float = 0.0,
        fallback_used: bool = False,
        reasoning: str = "",
    ) -> None:
        self.steps = steps or []
        self.plan_id = plan_id
        self.original_intent = original_intent
        self.estimated_total_eu = estimated_total_eu
        self.estimated_duration = estimated_duration
        self.can_parallelize = can_parallelize or []
        self.confidence = confidence
        self.fallback_used = fallback_used
        self.reasoning = reasoning


class TaskResult(NamedTuple):
    """Result of a task execution."""

    task_id: str
    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    worker_id: str = ""
    eu_consumed: float = 0.0


# ── Type stubs ────────────────────────────────────────────────────────────


class ISynapseWorker:
    """Stub interface for synapse workers."""

    def describe(self) -> SynapseAgentCard:
        return SynapseAgentCard()

    def accept(self, envelope: MessageEnvelope) -> Receipt:
        return Receipt(envelope_id=envelope.id)

    def heartbeat(self) -> dict[str, Any]:
        return {"status": "ok"}


class WorkerHandle:
    """Stub worker handle for lifecycle tracking."""

    def __init__(self, **kw: Any) -> None:
        for k, v in kw.items():
            setattr(self, k, v)

    @property
    def worker_id(self) -> str:
        return getattr(self, "_worker_id", "")

    @worker_id.setter
    def worker_id(self, value: str) -> None:
        self._worker_id = value

    @property
    def state(self) -> WorkerState:
        return getattr(self, "_state", WorkerState.ACTIVE)

    @state.setter
    def state(self, value: WorkerState) -> None:
        self._state = value

    @property
    def pid(self) -> int:
        return getattr(self, "_pid", 0)

    @pid.setter
    def pid(self, value: int) -> None:
        self._pid = value

    @property
    def process(self) -> Any:
        return getattr(self, "_process", None)

    @process.setter
    def process(self, value: Any) -> None:
        self._process = value

    @property
    def last_heartbeat(self) -> float:
        return getattr(self, "_last_heartbeat", 0.0)

    @last_heartbeat.setter
    def last_heartbeat(self, value: float) -> None:
        self._last_heartbeat = value

    @property
    def eu_consumed(self) -> float:
        return getattr(self, "_eu_consumed", 0.0)

    @eu_consumed.setter
    def eu_consumed(self, value: float) -> None:
        self._eu_consumed = value

    @property
    def eu_budget(self) -> float:
        return getattr(self, "_eu_budget", 0.0)

    @eu_budget.setter
    def eu_budget(self, value: float) -> None:
        self._eu_budget = value


class WorkerBundle:
    """Bundle of a worker handle and its metadata."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if args:
            self.handle = args[0] if len(args) > 0 else WorkerHandle()
            self.task_type = args[1] if len(args) > 1 else TaskType.UNKNOWN
            self.task_results = args[2] if len(args) > 2 else ()
            self.total_eu_consumed = args[3] if len(args) > 3 else 0.0
            self.total_tasks = args[4] if len(args) > 4 else 0
            self.successful_tasks = args[5] if len(args) > 5 else 0
            self.nectar_earned = args[6] if len(args) > 6 else 0.0
        else:
            self.handle = kwargs.get("handle", WorkerHandle())
            self.task_type = kwargs.get("task_type", TaskType.UNKNOWN)
            self.task_results = kwargs.get("task_results", ())
            self.total_eu_consumed = kwargs.get("total_eu_consumed", 0.0)
            self.total_tasks = kwargs.get("total_tasks", 0)
            self.successful_tasks = kwargs.get("successful_tasks", 0)
            self.nectar_earned = kwargs.get("nectar_earned", 0.0)


class AgentDaemonBase:
    """Stub base class for agent daemons."""

    def __init__(self, **kwargs: Any) -> None:
        self.agent_id: str = kwargs.get("agent_id", "")
        self.persona: str = kwargs.get("persona", "")
        self.capabilities: list[str] = kwargs.get("capabilities", [])
        self.heartbeat_interval: float = kwargs.get("heartbeat_interval", 10.0)
        self.poll_interval: float = kwargs.get("poll_interval", 2.0)
        self.running: bool = False
        self.current_load: int = 0
        self.current_eu: float = kwargs.get("current_eu", 100.0)
        self.instance_id: str = kwargs.get("instance_id", "")
        self._mcp_send_envelope: Callable[[Any], Any] | None = None

    def run(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def shutdown(self) -> None:
        self.running = False

    def get_health_report(self) -> dict[str, Any]:
        return {}


# ── Path / Config ─────────────────────────────────────────────────────────


class ProjectPaths:
    """Stub project path resolver."""

    ROOT: str = "."

    @classmethod
    def get_core_db_path(cls, name: str) -> str:
        return name

    @classmethod
    def get_db_path(cls, name: str, *args: str) -> str:
        return name


class Infrastructure:
    """Stub infrastructure config."""


class InferenceOracle:
    """Stub inference oracle."""

    @classmethod
    def get_instance(cls) -> InferenceOracle:
        return cls()

    def infer(self, *args: Any, **kwargs: Any) -> Any:
        return None


class ResultBus:
    """Stub result bus."""

    @classmethod
    def get_instance(cls) -> ResultBus:
        return cls()

    def drain_results(self, worker_id: str) -> list[Any]:
        return []


class Gateway:
    """Stub gateway reference."""

    @classmethod
    def register_model(cls, card: dict[str, Any]) -> None:
        pass

    @classmethod
    def call(cls, *args: Any, **kwargs: Any) -> Any:
        return None


class BOSUri:
    """Stub BOS URI."""

    domain: str = ""
    resource: str = ""
    action: str = ""
    trace_id: str = ""
    span_id: str = ""

    @classmethod
    def parse(cls, uri: str) -> BOSUri:
        return cls()


class CapabilityRegistry:
    """Stub capability registry."""

    def list_agents(self) -> list[dict[str, Any]]:
        return []

    def select_for_task(self, **kwargs: Any) -> Any:
        return None


class KnowledgeEnhancementMixin:
    """Stub knowledge enhancement mixin."""

    def enhance_task_with_knowledge(self, task_payload: dict[str, Any], persona: str, cwd: str) -> None:
        pass


class ContextInjector:
    """Stub context injector."""

    @classmethod
    def prepare_environment(cls, **kwargs: Any) -> Any:
        return None

    @classmethod
    def generate_hifi_prompt(cls, **kwargs: Any) -> str:
        return ""


class AssociationEngine:
    """Stub association engine."""

    @classmethod
    def get_instance(cls) -> AssociationEngine:
        return cls()


# ── Functions ─────────────────────────────────────────────────────────────

_synapse_registry_cache: Any | None = None


def get_synapse_registry() -> Any:
    """Stub — returns the synapse registry (cached)."""
    global _synapse_registry_cache
    if _synapse_registry_cache is None:
        _synapse_registry_cache = _SynapseRegistryStub()
    return _synapse_registry_cache


def get_spore_gateway() -> Any:
    """Stub — returns a spore gateway object."""
    return _SporeGatewayStub()


def get_synapse_router() -> Any:
    """Stub — returns a synapse router."""
    return _SynapseRouterStub()


def get_path_resolver() -> Any:
    """Stub — returns a path resolver."""
    return None


class _BOSAgentRouterBridge:
    """Stub agent router bridge."""

    def agent_send_envelope(self, envelope: Any) -> Any:
        return None


bos_agent_router_bridge = _BOSAgentRouterBridge()


def managed_connection(uri: str = "", **kwargs: Any) -> Any:
    """Stub — returns a managed connection."""
    return None


# ── Internal Stubs ────────────────────────────────────────────────────────


class _SporeGatewayStub:
    """Internal stub for spore gateway."""

    def get_component(self, name: str) -> Any:
        return _TransportStub()


class _SynapseRouterStub:
    """Internal stub for synapse router."""

    def route(self, envelope: MessageEnvelope) -> Any:
        return None


class _TransportStub:
    """Internal stub for message transport."""

    def deliver_frame(self, *args: Any, **kwargs: Any) -> Any:
        return None


class _SynapseRegistryStub:
    """Internal stub for synapse registry."""

    def register(self, worker: Any) -> str:
        return "stub-id"

    def unregister(self, synapse_id: str) -> None:
        pass


class RegistryAgentCard:
    """Stub for nucleus.Z_Microkernel.organs.capability_registry.AgentCard."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass


def agent_send(target: str, message: Any) -> bool:
    """Stub for bos_agent_router_bridge.agent_send."""
    return True


def agent_receive(target: str) -> list[Any]:
    """Stub for bos_agent_router_bridge.agent_receive."""
    return []


def agent_ack(message_id: str) -> bool:
    """Stub for bos_agent_router_bridge.agent_ack."""
    return True
