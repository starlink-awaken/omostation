# TaskObject — eCOS L3 中立任务格式规范 v1.0

> Standard task format for cross-agent task passing through the L3 Entry Bridge.

## Overview

TaskObject 是 eCOS L3 入口桥接矩阵层的**中立任务单元**，
用于在所有入口（Hermes / Claude Code / Codex / OpenCode）之间传递任务，
不依赖任何特定 Agent 的内部协议。

```
Agent A → TaskObject → L3 MCP Server → Agent B
```

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

## Intent Types

| Intent | Meaning | Example |
|--------|---------|---------|
| `run` | Execute an action | Start/stop service, run health scan |
| `query` | Retrieve information | List services, get protocol details |
| `control` | Manage lifecycle | Restart daemon, reload config |
| `custom` | Free-form task | Arbitrary agent-to-agent cooperation |

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
    source: claude
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

## Compatibility

| Agent | MCP Client | TaskObject Support |
|-------|-----------|-------------------|
| Hermes | Native (config.yaml) | Full ✅ |
| Claude Code | Native (settings.json) | Full ✅ |
| Codex | Native (config.toml) | Full ✅ |
| OpenCode | Not MCP client | Via terminal wrapper |
