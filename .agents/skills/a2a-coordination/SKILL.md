---
name: a2a-coordination
description: "Coordinate tasks between multiple AI agents using the A2A (Agent-to-Agent) protocol via Agora MCP. Covers Agent Card registration, task delegation, status tracking, and swarm node discovery. Use when multiple agents need to collaborate, delegate work, or discover each other's capabilities."

last-reviewed: 2026-08-26
type: ssot
owner: governance-team
---

# A2A Coordination - Agent-to-Agent Task Delegation

Guide for multi-agent collaboration through the A2A protocol. Agora MCP provides `a2a_send_task`, `a2a_get_task`, `a2a_cancel_task`, `a2a_list_tasks`, `list_agent_cards`, and `get_agent_card` tools for inter-agent communication.

## When To Use

- Multiple agents need to collaborate on a task
- One agent wants to delegate work to another agent
- Agent needs to discover what other agents are available
- User says "delegate to another agent" / "多 agent 协作" / "a2a"
- Swarm coordination: find which node can handle a BOS URI

## A2A Protocol Overview

```
Agent A                    Agora MCP                   Agent B
  |                            |                          |
  |--- list_agent_cards ----->|                          |
  |<-- [card1, card2, ...] ---|                          |
  |                            |                          |
  |--- a2a_send_task --------->|                          |
  |    (tool_name, args)       |--- invoke tool --------->|
  |                            |<-- result ---------------|
  |<-- {task_id, status} ------|                          |
  |                            |                          |
  |--- a2a_get_task ---------->|                          |
  |    (task_id)               |                          |
  |<-- {status, result} -------|                          |
```

## Phase 1: Agent Discovery

### 1.1 List Registered Agent Cards

```python
# Via MCP
result = await list_agent_cards()
# Returns: {"agents": [{"name": "...", "description": "...", "capabilities": [...]}]}
```

### 1.2 Get a Specific Agent Card

```python
# Via MCP
result = await get_agent_card(name="omo-agent")
# Returns: {"name": "...", "description": "...", "capabilities": [...], "endpoints": [...]}
```

### 1.3 Discover Swarm Nodes

```python
# Via MCP - find which node can handle a BOS URI
result = await swarm_resolve(uri="bos://memory/kos/search")
# Returns: {"found": true, "node": {...}} or {"found": false, "hint": "..."}

# List all online swarm nodes
result = await swarm_nodes(role="")  # role: master/worker/function
# Returns: {"total": N, "nodes": [...]}

# Check overall swarm status
result = await swarm_status()
```

## Phase 2: Task Delegation

### 2.1 Send a Task to Another Agent

```python
# Via MCP
result = await a2a_send_task(
    tool_name="search_knowledge",  # The tool to call on the target agent
    arguments={"query": "ADR-0203 requirement iteration"},  # Tool arguments
    service=""  # Optional: target specific service/agent
)
# Returns: {"task_id": "abc123", "status": "submitted"}
```

### 2.2 Track Task Status

```python
# Via MCP
result = await a2a_get_task(task_id="abc123")
# Returns: {"task_id": "...", "status": "completed|running|failed", "result": {...}}
```

### 2.3 List All Tasks

```python
# Via MCP - filter by status, service, or time
result = await a2a_list_tasks(
    service="",      # Filter by service name
    status="",       # Filter by status (submitted, running, completed, failed)
    since="",        # ISO timestamp filter
    limit=50         # Max results
)
```

### 2.4 Cancel a Task

```python
# Via MCP
result = await a2a_cancel_task(task_id="abc123")
# Returns: {"task_id": "...", "status": "cancelled"}
```

## Phase 3: Register as an A2A Service

For an agent to receive A2A tasks, it must register as a service in Agora.

### 3.1 Register Service

```python
# Via MCP
result = await register_service(
    name="my-agent",
    description="Custom agent for X",
    capabilities=["search", "analyze", "summarize"],
    transport="stdio",  # or "http", "mcp_proxy"
    command=["uv", "run", "--project", "projects/my-agent", "python", "-m", "my_agent"],
    bos_uri="bos://custom/my-agent/invoke"  # Optional BOS URI
)
```

### 3.2 Verify Registration

```python
# List services to confirm
result = await list_services()
# Or check via swarm
result = await swarm_nodes()
```

## Phase 4: Multi-Agent Workflow Patterns

### Pattern 1: Sequential Delegation

Agent A -> delegate to Agent B -> B delegates to Agent C -> results bubble back up.

```python
# Agent A
task = await a2a_send_task(tool_name="analyze_code", arguments={"path": "src/"})
result = await a2a_get_task(task_id=task["task_id"])
# Agent B (receives via its own MCP loop)
subtask = await a2a_send_task(tool_name="search_knowledge", arguments={"query": result["analysis"]})
```

### Pattern 2: Parallel Fan-Out

Agent A delegates to B, C, D simultaneously and aggregates results.

```python
# Fan out
tasks = []
for agent_tool in ["agent_b_search", "agent_c_analyze", "agent_d_summarize"]:
    t = await a2a_send_task(tool_name=agent_tool, arguments={"data": payload})
    tasks.append(t["task_id"])

# Collect
results = []
for tid in tasks:
    while True:
        r = await a2a_get_task(task_id=tid)
        if r["status"] in ("completed", "failed"):
            results.append(r)
            break
        await asyncio.sleep(2)
```

### Pattern 3: BOS URI-Mediated Collaboration

Agents collaborate through BOS event bus instead of direct A2A calls.

```python
# Agent A publishes event
await publish_event(
    event_type="bos://brain/events/task_created",
    payload={"task": "review PR", "assigned_to": "agent-b"}
)

# Agent B subscribes
await subscribe_event(
    event_type="bos://brain/events/task_created",
    callback_url="http://agent-b:9000/handle"
)
```

## Phase 5: Governance Considerations

### 5.1 Audit Trail

All A2A interactions are logged in the audit system.

```python
# Query audit log for A2A events
result = await audit_query(actor="agent-a", event_type="a2a_send_task", limit=50)
```

### 5.2 Swarm Coordination (G-CONV.7 / ADR-0220)

Multi-agent work on the same workspace must follow swarm discipline:

| Gate | Command |
|------|---------|
| ADR claim | `python3 bin/adr/next-adr-id.py --session <s> --claim` |
| Branch lock | `bash bin/gac/gac-worktree.sh claim <s>` |
| Shared claim | `make install-hooks` -> pre-commit `claim-check` |
| Escape valve | `SWARM_ESCAPE_ID=...` for `CI_LOCAL_SKIP` |

```bash
# Check swarm coordination window
python3 bin/gac/swarm-discipline-cli.py window-status

# Use swarm-safe git
bash bin/gac/swarm-git <git-command>
```

### 5.3 Agent Workflow Compliance

Each agent's work must still go through the agent-workflow lifecycle (ADR-0203). A2A task delegation does NOT exempt the receiving agent from running its own workflow.

## Related

- Skills: `agent-onboarding`, `bos-service-discovery`, `project-governance`
- A2A tools: `projects/agora/src/agora/server/tools_governance.py`
- Swarm tools: `projects/agora/src/agora/server/tools_swarm.py`
- Swarm coordination: `.omo/_truth/registry/swarm-coordination.yaml`
- ADR-0220: Swarm coordination
- Cockpit: `uv run --project projects/cockpit cockpit agent-workflow --help`
