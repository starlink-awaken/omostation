"""
_compat.py — Swarm compatibility layer backed by bus-foundation.

Data‑type stubs (enums, dataclasses) are kept here for import stability.
Event‑emitting functions now publish onto the real `bus-foundation` event
bus (OmniEnvelope / EventBusBackend) instead of being no-ops.  All imports
remain backward‑compatible — callers do not need to change.

  Bus topic conventions:
    swarm:worker:hatched       — worker successfully spawned
    swarm:worker:terminated    — worker process exited
    swarm:agent:send           — point-to-point message from agent
    swarm:agent:receive        — polled inbox for agent
    swarm:inference:request    — oracle inference request
    swarm:inference:response   — oracle inference response
    swarm:governance:action    — governance lifecycle event
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from enum import StrEnum
from typing import Any, NamedTuple

# ── bus-foundation integration ──────────────────────────────────────────────
# Import bus-foundation lazily so that swarm_engine can still be imported
# in environments where bus-foundation is not yet installed (tests that only
# exercise data-type stubs will still work; the fallback is the old no-op).


def _try_get_bus_publish():
    """Return (publish_fn, BusEnvelope, EventType) or (None, None, None) if unavailable."""
    try:
        from bus_foundation import publish  # type: ignore[import]
        from bus_foundation.envelope import BusEnvelope, EventType  # type: ignore[import]

        return publish, BusEnvelope, EventType
    except Exception:
        return None, None, None


def _bus_publish(topic: str, payload: dict, source: str = "swarm_engine._compat") -> None:
    """Publish a swarm event onto the bus-foundation bus. No-op if unavailable."""
    publish_fn, bus_env_cls, event_type_cls = _try_get_bus_publish()
    if publish_fn is None:
        _log.debug("bus-foundation unavailable, skipping publish: %s", topic)
        return
    try:
        env = bus_env_cls(  # type: ignore[reportOptionalCall]
            event_type=event_type_cls.INFO,  # type: ignore[reportOptionalMemberAccess]
            topic=topic,
            source=source,  # type: ignore[reportCallIssue]
            payload=payload,
        )
        publish_fn(env)
    except Exception as exc:
        _log.warning("bus_publish failed topic=%s: %s", topic, exc)


# In-process subscriber registry for agent-inbox simulation
_agent_inboxes: dict[str, list[Any]] = {}
_agent_inbox_lock = threading.Lock()

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
    """Publish an agent→agent message onto the bus and local inbox."""
    payload = {"target": target, "message": message}
    _bus_publish("swarm:agent:send", payload)
    # Also deliver to local in-process inbox so agent_receive works
    with _agent_inbox_lock:
        _agent_inboxes.setdefault(target, []).append(message)
    return True


def agent_receive(target: str) -> list[Any]:
    """Drain the in-process inbox for *target* agent."""
    with _agent_inbox_lock:
        messages = _agent_inboxes.pop(target, [])
    if messages:
        _bus_publish("swarm:agent:receive", {"target": target, "count": len(messages)})
    return messages


def agent_ack(message_id: str) -> bool:
    """Acknowledge a message — published as a bus event."""
    _bus_publish("swarm:agent:ack", {"message_id": message_id})
    return True


# ── Additional Stubs for Organs Migration ─────────────────────────────────


class AgentProfile:
    """Stub for AgentProfile."""

    def __init__(self, **kwargs: Any) -> None:
        self.agent_id: str = kwargs.get("agent_id", "")
        self.persona: str = kwargs.get("persona", "")
        self.capabilities: list[str] = kwargs.get("capabilities", [])


class IntentParticle:
    """Stub for IntentParticle."""

    def __init__(self, **kwargs: Any) -> None:
        self.intent: str = kwargs.get("intent", "")
        self.particle_type: str = kwargs.get("particle_type", "VISION")
        self.estimated_eu: float = kwargs.get("estimated_eu", 10.0)


class MetabolicStage(StrEnum):
    """Stub for MetabolicStage."""

    RAW = "RAW"
    PARSED = "PARSED"
    METABOLIZED = "METABOLIZED"


class VisionParser:
    """Stub for VisionParser."""

    def parse(self, vision_text: str, total_eu_budget: float = 0.0) -> list[Any]:
        return []


WORKER_REGISTRY: dict[str, Any] = {}


def get_worker_profile(worker_id: str, overrides: dict[str, Any] | None = None) -> Any:
    """Stub for get_worker_profile."""

    class _StubProfile:
        def to_dict(self) -> dict[str, Any]:
            return {}

    return _StubProfile()


def build_agent_cli_handle(*args: Any, **kwargs: Any) -> Any:
    return None


def inject_agent_cli_soul_env(*args: Any, **kwargs: Any) -> Any:
    return {}


def prepare_agent_cli_bootstrap(*args: Any, **kwargs: Any) -> Any:
    return None


def resolve_agent_cli_command(*args: Any, **kwargs: Any) -> list[str]:
    return []


def spawn_agent_cli_process(*args: Any, **kwargs: Any) -> Any:
    return None


class WorkerProcessExitedError(Exception):
    """Stub for WorkerProcessExitedError."""


class WorkerProcessStartTimeoutError(Exception):
    """Stub for WorkerProcessStartTimeoutError."""


def build_active_worker_handle(*args: Any, **kwargs: Any) -> Any:
    return None


def inject_soul_env(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {}


class HatchError(Exception):
    """Exception raised when hatcher fails."""


class HatchTimeoutError(Exception):
    """Exception raised when hatching process times out."""


def spawn_worker_process(*args: Any, **kwargs: Any) -> Any:
    return None


def wait_for_worker_process_start(*args: Any, **kwargs: Any) -> Any:
    return None


def emit_worker_hatched(
    worker_id: str = "",
    task_type: str = "",
    pid: int = 0,
    **kwargs: Any,
) -> None:
    """Publish a 'worker hatched' event onto the bus."""
    _bus_publish(
        "swarm:worker:hatched",
        {"worker_id": worker_id, "task_type": task_type, "pid": pid, **kwargs},
    )


def emit_worker_terminated(
    worker_id: str = "",
    reason: str = "",
    eu_consumed: float = 0.0,
    **kwargs: Any,
) -> None:
    """Publish a 'worker terminated' event onto the bus."""
    _bus_publish(
        "swarm:worker:terminated",
        {"worker_id": worker_id, "reason": reason, "eu_consumed": eu_consumed, **kwargs},
    )


class RetryExhaustedError(Exception):
    """Stub for RetryExhaustedError."""


class RetryPolicy:
    """Stub for RetryPolicy."""


class RetryState:
    """Stub for RetryState."""


class TaskState(StrEnum):
    """Stub for TaskState."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class TaskStore:
    """Stub for TaskStore with basic in-memory implementation."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._tasks: dict[str, dict[str, Any]] = {}

    def transition(self, task_id: str, state: Any, **kwargs: Any) -> None:
        self._tasks[task_id] = {"state": state, **kwargs}

    def schedule_retry(self, task_id: str) -> None:
        pass


class TaskRecord:
    """Stub for TaskRecord."""

    def __init__(self, task_id: str = "", state: Any = None, **kwargs: Any) -> None:
        self.task_id = task_id
        self.state = state


class TaskRequest:
    """Stub for TaskRequest."""

    def __init__(
        self, task_id: str = "", required_capabilities: list[str] | None = None, priority: int = 5, **kwargs: Any
    ) -> None:
        self.task_id = task_id
        self.required_capabilities = required_capabilities or []
        self.priority = priority


class TaskEnvelope:
    """Stub for TaskEnvelope."""

    def __init__(self, task_id: str = "", payload: dict[str, Any] | None = None, **kwargs: Any) -> None:
        self.task_id = task_id
        self.payload = payload or {}


class SwarmDispatchError(Exception):
    """Stub for SwarmDispatchError."""


class SwarmLifecycleManagerClass:
    """Stub for SwarmLifecycleManager."""


class CapabilityMatcher:
    """Stub for CapabilityMatcher."""

    def match(self, task_description: str, capabilities: list[str]) -> list[str]:
        return capabilities


class IntentDigestor:
    """Stub for IntentDigestor."""

    def digest(self, intent: str) -> list[Any]:
        return []


class LLMRequest:
    """Stub for LLMRequest."""

    def __init__(self, prompt: str = "", system: str = "", **kwargs: Any) -> None:
        self.prompt = prompt
        self.system = system


class LLMProvider:
    """Stub for LLMProvider."""

    def __init__(self, name: str = "", **kwargs: Any) -> None:
        self.name = name


class LLMResponse:
    """Stub for LLMResponse."""

    def __init__(self, text: str = "", **kwargs: Any) -> None:
        self.text = text


def get_default_factory() -> Any:
    """Stub for get_default_factory."""
    return None


def get_default_voice_session_particle_queue() -> Any:
    """Stub for get_default_voice_session_particle_queue."""
    return None


def get_quota_aware_priority() -> list[str]:
    """Stub for get_quota_aware_priority."""
    return []


def _thread_worker(*args: Any, **kwargs: Any) -> Any:
    return None
