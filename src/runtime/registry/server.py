"""Agent Registry — FastAPI HTTP API."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from .dispatch import Dispatcher, TaskRequest, TaskStatus
from .heartbeat import HeartbeatManager
from .models import AgentInfo, AgentStatus, Capability, NodeInfo, NodeRole
from .store import RegistryStore
from .sync import GossipSync

logger = logging.getLogger(__name__)


class CapabilitySchema(BaseModel):
    name: str
    tags: list[str] = []
    cost_eu: float = 0.0


class RegisterAgentRequest(BaseModel):
    name: str
    node_id: str = ""
    endpoint: str = ""
    capabilities: list[CapabilitySchema] = []
    max_concurrency: int = 1
    metadata: dict[str, Any] = {}


class RegisterNodeRequest(BaseModel):
    host: str
    port: int = 8000
    mcp_port: int = 0
    role: str = "worker"
    capabilities: list[CapabilitySchema] = []


class SubmitTaskRequest(BaseModel):
    name: str
    required_capabilities: list[str] = []
    priority: int = 0
    payload: dict[str, Any] = {}


class AgentResponse(BaseModel):
    agent_id: str
    name: str
    node_id: str
    endpoint: str
    capabilities: list[CapabilitySchema]
    status: str
    max_concurrency: int
    active_tasks: int
    load_ratio: float
    last_heartbeat: str


class NodeResponse(BaseModel):
    node_id: str
    host: str
    port: int
    role: str
    health: str
    load_score: float
    last_heartbeat: str


class HealthResponse(BaseModel):
    status: str
    agents: int
    nodes: int
    healthy_agents: int


_store: RegistryStore | None = None
_heartbeat: HeartbeatManager | None = None
_dispatcher: Dispatcher | None = None
_sync: GossipSync | None = None


class SyncDeltaRequest(BaseModel):
    source_node_id: str = ""
    vclock: int = 0
    agents: list[dict[str, Any]] = []


def create_app(persist_path: str | None = None, node_id: str = "local") -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        global _store, _heartbeat, _dispatcher, _sync
        _store = RegistryStore(persist_path)
        _heartbeat = HeartbeatManager(_store)
        _dispatcher = Dispatcher(_store)
        _sync = GossipSync(_store, local_node_id=node_id)
        _heartbeat.start()
        await _sync.start()
        yield
        await _sync.stop()
        _heartbeat.stop()

    app = FastAPI(title="Agent Registry", version="0.1.0", lifespan=lifespan)

    def _get_store() -> RegistryStore:
        assert _store is not None
        return _store

    def _get_sync() -> GossipSync:
        assert _sync is not None
        return _sync

    @app.post("/agents", response_model=AgentResponse, status_code=201)
    def register_agent(req: RegisterAgentRequest) -> AgentResponse:
        caps = [Capability(name=c.name, tags=c.tags, cost_eu=c.cost_eu) for c in req.capabilities]
        agent = AgentInfo(name=req.name, node_id=req.node_id, endpoint=req.endpoint, capabilities=caps, max_concurrency=req.max_concurrency, metadata=req.metadata)
        _get_store().register_agent(agent)
        _get_sync().notify_local_mutation()
        return _agent_to_response(agent)

    @app.get("/agents", response_model=list[AgentResponse])
    def list_agents() -> list[AgentResponse]:
        return [_agent_to_response(a) for a in _get_store().list_agents()]

    @app.get("/agents/find", response_model=list[AgentResponse])
    def find_agents(capability: str | None = Query(None), status: str | None = Query(None), node_id: str | None = Query(None)) -> list[AgentResponse]:
        caps = [capability] if capability else None
        st = AgentStatus(status) if status else None
        return [_agent_to_response(a) for a in _get_store().find_agents(caps, st, node_id)]

    @app.get("/agents/{agent_id}", response_model=AgentResponse)
    def get_agent(agent_id: str) -> AgentResponse:
        agent = _get_store().get_agent(agent_id)
        if agent is None:
            raise HTTPException(404, f"Agent {agent_id} not found")
        return _agent_to_response(agent)

    @app.post("/agents/{agent_id}/heartbeat")
    def agent_heartbeat(agent_id: str) -> dict:
        if not _get_store().heartbeat(agent_id):
            raise HTTPException(404, f"Agent {agent_id} not found")
        _get_sync().notify_local_mutation()
        return {"ok": True}

    @app.delete("/agents/{agent_id}")
    def deregister_agent(agent_id: str) -> dict:
        if not _get_store().remove_agent(agent_id):
            raise HTTPException(404, f"Agent {agent_id} not found")
        _get_sync().notify_local_mutation()
        return {"ok": True}

    @app.post("/nodes", response_model=NodeResponse, status_code=201)
    def register_node(req: RegisterNodeRequest) -> NodeResponse:
        caps = [Capability(name=c.name, tags=c.tags, cost_eu=c.cost_eu) for c in req.capabilities]
        node = NodeInfo(host=req.host, port=req.port, mcp_port=req.mcp_port, role=NodeRole(req.role), capabilities=caps)
        _get_store().register_node(node)
        return _node_to_response(node)

    @app.get("/nodes", response_model=list[NodeResponse])
    def list_nodes() -> list[NodeResponse]:
        return [_node_to_response(n) for n in _get_store().list_nodes()]

    @app.post("/nodes/{node_id}/heartbeat")
    def node_heartbeat(node_id: str) -> dict:
        if not _get_store().heartbeat_node(node_id):
            raise HTTPException(404, f"Node {node_id} not found")
        return {"ok": True}

    @app.delete("/nodes/{node_id}")
    def deregister_node(node_id: str) -> dict:
        if not _get_store().remove_node(node_id):
            raise HTTPException(404, f"Node {node_id} not found")
        return {"ok": True}

    @app.post("/tasks", status_code=201)
    def submit_task(req: SubmitTaskRequest) -> dict:
        request = TaskRequest(name=req.name, required_capabilities=req.required_capabilities, priority=req.priority, payload=req.payload)
        assignment = _dispatcher.submit(request)
        if assignment is None:
            return {"task_id": request.task_id, "status": "pending", "message": "No capable agent available, queued"}
        return {"task_id": assignment.task_id, "agent_id": assignment.agent_id, "agent_name": assignment.agent_name, "status": "dispatched"}

    @app.get("/tasks")
    def list_tasks(status: str | None = Query(None)) -> list[dict]:
        st = TaskStatus(status) if status else None
        assignments = _dispatcher.get_assignments(st)
        return [{"task_id": a.task_id, "agent_id": a.agent_id, "agent_name": a.agent_name, "status": a.status.value, "assigned_at": a.assigned_at.isoformat()} for a in assignments]

    @app.get("/tasks/pending")
    def list_pending_tasks() -> list[dict]:
        return [{"task_id": t.task_id, "name": t.name, "required_capabilities": t.required_capabilities} for t in _dispatcher.get_pending()]

    @app.post("/tasks/{task_id}/complete")
    def complete_task(task_id: str) -> dict:
        if not _dispatcher.complete(task_id):
            raise HTTPException(404, f"Task {task_id} not found")
        return {"ok": True, "task_id": task_id, "status": "completed"}

    @app.post("/tasks/{task_id}/fail")
    def fail_task(task_id: str) -> dict:
        if not _dispatcher.fail(task_id):
            raise HTTPException(404, f"Task {task_id} not found")
        return {"ok": True, "task_id": task_id, "status": "failed"}

    @app.get("/tasks/stats")
    def task_stats() -> dict:
        return _dispatcher.stats()

    @app.post("/tasks/dispatch-pending")
    def dispatch_pending() -> dict:
        assigned = _dispatcher.dispatch_pending()
        return {"dispatched": len(assigned), "assignments": [{"task_id": a.task_id, "agent_id": a.agent_id} for a in assigned]}

    @app.post("/sync/delta")
    def apply_sync_delta(req: SyncDeltaRequest) -> dict:
        merged = _get_sync().apply_delta(req.agents, req.source_node_id, req.vclock)
        return {"ok": True, "merged": merged, "vclock": _get_sync().get_status()["vclock"]}

    @app.post("/sync/force")
    async def force_sync() -> dict:
        return (await _get_sync().sync_once()).to_dict()

    @app.get("/sync/status")
    def sync_status() -> dict:
        return _get_sync().get_status()

    @app.post("/failover/{node_id}")
    def failover_node(node_id: str) -> dict:
        assignments = _dispatcher.failover_node(node_id)
        return {
            "ok": True,
            "node_id": node_id,
            "redispatched": len(assignments),
            "assignments": [{"task_id": a.task_id, "agent_id": a.agent_id} for a in assignments],
        }

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        store = _get_store()
        agents = store.list_agents()
        healthy = [a for a in agents if a.status != AgentStatus.OFFLINE]
        return HealthResponse(status="ok", agents=len(agents), nodes=len(store.list_nodes()), healthy_agents=len(healthy))

    return app


def _agent_to_response(a: AgentInfo) -> AgentResponse:
    return AgentResponse(
        agent_id=a.agent_id, name=a.name, node_id=a.node_id, endpoint=a.endpoint,
        capabilities=[CapabilitySchema(name=c.name, tags=c.tags, cost_eu=c.cost_eu) for c in a.capabilities],
        status=a.status.value, max_concurrency=a.max_concurrency, active_tasks=a.active_tasks,
        load_ratio=round(a.load_ratio, 3), last_heartbeat=a.last_heartbeat.isoformat(),
    )


def _node_to_response(n: NodeInfo) -> NodeResponse:
    return NodeResponse(
        node_id=n.node_id, host=n.host, port=n.port, role=n.role.value,
        health=n.health, load_score=n.load_score, last_heartbeat=n.last_heartbeat.isoformat(),
    )


__all__ = ["create_app"]

app = create_app()
