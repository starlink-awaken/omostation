"""Tests for Agent Registry — 31 tests."""

from __future__ import annotations

import tempfile
import time
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from runtime.registry.dispatch import Dispatcher, TaskRequest, TaskStatus
from runtime.registry.heartbeat import HeartbeatManager
from runtime.registry.models import AgentInfo, AgentStatus, Capability, NodeInfo, NodeRole
from runtime.registry.server import create_app
from runtime.registry.store import RegistryStore


class TestCapability:
    def test_matches_name(self):
        cap = Capability(name="code-generation", tags=["python"])
        assert cap.matches("code")
        assert cap.matches("CODE-GENERATION")
        assert not cap.matches("deploy")

    def test_matches_tag(self):
        cap = Capability(name="deploy", tags=["kubernetes", "docker"])
        assert cap.matches("kubernetes")
        assert cap.matches("docker")
        assert not cap.matches("python")


class TestAgentInfo:
    def test_load_ratio(self):
        agent = AgentInfo(max_concurrency=4, active_tasks=2)
        assert agent.load_ratio == 0.5

    def test_load_ratio_saturated(self):
        agent = AgentInfo(max_concurrency=2, active_tasks=5)
        assert agent.load_ratio == 1.0

    def test_can_handle(self):
        agent = AgentInfo(capabilities=[Capability(name="code-generation", tags=["python"]), Capability(name="deploy")])
        assert agent.can_handle(["code-generation"])
        assert agent.can_handle(["deploy"])
        assert agent.can_handle(["code-generation", "deploy"])
        assert not agent.can_handle(["code-generation", "ml-training"])

    def test_to_dict_roundtrip(self):
        agent = AgentInfo(name="test-agent", capabilities=[Capability(name="code")])
        d = agent.to_dict()
        restored = AgentInfo.from_dict(d)
        assert restored.name == "test-agent"
        assert restored.capabilities[0].name == "code"


