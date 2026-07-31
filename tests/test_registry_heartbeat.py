"""Unit tests for heartbeat.py — heartbeat liveness manager."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import pytest

from runtime.registry.heartbeat import HeartbeatManager, DEFAULT_TTL, DEFAULT_ZOMBIE, DEFAULT_INTERVAL
from runtime.registry.models import AgentInfo, AgentStatus
from runtime.registry.store import RegistryStore


@pytest.fixture
def store() -> RegistryStore:
    return RegistryStore()


@pytest.fixture
def hb(store: RegistryStore) -> HeartbeatManager:
    return HeartbeatManager(store, heartbeat_ttl=5, zombie_threshold=10, check_interval=1)


def _reg(store: RegistryStore, agent_id: str, *, status: AgentStatus = AgentStatus.IDLE) -> None:
    store.register_agent(AgentInfo(agent_id=agent_id, name=agent_id, status=status))


# ── HeartbeatManager lifecycle ──────────────────────────────────────────────


class TestHeartbeatManagerLifecycle:
    def test_start_stop(self, hb: HeartbeatManager) -> None:
        hb.start()
        assert hb._running is True
        hb.stop()
        assert hb._running is False

    def test_double_start(self, hb: HeartbeatManager) -> None:
        hb.start()
        hb.start()
        assert hb._running is True
        hb.stop()


# ── HeartbeatManager.sweep ─────────────────────────────────────────────────


class TestSweep:
    def test_sweep_marks_stale_offline(self, hb: HeartbeatManager, store: RegistryStore) -> None:
        _reg(store, "a1", status=AgentStatus.BUSY)
        agent = store.get_agent("a1")
        agent.last_heartbeat = datetime.now(UTC) - timedelta(seconds=100)  # 100s ago
        hb.sweep()
        agent = store.get_agent("a1")
        assert agent.status == AgentStatus.OFFLINE

    def test_sweep_keeps_fresh(self, hb: HeartbeatManager, store: RegistryStore) -> None:
        _reg(store, "a1", status=AgentStatus.BUSY)
        agent = store.get_agent("a1")
        agent.last_heartbeat = datetime.now(UTC)  # now
        hb.sweep()
        agent = store.get_agent("a1")
        assert agent.status == AgentStatus.BUSY


# ── Constants ───────────────────────────────────────────────────────────────


class TestDefaults:
    def test_defaults(self) -> None:
        assert DEFAULT_TTL == 60
        assert DEFAULT_ZOMBIE == 3600
        assert DEFAULT_INTERVAL == 10
