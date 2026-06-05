# TaskObject — eCOS L3 中立任务格式规范 v1.0

> Standard task format for cross-agent task passing through the L3 Entry Bridge.
> Status: design-locked for v1.0 minimal envelope; not a full workflow/DAG contract.

## Overview

TaskObject 是 eCOS L3 入口桥接矩阵层的**中立任务单元**，
用于在所有入口（Hermes / Claude Code / Codex / OpenCode）之间传递任务，
不依赖任何特定 Agent 的内部协议。

```
Agent A → TaskObject → L3 MCP Server → Agent B
```

## Current Scope

TaskObject v1.0 only solves one thing: a stable **single-request envelope** for
L3 entry bridging. It does **not** yet standardize:

- multi-step workflow orchestration
- DAG dependencies
- typed result contracts
- chain-of-custody audit payloads
- approval state transitions

## Schema

```yaml
task_object:
  version: string        # Required. Schema version (currently "1.0")
  id: string             # Required. UUID v4
  intent: string         # Required. One of: run | query | control | custom
  context:
    source: string       # Required. Originating agent: hermes | claude | codex | opencode
    session: string      # Optional. Source agent session ID for traceability
    description: string  # Optional. Human-readable task description
  target:
    service: string      # Required. Target MCP service name
    tool: string         # Required. Target tool name
    params: object       # Optional. Tool parameters
  callback:
    channel: string      # Optional. "stdout" | "weixin" | "file"
    format: string       # Optional. "text" | "json" | "markdown"
  ttl: integer           # Optional. Time-to-live in seconds (default: 300)
  priority: integer      # Optional. 0=critical, 1=high, 2=normal (default: 2)
```

## Implementation Status

### Implemented in v1.0

| Field | Status | Notes |
|------|--------|------|
| `version` | Implemented | Current value locked to `1.0` |
| `id` | Implemented | Used as JSON-RPC correlation ID |
| `intent` | Implemented | Used for routing semantics and walkthrough classification |
| `context.source` | Implemented | Source client identity |
| `context.session` | Partial | Trace-friendly, client dependent |
| `context.description` | Implemented | Human-readable task summary |
| `target.service` | Implemented | Logical target service, e.g. `runtime` |
| `target.tool` | Implemented | Maps to MCP `tools/call.name` |
| `target.params` | Implemented | Maps to MCP `tools/call.arguments` |
| `callback.channel` | Partial | Response channel intent only |
| `callback.format` | Partial | Output preference only |
| `ttl` | Partial | Envelope-level hint, not yet enforced end-to-end |
| `priority` | Partial | Envelope-level hint, not yet enforced by a scheduler |

### Reserved for future versions

| Field | Why deferred |
|------|--------------|
| `pipeline` | Not needed before tri-plane main path is stable |
| `dependencies` | DAG orchestration is out of v1 scope |
| `result_contract` | Result typing is not yet stabilized across clients |
| `audit` | Governance evidence is currently recorded outside the envelope |

## Intent Types

| Intent | Meaning | Example |
|--------|---------|---------|
| `run` | Execute an action | Start/stop service, run health scan |
| `query` | Retrieve information | List services, get protocol details |
| `control` | Manage lifecycle | Restart daemon, reload config |
| `custom` | Free-form task | Arbitrary agent-to-agent cooperation |

## Source Values

Recommended `context.source` values:

- `hermes`
- `claude-code`
- `codex`
- `opencode`
- `runtime-bridge`

## Examples

### Query runtime health

```yaml
task_object:
  version: "1.0"
  id: "550e8400-e29b-41d4-a716-446655440000"
  intent: query
  context:
    source: hermes
    session: "ses_abc123"
    description: "Check all service health"
  target:
    service: runtime
    tool: runtime_health
    params: {}
  callback:
    channel: stdout
    format: json
  ttl: 60
  priority: 2
```

### Control a service

```yaml
task_object:
  version: "1.0"
  id: "550e8400-e29b-41d4-a716-446655440001"
  intent: control
  context:
    source: claude-code
    session: "cls_xyz789"
    description: "Restart cron-service"
  target:
    service: runtime
    tool: runtime_service_ctl
    params:
      name: cron-service
      action: restart
  callback:
    channel: stdout
    format: text
  ttl: 120
  priority: 0
```

## Implementation

### JSON-RPC Mapping

TaskObject maps to MCP `tools/call` as follows:

```json
{
  "jsonrpc": "2.0",
  "id": "<task_object.id>",
  "method": "tools/call",
  "params": {
    "name": "<task_object.target.tool>",
    "arguments": <task_object.target.params>
  }
}
```

### Current Runtime MCP Tool Surface

Current `runtime` service tools exposed by Runtime MCP Server:

- `runtime_health`
- `runtime_matrix_list`
- `runtime_matrix_get`
- `runtime_service_ctl`
- `runtime_protocol_list`
- `runtime_protocol_get`
- `runtime_ontology_get`

### CLI Invocation

```bash
# Direct MCP invocation
echo '{"jsonrpc":"2.0","id":"<uuid>","method":"tools/call","params":{"name":"<tool>","arguments":{}}}' | \
  PYTHONPATH=src python3 src/runtime/mcp_server.py

# Using runtime CLI
python3 -m runtime health
python3 -m runtime matrix list
python3 -m runtime service <name> status
```

## Extensibility

TaskObject v1.0 intentionally minimal. Future versions may add:

- `pipeline` field for multi-step task chaining
- `dependencies` field for DAG-based task orchestration
- `result_contract` field for typed result expectations
- `audit` field for governance chain-of-custody

## Adoption Status

TaskObject v1.0 is the canonical L3 task envelope format. Current adoption:

| Component | Status | Evidence |
|-----------|--------|----------|
| Runtime MCP Server | **Native params** — tools accept individual params, not a full TaskObject envelope. A thin adapter could wrap/decorate incoming requests into TaskObject format. | `src/runtime/mcp_server.py` defines per-tool pydantic models, not a unified TaskObject dispatcher. |
| Hermes | MCP client — TaskObject fields map to JSON-RPC params, no envelope enforcement at client level. | Hermes calls MCP tools directly, not through TaskObject. |
| Claude Code | MCP client — same as Hermes. | No TaskObject awareness. |

**Adoption path:**
- ✅ P2 (DONE): TaskObject adapter at `src/runtime/taskobject_adapter.py` validates envelopes and dispatches to MCP tools
- P3: Make all L3 entry points (Hermes, Claude Code, Codex) emit TaskObject envelopes
- Current: TaskObject is implemented at the adapter layer; agents still call tools directly

## Compatibility

| Agent | MCP Client | TaskObject Support |
|-------|-----------|-------------------|
| Hermes | Native (config.yaml) | Full ✅ |
| Claude Code | Native (settings.json) | Full ✅ |
| Codex | Native (config.toml) | Full ✅ |
| OpenCode | Not MCP client | Via terminal wrapper |

### Current Implementation

The TaskObject adapter at `src/runtime/taskobject_adapter.py` implements the dispatch pipeline:

- `dispatch_taskobject()` — validates envelope → routes to MCP tool → returns standardized result
- `call_via_taskobject()` — wraps native calls in TaskObject format
- Status: [EXISTS] — first implementation, covers all 12 Runtime MCP tools