class TestRegistryStore:
    def test_register_and_list(self):
        store = RegistryStore()
        agent = AgentInfo(name="a1", capabilities=[Capability(name="code")])
        store.register_agent(agent)
        assert len(store.list_agents()) == 1
        assert store.get_agent(agent.agent_id) is not None

    def test_find_by_capability(self):
        store = RegistryStore()
        store.register_agent(AgentInfo(name="coder", capabilities=[Capability(name="code")]))
        store.register_agent(AgentInfo(name="deployer", capabilities=[Capability(name="deploy")]))
        found = store.find_agents(capabilities=["code"])
        assert len(found) == 1
        assert found[0].name == "coder"

    def test_find_by_status(self):
        store = RegistryStore()
        store.register_agent(AgentInfo(name="idle", status=AgentStatus.IDLE))
        store.register_agent(AgentInfo(name="busy", status=AgentStatus.BUSY))
        found = store.find_agents(status=AgentStatus.BUSY)
        assert len(found) == 1
        assert found[0].name == "busy"

    def test_heartbeat(self):
        store = RegistryStore()
        agent = AgentInfo(name="h")
        store.register_agent(agent)
        old_hb = agent.last_heartbeat
        time.sleep(0.01)
        assert store.heartbeat(agent.agent_id)
        assert store.get_agent(agent.agent_id).last_heartbeat > old_hb

    def test_remove(self):
        store = RegistryStore()
        agent = AgentInfo(name="r")
        store.register_agent(agent)
        assert store.remove_agent(agent.agent_id)
        assert store.get_agent(agent.agent_id) is None
        assert not store.remove_agent("nonexistent")

    def test_persistence(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        store1 = RegistryStore(persist_path=path)
        store1.register_agent(AgentInfo(name="persist"))
        store2 = RegistryStore(persist_path=path)
        assert len(store2.list_agents()) == 1
        assert store2.list_agents()[0].name == "persist"

    def test_node_registration(self):
        store = RegistryStore()
        node = NodeInfo(node_id="n1", host="localhost", port=8000)
        store.register_node(node)
        assert len(store.list_nodes()) == 1
        assert store.heartbeat_node("n1")
        assert not store.heartbeat_node("nonexistent")


class TestHeartbeatManager:
    def test_marks_stale_offline(self):
        store = RegistryStore()
        agent = AgentInfo(name="stale")
        agent.last_heartbeat = datetime.now(UTC) - timedelta(seconds=120)
        store.register_agent(agent)
        mgr = HeartbeatManager(store, heartbeat_ttl=60, check_interval=1)
        actions = mgr.sweep()
        assert agent.agent_id in actions["marked_offline"]
        assert store.get_agent(agent.agent_id).status == AgentStatus.OFFLINE

    def test_removes_zombies(self):
        store = RegistryStore()
        agent = AgentInfo(name="zombie", status=AgentStatus.OFFLINE)
        agent.last_heartbeat = datetime.now(UTC) - timedelta(seconds=7200)
        store.register_agent(agent)
        mgr = HeartbeatManager(store, heartbeat_ttl=60, zombie_threshold=3600)
        actions = mgr.sweep()
        assert agent.agent_id in actions["removed_zombies"]
        assert store.get_agent(agent.agent_id) is None


class TestRegistryServer:
    @pytest.fixture()
    def client(self):
        app = create_app()
        with TestClient(app) as c:
            yield c

    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_register_and_discover(self, client):
        r = client.post("/agents", json={"name": "coder", "endpoint": "http://localhost:9000", "capabilities": [{"name": "code-generation", "tags": ["python"]}]})
        assert r.status_code == 201
        agent_id = r.json()["agent_id"]
        r = client.get("/agents/find", params={"capability": "code-generation"})
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_heartbeat_endpoint(self, client):
        r = client.post("/agents", json={"name": "h"})
        agent_id = r.json()["agent_id"]
        r = client.post(f"/agents/{agent_id}/heartbeat")
        assert r.status_code == 200
        assert r.json()["ok"]

    def test_deregister(self, client):
        r = client.post("/agents", json={"name": "d"})
        agent_id = r.json()["agent_id"]
        r = client.delete(f"/agents/{agent_id}")
        assert r.status_code == 200
        r = client.get(f"/agents/{agent_id}")
        assert r.status_code == 404

    def test_node_register(self, client):
        r = client.post("/nodes", json={"host": "192.168.1.100", "port": 8000, "role": "worker", "capabilities": [{"name": "compute"}]})
        assert r.status_code == 201
        assert r.json()["host"] == "192.168.1.100"

    def test_node_list(self, client):
        client.post("/nodes", json={"host": "a", "port": 8000})
        client.post("/nodes", json={"host": "b", "port": 8001})
        r = client.get("/nodes")
        assert len(r.json()) == 2

    def test_submit_task(self, client):
        client.post("/agents", json={"name": "c", "capabilities": [{"name": "code"}]})
        r = client.post("/tasks", json={"name": "t1", "required_capabilities": ["code"]})
        assert r.status_code == 201
        assert r.json()["status"] == "dispatched"

    def test_submit_no_agent(self, client):
        r = client.post("/tasks", json={"name": "t1", "required_capabilities": ["code"]})
        assert r.status_code == 201
        assert r.json()["status"] == "pending"

    def test_sync_delta_merges_remote_agent(self, client):
        remote = AgentInfo(name="remote", node_id="node-b", capabilities=[Capability(name="code")])
        r = client.post(
            "/sync/delta",
            json={"source_node_id": "node-b", "vclock": 4, "agents": [remote.to_dict()]},
        )
        assert r.status_code == 200
        assert r.json()["merged"] == 1
        assert client.get("/agents/find", params={"node_id": "node-b"}).json()[0]["name"] == "remote"

    def test_sync_status_exposes_vclock(self, client):
        r = client.get("/sync/status")
        assert r.status_code == 200
        assert r.json()["local_node_id"] == "local"
        assert r.json()["vclock"] >= 0

    def test_failover_redispatches_inflight_task(self, client):
        failed = client.post(
            "/agents",
            json={"name": "failed", "node_id": "node-failed", "capabilities": [{"name": "code"}]},
        ).json()
        healthy = client.post(
            "/agents",
            json={"name": "healthy", "node_id": "node-good", "capabilities": [{"name": "code"}]},
        ).json()
        task = client.post("/tasks", json={"name": "t1", "required_capabilities": ["code"]}).json()
        assert task["agent_id"] == failed["agent_id"]

        r = client.post("/failover/node-failed")
        assert r.status_code == 200
        assert r.json()["redispatched"] == 1
        assert r.json()["assignments"][0]["agent_id"] == healthy["agent_id"]
        failed_state = client.get(f"/agents/{failed['agent_id']}").json()
        assert failed_state["status"] == "remote_offline"


class TestDispatcher:
    def test_dispatch_to_capable_agent(self):
        store = RegistryStore()
        store.register_agent(AgentInfo(name="coder", capabilities=[Capability(name="code")]))
        dispatcher = Dispatcher(store)
        assignment = dispatcher.submit(TaskRequest(name="t1", required_capabilities=["code"]))
        assert assignment is not None
        assert assignment.agent_name == "coder"

    def test_dispatch_no_capable_agent(self):
        store = RegistryStore()
        store.register_agent(AgentInfo(name="coder", capabilities=[Capability(name="code")]))
        dispatcher = Dispatcher(store)
        assignment = dispatcher.submit(TaskRequest(name="t1", required_capabilities=["deploy"]))
        assert assignment is None
        assert len(dispatcher.get_pending()) == 1

    def test_dispatch_respects_concurrency(self):
        store = RegistryStore()
        store.register_agent(AgentInfo(name="coder", capabilities=[Capability(name="code")], max_concurrency=1))
        dispatcher = Dispatcher(store)
        dispatcher.submit(TaskRequest(name="t1", required_capabilities=["code"]))
        assignment = dispatcher.submit(TaskRequest(name="t2", required_capabilities=["code"]))
        assert assignment is None

    def test_complete_frees_agent(self):
        store = RegistryStore()
        agent = AgentInfo(name="coder", capabilities=[Capability(name="code")], max_concurrency=1)
        store.register_agent(agent)
        dispatcher = Dispatcher(store)
        req = TaskRequest(name="t1", required_capabilities=["code"])
        dispatcher.submit(req)
        assert dispatcher.complete(req.task_id)
        a = store.get_agent(agent.agent_id)
        assert a.active_tasks == 0
        assert a.status == AgentStatus.IDLE

    def test_dispatch_pending(self):
        store = RegistryStore()
        dispatcher = Dispatcher(store)
        dispatcher.submit(TaskRequest(name="t1", required_capabilities=["code"]))
        assert len(dispatcher.get_pending()) == 1
        store.register_agent(AgentInfo(name="coder", capabilities=[Capability(name="code")]))
        assigned = dispatcher.dispatch_pending()
        assert len(assigned) == 1
        assert len(dispatcher.get_pending()) == 0

    def test_stats(self):
        store = RegistryStore()
        store.register_agent(AgentInfo(name="c", capabilities=[Capability(name="code")]))
        dispatcher = Dispatcher(store)
        dispatcher.submit(TaskRequest(name="t1", required_capabilities=["code"]))
        s = dispatcher.stats()
        assert s["dispatched"] == 1
        assert s["completed"] == 0

    def test_task_assignment_serialization(self):
        from runtime.registry.dispatch import TaskAssignment
        a = TaskAssignment(task_id="t1", agent_id="a1", agent_name="w1")
        assert a.task_id == "t1"
        assert a.status == TaskStatus.DISPATCHED

    def test_fail_decrements_tasks(self):
        store = RegistryStore()
        agent = AgentInfo(name="coder", capabilities=[Capability(name="code")])
        store.register_agent(agent)
        dispatcher = Dispatcher(store)
        req = TaskRequest(name="t1", required_capabilities=["code"])
        dispatcher.submit(req)
        assert dispatcher.fail(req.task_id)
        a = store.get_agent(agent.agent_id)
        assert a.active_tasks == 0
