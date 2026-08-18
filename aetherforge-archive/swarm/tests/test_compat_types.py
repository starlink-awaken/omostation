"""Tests for swarm_engine._compat — data classes, enums, and type stubs."""

from __future__ import annotations

# ── Enums ──────────────────────────────────────────────────────────────────


class TestTaskType:
    def test_enum_values(self):
        from swarm_engine._compat import TaskType

        assert TaskType.CODE_GENERATION.value == "CODE_GENERATION"
        assert TaskType.RESEARCH.value == "RESEARCH"
        assert TaskType.UNKNOWN.value == "UNKNOWN"
        assert len(TaskType) >= 10


class TestWorkerState:
    def test_enum_values(self):
        from swarm_engine._compat import WorkerState

        assert WorkerState.HATCHING.value == "HATCHING"
        assert WorkerState.ACTIVE.value == "ACTIVE"
        assert WorkerState.IDLE.value == "IDLE"
        assert WorkerState.TERMINATED.value == "TERMINATED"


class TestPriority:
    def test_enum_values(self):
        from swarm_engine._compat import Priority

        assert Priority.LOW.value == "LOW"
        assert Priority.CRITICAL.value == "CRITICAL"


class TestGovernanceAction:
    def test_enum_values(self):
        from swarm_engine._compat import GovernanceAction

        assert GovernanceAction.HATCH.value == "HATCH"
        assert GovernanceAction.TERMINATE.value == "TERMINATE"
        assert GovernanceAction.DOWNGRADE.value == "DOWNGRADE"


class TestMetabolicStage:
    def test_enum_values(self):
        from swarm_engine._compat import MetabolicStage

        assert MetabolicStage.RAW.value == "RAW"
        assert MetabolicStage.PARSED.value == "PARSED"
        assert MetabolicStage.METABOLIZED.value == "METABOLIZED"


class TestTaskState:
    def test_enum_values(self):
        from swarm_engine._compat import TaskState

        assert TaskState.PENDING.value == "PENDING"
        assert TaskState.RUNNING.value == "RUNNING"
        assert TaskState.SUCCESS.value == "SUCCESS"
        assert TaskState.FAILED.value == "FAILED"


# ── Data Classes ───────────────────────────────────────────────────────────


class TestReceipt:
    def test_receipt(self):
        from swarm_engine._compat import Receipt

        r = Receipt(envelope_id="env-123")
        assert r.envelope_id == "env-123"


class TestMessageEnvelope:
    def test_default_envelope(self):
        from swarm_engine._compat import MessageEnvelope

        env = MessageEnvelope()
        assert env.id == ""
        assert env.task_type == ""
        assert env.eu_budget == 0.0
        assert env.payload == {}

    def test_custom_envelope(self):
        from swarm_engine._compat import MessageEnvelope

        env = MessageEnvelope(id="msg-1", task_type="CODE", eu_budget=10.0, payload={"key": "val"})
        assert env.id == "msg-1"
        assert env.task_type == "CODE"
        assert env.eu_budget == 10.0
        assert env.payload == {"key": "val"}

    def test_kwargs_as_attributes(self):
        from swarm_engine._compat import MessageEnvelope

        env = MessageEnvelope(id="msg-1", extra_field="extra_value")
        assert env.extra_field == "extra_value"  # type: ignore[reportAttributeAccessIssue]


class TestSynapseAgentCard:
    def test_default_card(self):
        from swarm_engine._compat import SynapseAgentCard

        card = SynapseAgentCard()
        assert card.capabilities == []
        assert card.cost_class == "medium"
        assert card.mode == "active"
        assert card.max_eu_budget == 50.0

    def test_custom_card(self):
        from swarm_engine._compat import SynapseAgentCard

        card = SynapseAgentCard(capabilities=["code", "review"], cost_class="high", max_eu_budget=100.0)
        assert card.capabilities == ["code", "review"]
        assert card.cost_class == "high"
        assert card.max_eu_budget == 100.0


