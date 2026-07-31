"""Unit tests for dispatch.py — capability-based task dispatcher."""

from __future__ import annotations

import pytest

from runtime.registry.dispatch import Dispatcher, TaskAssignment, TaskRequest, TaskStatus
from runtime.registry.models import AgentInfo, AgentStatus, Capability
from runtime.registry.store import RegistryStore


@pytest.fixture
def store() -> RegistryStore:
    return RegistryStore()


@pytest.fixture
def dispatcher(store: RegistryStore) -> Dispatcher:
    return Dispatcher(store)


def _reg(store: RegistryStore, agent_id: str, *, caps: list[str] | None = None,
         status: AgentStatus = AgentStatus.IDLE, active: int = 0) -> None:
    store.register_agent(AgentInfo(
        agent_id=agent_id, name=agent_id,
        capabilities=[Capability(name=c) for c in (caps or [])],
        status=status, active_tasks=active, max_concurrency=2,
    ))


# ── TaskRequest / TaskAssignment ────────────────────────────────────────────


class TestTaskRequest:
    def test_default_values(self) -> None:
        req = TaskRequest()
        assert req.task_id
        assert req.required_capabilities == []

    def test_custom_values(self) -> None:
        req = TaskRequest(task_id="t1", name="coding", required_capabilities=["coding"], priority=10)
        assert req.task_id == "t1"
        assert req.required_capabilities == ["coding"]


class TestTaskAssignment:
    def test_fields(self) -> None:
        a = TaskAssignment(task_id="t1", agent_id="a1", agent_name="agent1")
        assert a.task_id == "t1"
        assert a.agent_id == "a1"
        assert a.status == TaskStatus.DISPATCHED


# ── Dispatcher.submit ───────────────────────────────────────────────────────


class TestDispatcherSubmit:
    def test_submit_no_agents(self, dispatcher: Dispatcher) -> None:
        assignment = dispatcher.submit(TaskRequest(task_id="t1", required_capabilities=["coding"]))
        assert assignment is None
        assert len(dispatcher.get_pending()) == 1

    def test_submit_assigns_to_idle(self, dispatcher: Dispatcher, store: RegistryStore) -> None:
        _reg(store, "agent-1", caps=["coding", "testing"])
        assignment = dispatcher.submit(TaskRequest(task_id="t1", required_capabilities=["coding"]))
        assert assignment is not None
        assert assignment.status == TaskStatus.DISPATCHED

    def test_submit_respects_capabilities(self, dispatcher: Dispatcher, store: RegistryStore) -> None:
        _reg(store, "agent-1", caps=["coding"])
        assignment = dispatcher.submit(TaskRequest(task_id="t1", required_capabilities=["nonexistent"]))
        assert assignment is None

    def test_submit_selects_lowest_load(self, dispatcher: Dispatcher, store: RegistryStore) -> None:
        _reg(store, "agent-1", caps=["coding"], active=1, status=AgentStatus.BUSY)
        _reg(store, "agent-2", caps=["coding"], active=0)
        assignment = dispatcher.submit(TaskRequest(task_id="t1", required_capabilities=["coding"]))
        assert assignment.agent_id == "agent-2"


# ── Dispatcher.dispatch_pending ─────────────────────────────────────────────


class TestDispatchPending:
    def test_dispatch_pending_empty(self, dispatcher: Dispatcher) -> None:
        assert dispatcher.dispatch_pending() == []

    def test_dispatch_pending_later_agents(self, dispatcher: Dispatcher, store: RegistryStore) -> None:
        dispatcher.submit(TaskRequest(task_id="t1", required_capabilities=["coding"]))
        assert len(dispatcher.get_pending()) == 1
        _reg(store, "a1", caps=["coding"])
        assigned = dispatcher.dispatch_pending()
        assert len(assigned) == 1
        assert len(dispatcher.get_pending()) == 0


# ── Dispatcher.complete / fail ──────────────────────────────────────────────


class TestDispatcherComplete:
    def test_complete(self, dispatcher: Dispatcher, store: RegistryStore) -> None:
        _reg(store, "a1", caps=["coding"])
        dispatcher.submit(TaskRequest(task_id="t1", required_capabilities=["coding"]))
        assert dispatcher.complete("t1") is True
        assert len(dispatcher.get_assignments(TaskStatus.COMPLETED)) == 1

    def test_complete_nonexistent(self, dispatcher: Dispatcher) -> None:
        assert dispatcher.complete("nonexistent") is False


class TestDispatcherFail:
    def test_fail(self, dispatcher: Dispatcher, store: RegistryStore) -> None:
        _reg(store, "a1", caps=["coding"])
        dispatcher.submit(TaskRequest(task_id="t1", required_capabilities=["coding"]))
        assert dispatcher.fail("t1") is True
        assert len(dispatcher.get_assignments(TaskStatus.FAILED)) == 1

    def test_fail_nonexistent(self, dispatcher: Dispatcher) -> None:
        assert dispatcher.fail("nonexistent") is False


# ── Dispatcher.failover_node ────────────────────────────────────────────────


class TestDispatcherFailoverNode:
    def test_failover_requeues(self, dispatcher: Dispatcher, store: RegistryStore) -> None:
        _reg(store, "a1", caps=["coding"])
        store.update_agent("a1", node_id="node1")
        dispatcher.submit(TaskRequest(task_id="t1", required_capabilities=["coding"]))
        reassigned = dispatcher.failover_node("node1")
        assert isinstance(reassigned, list)


# ── Dispatcher.stats ────────────────────────────────────────────────────────


class TestDispatcherStats:
    def test_stats_empty(self, dispatcher: Dispatcher) -> None:
        s = dispatcher.stats()
        assert s["total_submitted"] == 0
        assert s["pending"] == 0

    def test_stats_with_tasks(self, dispatcher: Dispatcher, store: RegistryStore) -> None:
        _reg(store, "a1", caps=["coding"])
        dispatcher.submit(TaskRequest(task_id="t1", required_capabilities=["coding"]))
        dispatcher.submit(TaskRequest(task_id="t2", required_capabilities=["nonexistent"]))
        s = dispatcher.stats()
        assert s["total_submitted"] == 2
        assert s["pending"] == 1
