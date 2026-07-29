# Agent Registry

Unified multi-machine agent coordination for eCOS. Merges patterns from Agora (Ed25519 identity, heartbeat), eCOS (AgentStatus enum, node_id), and Runtime (endpoint tracking).

## Quick Start

```bash
# Start the registry server
cd projects/runtime
uvicorn runtime.registry.server:app --host 0.0.0.0 --port 8100

# Register an agent
curl -X POST http://localhost:8100/agents \
  -H "Content-Type: application/json" \
  -d '{"name": "coder", "capabilities": [{"name": "code-generation", "tags": ["python"]}]}'

# Submit a task
curl -X POST http://localhost:8100/tasks \
  -H "Content-Type: application/json" \
  -d '{"name": "task-1", "required_capabilities": ["code-generation"]}'
```

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  Agent Registry + Dispatcher                         │
│                                                      │
│  POST /agents ──→ register ──→ RegistryStore         │
│  POST /tasks ──→ Dispatcher.submit()                 │
│                     │                                │
│                     ├─ find_agents(capabilities)     │
│                     ├─ select_best(least_load)       │
│                     └─ assign ──→ TaskAssignment     │
│                                                      │
│  HeartbeatManager (background sweep)                 │
│    ├─ TTL 60s → mark OFFLINE                         │
│    └─ Zombie 3600s → remove                          │
└──────────────────────────────────────────────────────┘
```

## Modules

| Module | Purpose |
|--------|---------|
| `models.py` | Data models: AgentInfo, NodeInfo, Capability, AgentStatus, NodeRole |
| `store.py` | Thread-safe in-memory cache + JSON file persistence |
| `heartbeat.py` | Background daemon: TTL-based liveness sweep + zombie removal |
| `dispatch.py` | Task dispatcher: capability matching, least-load selection, concurrency-aware routing |
| `server.py` | FastAPI HTTP API (17 endpoints) |

## API Reference

### Agents

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/agents` | Register agent |
| GET | `/agents` | List all agents |
| GET | `/agents/find?capability=X&status=Y` | Find agents by capability/status |
| GET | `/agents/{id}` | Get agent details |
| POST | `/agents/{id}/heartbeat` | Agent heartbeat |
| DELETE | `/agents/{id}` | Deregister agent |

### Nodes

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/nodes` | Register node |
| GET | `/nodes` | List all nodes |
| POST | `/nodes/{id}/heartbeat` | Node heartbeat |
| DELETE | `/nodes/{id}` | Deregister node |

### Tasks

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/tasks` | Submit task (dispatched or queued) |
| GET | `/tasks` | List dispatched tasks |
| GET | `/tasks/pending` | List queued tasks |
| GET | `/tasks/stats` | Task statistics |
| POST | `/tasks/{id}/complete` | Mark task completed |
| POST | `/tasks/{id}/fail` | Mark task failed |
| POST | `/tasks/dispatch-pending` | Retry queued tasks |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Registry health check |

## Data Model

```python
AgentInfo:
  agent_id: str        # auto-generated 12-char hex
  name: str
  node_id: str         # which node this agent lives on
  endpoint: str        # network address
  capabilities: list[Capability]
  status: AgentStatus  # idle/busy/offline/error/draining
  max_concurrency: int
  active_tasks: int
  load_ratio: float    # active_tasks / max_concurrency

Capability:
  name: str
  tags: list[str]
  cost_eu: float       # execution units (for future auction dispatch)
```

## Dispatch Logic

1. `submit(task)` finds agents with matching capabilities
2. Filters out saturated agents (`active_tasks >= max_concurrency`)
3. Selects agent with lowest `load_ratio` (least load)
4. If no capable agent, queues task to pending
5. `dispatch_pending()` retries all queued tasks

## Heartbeat

- Agents must heartbeat within 60s (configurable)
- After 60s without heartbeat → marked OFFLINE
- After 3600s offline → removed as zombie
- Background sweep runs every 10s

## Tests

```bash
cd projects/runtime
pytest tests/test_registry.py -v
# 31 tests: models(6) + store(7) + heartbeat(2) + server(8) + dispatch(8)
```