class TestPlannedStep:
    def test_default_step(self):
        from swarm_engine._compat import PlannedStep, Priority, TaskType

        step = PlannedStep()
        assert step.task_type == TaskType.UNKNOWN
        assert step.description == ""
        assert step.priority == Priority.MEDIUM
        assert step.step_id == ""
        assert step.dependencies == []
        assert step.estimated_eu == 1.0

    def test_custom_step(self):
        from swarm_engine._compat import PlannedStep, Priority, TaskType

        step = PlannedStep(
            task_type=TaskType.CODE_GENERATION,
            description="Generate code",
            priority=Priority.HIGH,
            step_id="step-1",
            estimated_eu=5.0,
            suggested_capability="code",
        )
        assert step.task_type == TaskType.CODE_GENERATION
        assert step.description == "Generate code"
        assert step.priority == Priority.HIGH
        assert step.step_id == "step-1"
        assert step.estimated_eu == 5.0


class TestExecutionPlan:
    def test_default_plan(self):
        from swarm_engine._compat import ExecutionPlan

        plan = ExecutionPlan()
        assert plan.steps == []
        assert plan.plan_id == ""
        assert plan.confidence == 0.0
        assert plan.fallback_used is False

    def test_plan_with_steps(self):
        from swarm_engine._compat import ExecutionPlan, PlannedStep

        steps = [PlannedStep(step_id="s1"), PlannedStep(step_id="s2")]
        plan = ExecutionPlan(steps=steps, plan_id="plan-1", confidence=0.9)
        assert len(plan.steps) == 2
        assert plan.plan_id == "plan-1"
        assert plan.confidence == 0.9


class TestTaskResult:
    def test_task_result(self):
        from swarm_engine._compat import TaskResult

        result = TaskResult(task_id="t1", success=True, data={"output": "ok"}, worker_id="w1", eu_consumed=5.0)
        assert result.task_id == "t1"
        assert result.success is True
        assert result.data == {"output": "ok"}
        assert result.worker_id == "w1"
        assert result.eu_consumed == 5.0

    def test_task_result_failure(self):
        from swarm_engine._compat import TaskResult

        result = TaskResult(task_id="t1", success=False, error="something went wrong")
        assert result.success is False
        assert result.error == "something went wrong"


# ── Governance State ─────────────────────────────────────────────────────


class TestGovernanceState:
    def test_normal_state(self):
        from swarm_engine._compat import GovernanceAction, GovernanceState

        gs = GovernanceState.NORMAL()
        assert gs.status == "NORMAL"

        event = gs.apply_action(GovernanceAction.HATCH, actor_id="actor-1", reason="need more")
        assert event.action == GovernanceAction.HATCH
        assert event.reason == "need more"
        assert event.actor_id == "actor-1"

    def test_degraded_state(self):
        from swarm_engine._compat import GovernanceState

        gs = GovernanceState.DEGRADED()
        assert gs.status == "DEGRADED"

    def test_critical_state(self):
        from swarm_engine._compat import GovernanceState

        gs = GovernanceState.CRITICAL()
        assert gs.status == "CRITICAL"


# ── Stub Classes ──────────────────────────────────────────────────────────


class TestWorkerHandle:
    def test_worker_handle_defaults(self):
        from swarm_engine._compat import WorkerHandle, WorkerState

        wh = WorkerHandle()
        assert wh.worker_id == ""
        assert wh.state == WorkerState.ACTIVE
        assert wh.pid == 0
        assert wh.eu_consumed == 0.0

    def test_worker_handle_setters(self):
        from swarm_engine._compat import WorkerHandle, WorkerState

        wh = WorkerHandle()
        wh.worker_id = "w-1"
        wh.state = WorkerState.BUSY
        wh.pid = 12345
        wh.eu_consumed = 10.0

        assert wh.worker_id == "w-1"
        assert wh.state == WorkerState.BUSY
        assert wh.pid == 12345
        assert wh.eu_consumed == 10.0

    def test_worker_handle_kwargs(self):
        from swarm_engine._compat import WorkerHandle

        wh = WorkerHandle(extra="value", flag=True)
        assert wh.extra == "value"  # type: ignore[reportAttributeAccessIssue]
        assert wh.flag is True  # type: ignore[reportAttributeAccessIssue]


