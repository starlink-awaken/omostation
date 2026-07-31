"""Unit tests for runtime.registry.failover — FailoverManager module."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from runtime.registry.failover import FailoverEvent, FailoverManager
from runtime.registry.dispatch import Dispatcher, TaskRequest
from runtime.registry.store import RegistryStore


class TestFailoverEvent:
    def test_to_dict(self):
        e = FailoverEvent(
            agent_id="a1",
            event_type="reassigned",
            old_status="offline",
            new_status="idle",
            reassigned_task_id="t1",
            target_agent_id="a2",
        )
        d = e.to_dict()
        assert d["agent_id"] == "a1"
        assert d["event_type"] == "reassigned"
        assert d["target_agent_id"] == "a2"


class TestFailoverManager:
    @pytest.mark.asyncio
    async def test_start_stop(self):
        fm = FailoverManager(MagicMock(), MagicMock())
        await fm.start()
        assert fm._running is True
        await fm.stop()
        assert fm._running is False

    @pytest.mark.asyncio
    async def test_sweep_with_no_offline_agents(self):
        store = MagicMock()
        store.list_agents.return_value = []
        fm = FailoverManager(store, MagicMock())
        events = await fm.sweep()
        assert events == []

    @pytest.mark.asyncio
    async def test_sweep_with_offline_agent_no_tasks(self):
        agent = MagicMock()
        agent.status.value = "offline"
        agent.active_tasks = 0
        agent.agent_id = "a1"
        store = MagicMock()
        store.list_agents.return_value = [agent]
        fm = FailoverManager(store, MagicMock())
        events = await fm.sweep()
        assert events == []

    @pytest.mark.asyncio
    async def test_sweep_finds_alternative(self):
        down_agent = MagicMock()
        down_agent.status.value = "offline"
        down_agent.active_tasks = 2
        down_agent.agent_id = "a1"

        healthy_agent = MagicMock()
        healthy_agent.status.value = "idle"
        healthy_agent.load_ratio = 0.3
        healthy_agent.agent_id = "a2"

        store = MagicMock()
        store.list_agents.return_value = [down_agent, healthy_agent]
        fm = FailoverManager(store, MagicMock())
        events = await fm.sweep()
        assert len(events) == 1
        assert events[0].event_type == "reassigned"
        assert events[0].target_agent_id == "a2"

    @pytest.mark.asyncio
    async def test_sweep_no_alternative_queues_fallback(self):
        down_agent = MagicMock()
        down_agent.status.value = "offline"
        down_agent.active_tasks = 1
        down_agent.agent_id = "a1"

        store = MagicMock()
        store.list_agents.return_value = [down_agent]
        fm = FailoverManager(store, MagicMock())
        events = await fm.sweep()
        assert len(events) == 1
        assert events[0].event_type == "fallback_queued"

    def test_get_events(self):
        fm = FailoverManager(MagicMock(), MagicMock())
        fm._events = [FailoverEvent(agent_id=f"a{i}", event_type="test", old_status="idle", new_status="idle") for i in range(15)]
        events = fm.get_events(limit=5)
        assert len(events) == 5

    def test_get_status(self):
        fm = FailoverManager(MagicMock(), MagicMock())
        s = fm.get_status()
        assert s["running"] is False
        assert s["events_total"] == 0