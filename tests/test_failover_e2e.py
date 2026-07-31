"""E2E integration tests for the failover system.

Wires real RegistryStore + Dispatcher + FailoverManager together
(no mocks) to verify:
  1. Task dispatch → agent assignment
  2. Agent failure → task reassignment to healthy agent
  3. All agents down → fallback queuing
  4. Node-level failover via Dispatcher.failover_node()
  5. Pending task dispatch on agent recovery
"""

from __future__ import annotations

import pytest

from runtime.registry.dispatch import Dispatcher, TaskRequest
from runtime.registry.failover import FailoverManager
from runtime.registry.models import AgentInfo, AgentStatus, Capability
from runtime.registry.store import RegistryStore


def _make_agent(name: str, caps: list[str], node_id: str = "node-a") -> AgentInfo:
    return AgentInfo(
        name=name,
        node_id=node_id,
        capabilities=[Capability(name=c) for c in caps],
        status=AgentStatus.IDLE,
        max_concurrency=2,
    )


@pytest.fixture
def store():
    return RegistryStore()  # in-memory


@pytest.fixture
def dispatcher(store):
    return Dispatcher(store)


@pytest.fixture
def fm(store, dispatcher):
    return FailoverManager(store, dispatcher)


class TestFailoverE2E:
    """Real-component integration: Store + Dispatcher + FailoverManager."""

    @pytest.mark.asyncio
    async def test_dispatch_and_reassign_on_failure(self, store, dispatcher, fm):
        """Agent goes down → FailoverManager reassigns to healthy peer."""
        a1 = store.register_agent(_make_agent("worker-1", ["coding", "review"]))
        a2 = store.register_agent(_make_agent("worker-2", ["coding", "review"]))

        # Submit task → dispatches to one agent
        task = TaskRequest(name="t1", required_capabilities=["coding"])
        assignment = dispatcher.submit(task)
        assert assignment is not None
        assert assignment.agent_id in (a1.agent_id, a2.agent_id)

        # Mark the assigned agent offline
        assigned_id = assignment.agent_id
        store.set_agent_status(assigned_id, AgentStatus.OFFLINE)

        # Sweep detects failure, emits reassignment event
        events = await fm.sweep()
        assert len(events) == 1
        assert events[0].event_type == "reassigned"
        assert events[0].target_agent_id != assigned_id

    @pytest.mark.asyncio
    async def test_all_agents_down_fallback_queue(self, store, fm, dispatcher):
        """All agents offline → task goes to fallback queue."""
        a1 = store.register_agent(_make_agent("solo-worker", ["coding"]))
        store.update_agent(a1.agent_id, active_tasks=1, status=AgentStatus.OFFLINE)

        events = await fm.sweep()
        assert len(events) == 1
        assert events[0].event_type == "fallback_queued"

    @pytest.mark.asyncio
    async def test_no_events_when_all_healthy(self, store, fm, dispatcher):
        """No offline agents → sweep emits nothing."""
        store.register_agent(_make_agent("healthy", ["coding"]))
        events = await fm.sweep()
        assert events == []

    def test_dispatcher_failover_node(self, store, dispatcher):
        """Dispatcher.failover_node() requeues tasks from a failed node."""
        a1 = store.register_agent(_make_agent("node-a-worker", ["coding"], node_id="node-a"))
        a2 = store.register_agent(_make_agent("node-b-worker", ["coding"], node_id="node-b"))

        # Submit task → goes to one agent
        task = TaskRequest(name="critical", required_capabilities=["coding"])
        assignment = dispatcher.submit(task)
        assert assignment is not None

        # Determine which node got the task, then fail that node
        assigned_agent = store.get_agent(assignment.agent_id)
        failed_node = assigned_agent.node_id

        reassigned = dispatcher.failover_node(failed_node)
        # Task reassigned to the other node's agent
        assert len(reassigned) >= 1
        expected_peer = a2.agent_id if failed_node == "node-a" else a1.agent_id
        assert reassigned[0].agent_id == expected_peer

    def test_pending_tasks_dispatched_on_recovery(self, store, dispatcher):
        """Tasks pending due to capacity dispatch when agent recovers."""
        a1 = _make_agent("limited", ["coding"])
        a1.max_concurrency = 1
        store.register_agent(a1)

        # First task dispatches
        t1 = TaskRequest(name="first", required_capabilities=["coding"])
        dispatcher.submit(t1)
        assert store.get_agent(a1.agent_id).active_tasks == 1

        # Second task: agent at capacity → queued
        t2 = TaskRequest(name="second", required_capabilities=["coding"])
        assignment2 = dispatcher.submit(t2)
        assert assignment2 is None
        assert len(dispatcher.get_pending()) == 1

        # Complete first task → agent has capacity
        dispatcher.complete(t1.task_id)

        # Dispatch pending
        dispatched = dispatcher.dispatch_pending()
        assert len(dispatched) == 1
        assert dispatched[0].task_id == t2.task_id

    def test_failover_manager_status(self, fm):
        """FailoverManager.get_status() reflects internal state."""
        status = fm.get_status()
        assert status["running"] is False
        assert status["events_total"] == 0
        assert status["fallback_queue_size"] == 0
        assert status["sweep_interval"] == 30

    @pytest.mark.asyncio
    async def test_multiple_offline_agents_emit_multiple_events(self, store, dispatcher, fm):
        """Multiple offline agents with tasks → multiple events."""
        a1 = store.register_agent(_make_agent("w1", ["coding"]))
        a2 = store.register_agent(_make_agent("w2", ["coding"]))
        # Give them active tasks
        store.update_agent(a1.agent_id, active_tasks=2, status=AgentStatus.OFFLINE)
        store.update_agent(a2.agent_id, active_tasks=1, status=AgentStatus.OFFLINE)

        events = await fm.sweep()
        # Both offline agents should produce events (reassigned or fallback_queued)
        assert len(events) == 2