class TestWorkerBundle:
    def test_default_bundle(self):
        from swarm_engine._compat import TaskType, WorkerBundle

        bundle = WorkerBundle()
        assert bundle.task_type == TaskType.UNKNOWN
        assert bundle.total_eu_consumed == 0.0
        assert bundle.total_tasks == 0
        assert bundle.successful_tasks == 0

    def test_bundle_with_args(self):
        from swarm_engine._compat import TaskType, WorkerBundle

        bundle = WorkerBundle(None, TaskType.CODE_GENERATION, (), 100.0, 10, 8, 50.0)
        assert bundle.task_type == TaskType.CODE_GENERATION
        assert bundle.total_eu_consumed == 100.0
        assert bundle.total_tasks == 10
        assert bundle.successful_tasks == 8
        assert bundle.nectar_earned == 50.0


class TestAgentDaemonBase:
    def test_default_daemon(self):
        from swarm_engine._compat import AgentDaemonBase

        daemon = AgentDaemonBase(agent_id="a1", persona="coder")
        assert daemon.agent_id == "a1"
        assert daemon.persona == "coder"
        assert daemon.capabilities == []
        assert daemon.running is False
        assert daemon.current_eu == 100.0

    def test_run_and_stop(self):
        from swarm_engine._compat import AgentDaemonBase

        daemon = AgentDaemonBase()
        daemon.run()
        assert daemon.running is True

        daemon.stop()
        assert daemon.running is False

    def test_shutdown(self):
        from swarm_engine._compat import AgentDaemonBase

        daemon = AgentDaemonBase()
        daemon.run()
        daemon.shutdown()
        assert daemon.running is False


class TestTaskStore:
    def test_task_store(self):
        from swarm_engine._compat import TaskStore

        store = TaskStore()
        assert store.db_path == ":memory:"
        assert store._tasks == {}

    def test_transition(self):
        from swarm_engine._compat import TaskState, TaskStore

        store = TaskStore()
        store.transition("task-1", TaskState.RUNNING, extra="data")
        assert "task-1" in store._tasks
        assert store._tasks["task-1"]["state"] == TaskState.RUNNING
        assert store._tasks["task-1"]["extra"] == "data"

    def test_schedule_retry(self):
        from swarm_engine._compat import TaskStore

        store = TaskStore()
        store.schedule_retry("task-1")  # should not raise


# ── Exception Stubs ───────────────────────────────────────────────────────


class TestExceptions:
    def test_hatch_error(self):
        from swarm_engine._compat import HatchError

        err = HatchError("hatch failed")
        assert str(err) == "hatch failed"
        assert isinstance(err, Exception)

    def test_hatch_timeout_error(self):
        from swarm_engine._compat import HatchTimeoutError

        err = HatchTimeoutError("timeout")
        assert str(err) == "timeout"
        assert isinstance(err, Exception)

    def test_retry_exhausted_error(self):
        from swarm_engine._compat import RetryExhaustedError

        err = RetryExhaustedError("retries exhausted")
        assert str(err) == "retries exhausted"
        assert isinstance(err, Exception)

    def test_worker_process_exited_error(self):
        from swarm_engine._compat import WorkerProcessExitedError

        err = WorkerProcessExitedError("worker exited")
        assert isinstance(err, Exception)

    def test_worker_process_start_timeout_error(self):
        from swarm_engine._compat import WorkerProcessStartTimeoutError

        err = WorkerProcessStartTimeoutError("start timeout")
        assert isinstance(err, Exception)

    def test_swarm_dispatch_error(self):
        from swarm_engine._compat import SwarmDispatchError

        err = SwarmDispatchError("dispatch failed")
        assert isinstance(err, Exception)


# ── Stub Functions ────────────────────────────────────────────────────────


