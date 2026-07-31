"""Unit + integration tests for runtime.registry.task_fallback — TaskFallbackManager."""

from __future__ import annotations

import pytest

from runtime.registry.dispatch import Dispatcher, TaskRequest
from runtime.registry.models import AgentInfo, AgentStatus, Capability
from runtime.registry.store import RegistryStore
from runtime.registry.task_fallback import (
    FallbackResult,
    TaskFallbackEvent,
    TaskFallbackManager,
)


def _make_agent(name: str, caps: list[str]) -> AgentInfo:
    return AgentInfo(
        name=name,
        capabilities=[Capability(name=c) for c in caps],
        status=AgentStatus.IDLE,
        max_concurrency=1,
    )


class TestTaskFallbackEvent:
    def test_to_dict(self):
        e = TaskFallbackEvent(
            task_id="t1",
            task_name="test",
            result=FallbackResult.DISPATCHED,
            attempts=1,
            total_wait_ms=5.0,
        )
        d = e.to_dict()
        assert d["task_id"] == "t1"
        assert d["result"] == "dispatched"
        assert d["attempts"] == 1


class TestTaskFallbackManagerUnit:
    def test_immediate_dispatch(self):
        store = RegistryStore()
        store.register_agent(_make_agent("w1", ["coding"]))
        dispatcher = Dispatcher(store)
        fm = TaskFallbackManager(dispatcher, max_retries=0, base_delay=0.01)

        req = TaskRequest(name="t1", required_capabilities=["coding"])
        import asyncio
        event = asyncio.run(fm.submit_with_fallback(req))

        assert event.result == FallbackResult.DISPATCHED
        assert event.attempts == 1

    def test_escalation_after_max_retries(self):
        store = RegistryStore()
        # No agents → always fails
        dispatcher = Dispatcher(store)
        fm = TaskFallbackManager(dispatcher, max_retries=2, base_delay=0.01)

        req = TaskRequest(name="doomed", required_capabilities=["coding"])
        import asyncio
        event = asyncio.run(fm.submit_with_fallback(req))

        assert event.result == FallbackResult.ESCALATED
        assert event.attempts == 3  # 1 immediate + 2 retries
        assert "Failed after" in event.error

    def test_retry_succeeds_on_second_attempt(self):
        """Agent registered during retry window → dispatch succeeds."""
        store = RegistryStore()
        dispatcher = Dispatcher(store)
        fm = TaskFallbackManager(dispatcher, max_retries=5, base_delay=0.05)

        # Schedule an agent to appear after 150ms
        async def _add_agent_later():
            await asyncio.sleep(0.15)
            store.register_agent(_make_agent("late-worker", ["coding"]))

        async def _run():
            import asyncio
            asyncio.create_task(_add_agent_later())
            req = TaskRequest(name="patient", required_capabilities=["coding"])
            return await fm.submit_with_fallback(req)

        import asyncio
        event = asyncio.run(_run())

        assert event.result == FallbackResult.DISPATCHED
        assert event.attempts >= 2  # succeeded on retry

    def test_retry_pending(self):
        """Escalated tasks can be retried via retry_pending()."""
        store = RegistryStore()
        dispatcher = Dispatcher(store)
        fm = TaskFallbackManager(dispatcher, max_retries=0, base_delay=0.01)

        import asyncio
        # Escalate a task
        req = TaskRequest(name="stuck", required_capabilities=["coding"])
        event = asyncio.run(fm.submit_with_fallback(req))
        assert event.result == FallbackResult.ESCALATED
        assert len(fm._pending_retries) == 1

        # Now add an agent and retry
        store.register_agent(_make_agent("rescuer", ["coding"]))
        events = fm.retry_pending()
        assert len(events) == 1
        assert events[0].result == FallbackResult.DISPATCHED
        assert len(fm._pending_retries) == 0

    def test_status(self):
        store = RegistryStore()
        dispatcher = Dispatcher(store)
        fm = TaskFallbackManager(dispatcher, max_retries=3, base_delay=0.5)

        status = fm.get_status()
        assert status["total_events"] == 0
        assert status["dispatched"] == 0
        assert status["escalated"] == 0
        assert status["pending_retries"] == 0
        assert status["max_retries"] == 3
        assert status["base_delay"] == 0.5

    def test_backoff_delay_capped(self):
        store = RegistryStore()
        dispatcher = Dispatcher(store)
        fm = TaskFallbackManager(dispatcher, base_delay=1.0, max_delay=10.0)

        # Attempt 1: 1.0, Attempt 2: 2.0, Attempt 3: 4.0, Attempt 4: 8.0, Attempt 5: 10.0 (capped)
        assert fm._backoff_delay(1) == 1.0
        assert fm._backoff_delay(2) == 2.0
        assert fm._backoff_delay(3) == 4.0
        assert fm._backoff_delay(5) == 10.0  # capped

    def test_get_events_limit(self):
        store = RegistryStore()
        dispatcher = Dispatcher(store)
        fm = TaskFallbackManager(dispatcher)

        # Manually inject events
        fm._events = [
            TaskFallbackEvent(
                task_id=f"t{i}",
                task_name=f"task-{i}",
                result=FallbackResult.DISPATCHED,
                attempts=1,
                total_wait_ms=1.0,
            )
            for i in range(25)
        ]
        events = fm.get_events(limit=10)
        assert len(events) == 10