class TestStubFunctions:
    def test_get_synapse_registry(self):
        from swarm_engine._compat import get_synapse_registry

        reg = get_synapse_registry()
        assert reg is not None

    def test_get_spore_gateway(self):
        from swarm_engine._compat import get_spore_gateway

        gw = get_spore_gateway()
        assert gw is not None

    def test_get_synapse_router(self):
        from swarm_engine._compat import get_synapse_router

        router = get_synapse_router()
        assert router is not None

    def test_get_path_resolver(self):
        from swarm_engine._compat import get_path_resolver

        resolver = get_path_resolver()
        assert resolver is None  # stub returns None

    def test_get_default_factory(self):
        from swarm_engine._compat import get_default_factory

        factory = get_default_factory()
        assert factory is None

    def test_get_default_voice_session_particle_queue(self):
        from swarm_engine._compat import get_default_voice_session_particle_queue

        queue = get_default_voice_session_particle_queue()
        assert queue is None

    def test_get_quota_aware_priority(self):
        from swarm_engine._compat import get_quota_aware_priority

        priorities = get_quota_aware_priority()
        assert priorities == []


# ── ProjectPaths ──────────────────────────────────────────────────────────


class TestProjectPaths:
    def test_root(self):
        from swarm_engine._compat import ProjectPaths

        assert ProjectPaths.ROOT == "."

    def test_get_core_db_path(self):
        from swarm_engine._compat import ProjectPaths

        assert ProjectPaths.get_core_db_path("test.db") == "test.db"

    def test_get_db_path(self):
        from swarm_engine._compat import ProjectPaths

        assert ProjectPaths.get_db_path("test.db") == "test.db"


# ── InferenceOracle ───────────────────────────────────────────────────────


class TestInferenceOracle:
    def test_get_instance(self):
        from swarm_engine._compat import InferenceOracle

        oracle = InferenceOracle.get_instance()
        assert isinstance(oracle, InferenceOracle)

    def test_infer(self):
        from swarm_engine._compat import InferenceOracle

        oracle = InferenceOracle.get_instance()
        result = oracle.infer("test prompt")
        assert result is None


# ── Stub Class Instantiation ──────────────────────────────────────────────


class TestStubClasses:
    def test_agent_profile(self):
        from swarm_engine._compat import AgentProfile

        ap = AgentProfile(agent_id="a1", persona="coder", capabilities=["code"])
        assert ap.agent_id == "a1"
        assert ap.persona == "coder"
        assert ap.capabilities == ["code"]

    def test_intent_particle(self):
        from swarm_engine._compat import IntentParticle

        ip = IntentParticle(intent="write tests", particle_type="VISION", estimated_eu=10.0)
        assert ip.intent == "write tests"
        assert ip.particle_type == "VISION"
        assert ip.estimated_eu == 10.0

    def test_task_record(self):
        from swarm_engine._compat import TaskRecord

        tr = TaskRecord(task_id="t1", state="RUNNING")
        assert tr.task_id == "t1"
        assert tr.state == "RUNNING"

    def test_task_request(self):
        from swarm_engine._compat import TaskRequest

        tr = TaskRequest(task_id="t1", required_capabilities=["code", "review"], priority=3)
        assert tr.task_id == "t1"
        assert tr.required_capabilities == ["code", "review"]
        assert tr.priority == 3

    def test_task_envelope(self):
        from swarm_engine._compat import TaskEnvelope

        te = TaskEnvelope(task_id="t1", payload={"key": "val"})
        assert te.task_id == "t1"
        assert te.payload == {"key": "val"}

    def test_capability_matcher(self):
        from swarm_engine._compat import CapabilityMatcher

        cm = CapabilityMatcher()
        result = cm.match("test task", ["code", "review"])
        assert result == ["code", "review"]

    def test_intent_digestor(self):
        from swarm_engine._compat import IntentDigestor

        digestor = IntentDigestor()
        result = digestor.digest("build a web app")
        assert result == []

    def test_llm_request_response(self):
        from swarm_engine._compat import LLMRequest, LLMResponse

        req = LLMRequest(prompt="hello", system="you are helpful")
        assert req.prompt == "hello"
        assert req.system == "you are helpful"

        resp = LLMResponse(text="hi there")
        assert resp.text == "hi there"
