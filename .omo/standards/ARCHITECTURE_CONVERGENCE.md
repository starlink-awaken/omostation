# Architecture Convergence Report

> 生成日期: 2026-05-28
> 任务: Batch 5 — agent-runtime 依赖分析 + SSOT 拆解执行总结

---

## Table of Contents

1. [Current Architecture State](#1-current-architecture-state)
2. [SSOT Decomposition Execution Summary](#2-ssot-decomposition-execution-summary)
3. [Project Boundary Redefinitions](#3-project-boundary-redefinitions)
4. [agent-runtime Deep Analysis](#4-agent-runtime-deep-analysis)
5. [agentmesh Gateway vs agent-runtime Comparison](#5-agentmesh-gateway-vs-agent-runtime-comparison)
6. [Convergence Proposal](#6-convergence-proposal)
7. [Next Steps](#7-next-steps)

---

## 1. Current Architecture State

### Before SSOT Decomposition (Pre-2026-05)

```
Hermes Cron Runner (run-agent-task.sh)
  │
  ├──► agent-runtime:9876 (Python FastAPI)
  │     ├── GET  /health
  │     ├── POST /run-task
  │     ├── POST /chat
  │     ├── GET  /logs
  │     └── GET  /task-history/{id}
  │
  └──► MCP Server (stdio, for Hermes MCP tools)
        ├── run_task
        └── chat
```

Relationship to agentmesh:

```
agentmesh Gateway:3000 (TypeScript Fastify)
  ├── /v1/health, /v1/tasks, /v1/scheduler
  ├── /v1/agents, /v1/pipeline, /v1/spaces
  ├── /v1/chat/completions (OpenAI compatible)
  ├── /v1/model-gateway, /v1/model-orchestrator
  ├── /v1/skills, /v1/hermes/*
  └── /v1/events (SSE)
        ▲
        │ No direct bridge
        │
agent-runtime:9876 (Python, independent)
```

**Problem:** `agent-runtime` exists as a Python silo — it duplicates API patterns (`/health`, `/run-task`) while agentmesh Gateway already provides a superset of HTTP API capabilities. The 12 cron jobs calling agent-runtime are locked to a legacy interface.

### After SSOT Decomposition (Current Topology)

```
Hermes (WeChat/CLI entry)
  │
  ├──► agent-runtime:9876 ────► 12 cron jobs (task_definitions/*.json)
  │     │                          │
  │     │                          ├── WF-001 KOS索引 (mcp_kos)
  │     │                          ├── WF-002 Minerva研究 (mcp_minerva)
  │     │                          ├── WF-003 系统健康检查
  │     │                          ├── WF-005 HANDOFF自动更新
  │     │                          ├── WF-006 感知管道
  │     │                          ├── WF-007 实时安全检查
  │     │                          ├── WF-008 Kanban-SSB桥接
  │     │                          ├── WF-009 委员会周检
  │     │                          ├── WF-010 宪法执行器
  │     │                          ├── WF-015 swarm-guardian
  │     │                          ├── codexbar-quota-refresh
  │     │                          └── daily-summary
  │     │
  │     └──► Agora:7430 ──► KOS:7420 / Minerva:8765 (MCP degrade)
  │
  ├──► agentmesh Gateway:3000 (TypeScript monorepo)
  │     ├── packages/gateway    — Fastify HTTP Gateway
  │     ├── packages/engine     — Honeycomb Orchestrator
  │     ├── packages/toolkit    — Capability SDK
  │     ├── packages/model-orchestrator — LLM Router
  │     ├── packages/core-types — Shared contracts
  │     ├── apps/server         — MCP Server
  │     └── apps/cli            — Unified CLI
  │
  ├──► Agora:7430 (Python MCP Hub)
  ├──► Minerva:8765 (Research Engine)
  ├──► KOS:7420 (Knowledge Store)
  └──► [Other MCP services]
```

---

## 2. SSOT Decomposition Execution Summary

| Batch | Task | Status | Key Outcome |
|-------|------|--------|-------------|
| Batch 1 | eCOS dependency audit + transfer plan | ✅ | eCOS dependencies mapped, transfer blueprint created |
| Batch 2 | Minerva → Sophia decoupling | ✅ | CLI-only communication, zero `import sophia` coupling |
| Batch 3 | Cross-project bridge + agentmesh integration | ✅ | Bridge contracts formalized in core-types |
| Batch 4 | Hermes agent configuration audit | ✅ | Hermes agents profiled, configs consolidated |
| **Batch 5** | **agent-runtime dependency analysis + convergence doc** | **✅ (this)** | Complete architecture convergence plan |

**SSOT Domain Entries (in `~/Workspace/SSOT/`):**

| Entity Type | Count | Domain File |
|-------------|-------|-------------|
| Organization entities | 6 | `domain/01-实体本体/01-组织实体.md` |
| Role entities | 5 | `domain/01-实体本体/02-角色实体.md` |
| Project entities | 8 | `domain/01-实体本体/03-项目实体.md` |
| Policy facts | 4 | `domain/02-事实基座/01-政策事实.md` |
| Data facts | 3 | `domain/02-事实基座/02-数据事实.md` |
| Inferences | 5 | `domain/03-推论体系/` |
| Relationship networks | 3 | `domain/04-关系网络/` |

---

## 3. Project Boundary Redefinitions

Updated based on SSOT insights from Batch 1–5.

### Core Runtime

| Project | Role | Boundary | Status |
|---------|------|----------|--------|
| **agentmesh** | TypeScript multi-agent orchestration monorepo | Gateway + Engine + Toolkit + Model-Orchestrator + MCP Server + CLI | 🔥 Active v2.x |
| **MetaOS** | Python system orchestration layer | Process-level cross-process orchestration, MCP bridge for Python ecosystem | ✅ Active |
| **agent-runtime** | **⏳ Legacy** Python task execution engine | Lightweight LLM task runner with file/tool access, **to be absorbed** | ⏳ Maintain (legacy) |

### MCP Bus

| Project | Role | Port | Status |
|---------|------|------|--------|
| **agentmesh Gateway** | TypeScript HTTP/SSE gateway | 3000 | 🔥 Active |
| **Agora** | Python MCP service hub | 7430 | ✅ Active v1.4→v2.0 |
| **Gateway (Python)** | Slimmed front-end for Agora | — | ⏳ Converging into Agora |
| **agent-runtime HTTP** | Legacy HTTP task API | 9876 | ⏳ Keep for cron compatibility |

### Knowledge Pipeline

| Project | Role | Status |
|---------|------|--------|
| **KOS** | Knowledge store + indexing | 7420 | ✅ Active |
| **Minerva** | Deep research engine | 8765 | ✅ Active |
| **Sophia** | Paradigm compiler | stdio | ✅ Active |
| **OntoDerive** | Fact derivation engine | CLI | ✅ Stable |
| **Pallas** | Knowledge engineering CLI | CLI | ✅ Active |

---

## 4. agent-runtime Deep Analysis

### 4.1 Code Structure

```
agent-runtime/
├── config.py          — Configuration module (model, port, paths, MCP endpoints)
├── tools.py           — Tool set: terminal_run, file_read/write, sqlite_query,
│                        mcp_call (with Agora degrade), http_get/post, send_message
├── engine.py          — AgentRuntime core engine (stateless task executor)
├── server.py          — FastAPI HTTP server (5 routes)
├── mcp_server.py      — MCP server (tools: run_task, chat)
├── cli.py             — CLI entry point (--server, --task, --prompt)
├── runtime.py         — Compatibility shim → cli_main()
├── run-agent-task.sh  — Shell wrapper for cron jobs
├── execution_log.jsonl— Execution history log
└── task_definitions/  — 12 JSON task definitions
    ├── WF-001.json   (KOS每日索引)
    ├── WF-002.json   (Minerva定期研究)
    ├── WF-003.json   (系统健康检查)
    ├── WF-005.json   (HANDOFF自动更新)
    ├── WF-006.json   (感知管道)
    ├── WF-007.json   (实时安全检查)
    ├── WF-008.json   (Kanban-SSB桥接)
    ├── WF-009.json   (委员会周检)
    ├── WF-010.json   (宪法执行器)
    └── WF-015.json   (swarm-guardian)
    ├── codexbar-quota.json
    └── daily-summary.json
```

### 4.2 HTTP API Surface

| Route | Method | Description |
|-------|--------|-------------|
| `/health` | GET | Returns `{status, model, auth}` |
| `/chat` | POST | General LLM chat with tool use (max 30 turns) |
| `/run-task` | POST | Execute a named task from `task_definitions/` or custom prompt |
| `/logs` | GET | Recent execution logs (from `execution_log.jsonl`) |
| `/task-history/{id}` | GET | Historical runs for a specific task |

### 4.3 Task Execution Flow

```
run-agent-task.sh
  │ curl -m 300 POST /run-task
  ▼
server.py:run_task()
  │ Load prompt from task_definitions/<task>.json
  │ Or use request.prompt directly
  ▼
engine.py:AgentRuntime.run_task(prompt)
  │ system_prompt → user_message → LLM call
  │ Loop (max 30 turns):
  │   └── _call_llm() → OpenAI compatible API
  │   └── _execute_tool() → tools.py
  ▼
Return {result, tool_calls, turns, usage}
  │
  ▼
server.py: _log_execution() → execution_log.jsonl
server.py: On error: _build_alert_message() → tools.send_message() → WeChat
```

### 4.4 Tool Inventory

| Tool | Target | Rate | Notes |
|------|--------|------|-------|
| `terminal_run` | Shell | Any | CWD = eCOS dir, timeout=120s |
| `file_read` | Workspace/* | Any | Sandboxed to ALLOWED_PATHS |
| `file_write` | Workspace/* | Any | Sandboxed to ALLOWED_PATHS |
| `sqlite_query` | Workspace/* DBs | Any | Sandboxed |
| `mcp_kos_run_indexer` | KOS MCP | Per-task | Via Agora or direct |
| `mcp_kos_get_system_status` | KOS MCP | Per-task | Via Agora or direct |
| `mcp_kos_research_now` | KOS→Minerva MCP | Per-task | Via Agora or direct |
| `http_get` | External | Any | timeout=30s |
| `http_post` | External | Any | timeout=30s |
| `send_message` | iLink→WeChat | Per-task | Receiver from env |

### 4.5 Notable Patterns

1. **[SILENT] Protocol**: Tasks that find nothing to report output `[SILENT]` to suppress notifications
2. **Agora Degrade**: 2 consecutive Agora failures → auto-switch to direct MCP for 5 minutes
3. **Path Sandbox**: All file operations checked against whitelist (Workspace, .hermes, .kos, .omo)
4. **Multi-source API Key Resolution**: Env → Hermes auth.json → .env file
5. **Fixed Model**: `deepseek-v4-flash` (not following default agentmesh config)
6. **No State Management**: Stateless per-call execution, no in-memory state beyond the task itself

---

## 5. agentmesh Gateway vs agent-runtime Comparison

### 5.1 Feature Matrix

| Feature | agent-runtime (9876) | agentmesh Gateway (3000) |
|---------|---------------------|--------------------------|
| **Health check** | `GET /health` (basic) | `GET /v1/health` + `GET /v1/health/detailed` ✅ |
| **Task execution** | `POST /run-task` (sync, blocking) | `POST /v1/tasks` (async, 202 accepted) ✅ |
| **Task status** | Embedded in response | `GET /v1/tasks/:taskId` ✅ |
| **Task cancellation** | ❌ Not supported | `POST /v1/tasks/:taskId/cancel` ✅ |
| **Task listing** | `GET /task-history/{id}` (from JSONL) | `GET /v1/tasks` (from in-memory TaskManager) ✅ |
| **Scheduler** | ❌ (handled by Hermes cron externally) | `POST /v1/scheduler` (built-in cron) ✅ |
| **Chat** | `POST /chat` (max 30 turns) | `POST /v1/model-orchestrator/chat` + SSE stream ✅ |
| **Agent registration** | ❌ | `POST /v1/agents` ✅ |
| **Tool/Skill system** | Tools in `tools.py` (hardcoded) | `GET /v1/skills` + `POST /v1/skills/:id/execute` ✅ |
| **Pipeline** | ❌ | `POST /v1/pipeline` ✅ |
| **Shared spaces** | ❌ | `POST /v1/spaces`, `GET /v1/spaces/:id` ✅ |
| **Events/SSE** | ❌ | `GET /v1/events` ✅ |
| **Model orchestration** | Single fixed model | Multi-provider + model routing ✅ |
| **OpenAI compatible** | ❌ (uses OpenAI API internally) | `POST /v1/chat/completions` ✅ |
| **MCP server** | FastMCP with `run_task`, `chat` | MCP in apps/server (separate process) ✅ |
| **Auth** | Bearer token | API key middleware ✅ |
| **File tools** | ✅ terminal_run, file_read/write, sqlite | ❌ (not built-in, but extensible via toolkit) |
| **Message push** | ✅ send_message → iLink → WeChat | ❌ (no built-in messaging agent) |
| **[SILENT] protocol** | ✅ Built into system prompt | ❌ (no equivalent) |
| **Task definitions** | ✅ `task_definitions/*.json` | ❌ (tasks defined in code) |
| **Agora degrade** | ✅ Auto fallback on 2 failures | ❌ (separate circuit breaker per provider) |
| **Path sandbox** | ✅ File access whitelist | ❌ (not applicable, no file tools) |

### 5.2 Gap Summary

**agent-runtime has 8 unique capabilities NOT in agentmesh Gateway**:
1. ✅ `task_definitions/*.json` — file-driven task definitions
2. ✅ `terminal_run` — shell access tool with sandbox
3. ✅ `file_read/write/sqlite_query` — file tools with path sandbox
4. ✅ `send_message` — WeChat/iLink push
5. ✅ `[SILENT]` protocol — suppress noise output
6. ✅ `execution_log.jsonl` — durable execution history
7. ✅ Agora degrade with auto-direct fallback
8. ✅ Self-start via `run-agent-task.sh` (if not running)

**agentmesh Gateway has 15+ capabilities agent-runtime lacks**:
1. Async task model (202 Accepted + status polling)
2. Built-in cron scheduler
3. Multi-agent orchestration pipeline
4. Shared workspaces for multi-agent collaboration
5. Model orchestration (multi-provider routing)
6. OpenAI-compatible `/v1/chat/completions`
7. SSE event stream
8. Skill system (plugin-based, extensible)
9. Circuit breaker per provider
10. Detailed health metrics
11. Rate limiting
12. Configuration hot-reload
13. API key auth (fail-closed)
14. Agent registration/discovery
15. TypeScript monorepo with core-types contracts

---

## 6. Convergence Proposal

### 6.1 Short-term (Immediate — Keep Both Running)

```
Hermes Cron ──► run-agent-task.sh ──► agent-runtime:9876
                                            │
                                     Keep as-is. No code changes.
                                     Only maintenance fixes.
```

**Rationale**: 12 active cron jobs depend on agent-runtime. It works stably. Don't change a working system under time pressure.

### 6.2 Medium-term (2-4 Weeks — Bridge Building)

```
                     ┌─────────────────────┐
                     │  agentmesh Gateway  │ :3000
                     │                     │
                     │  New route:         │
                     │  POST /v1/agent-    │
                     │   runtime/task      │
                     │                     │
                     │  New: toolkit-      │
                     │  integration for    │
                     │  terminal_run,      │
                     │  file_read/write    │
                     └─────────┬───────────┘
                               │ Bridge
                               ▼
                     ┌─────────────────────┐
                     │  agent-runtime      │ :9876
                     │  (lightweight)      │
                     │  No server.py       │
                     │  Just engine + tools│
                     └─────────────────────┘
```

**Actions:**
1. **Add `/v1/agent-runtime/task` route** in agentmesh Gateway that proxies to agent-runtime for backward compatibility
2. **Extend toolkit** with `TerminalTool`, `FileTool`, `MessageTool` (wrapping agent-runtime's tools.py patterns)
3. **Port `task_definitions/*.json`** → agentmesh scheduler tasks
4. **Port `[SILENT]` protocol** → agentmesh task system (add `suppress_on_silent` flag)

### 6.3 Long-term (4-8 Weeks — Full Absorption)

```
Hermes Cron ──► agentmesh Gateway:3000
                     │
                     ├── POST /v1/tasks (with task_definitions JSON support)
                     ├── Built-in cron scheduler replaces Hermes cron
                     ├── toolkit.terminal, toolkit.file, toolkit.message
                     ├── [SILENT] protocol support
                     └── execution_log → SQLite or event store

agent-runtime directory → ARCHIVED
  └── task_definitions/*.json → agentmesh config/tasks/
```

**Spec for `toolkit-terminal` package** (new module in `packages/toolkit/src/`):

```typescript
// packages/toolkit/src/tools/terminal.ts
interface TerminalToolConfig {
  allowedPaths: string[];        // Path sandbox
  defaultCwd: string;
  defaultTimeout: number;        // 120s
  maxOutputLength: number;       // 5000 chars stdout, 2000 stderr
}

// tools/file.ts — file_read, file_write, sqlite_query
// tools/message.ts — send_message via iLink
```

**Spec for task definitions format** (port to agentmesh):

The `task_definitions/*.json` format maps cleanly to agentmesh's existing task system:

```json
{
  "id": "WF-005",
  "name": "HANDOFF自动更新",
  "type": "agent-runtime-compat",
  "prompt": "...",
  "tools": ["file_read", "file_write", "terminal_run"],
  "schedule": "0 */2 * * *",
  "deliver": "origin",
  "suppress_on_silent": true,
  "runtime_options": {
    "max_turns": 30,
    "model": "deepseek-v4-flash",
    "temperature": 0.1
  }
}
```

---

## 7. Next Steps

### Priority 1: Documentation & Inventory (Immediate)
- [ ] Add `AGENTS.md` to `agent-runtime/` with current state and convergence notes
- [ ] Tag `agent-runtime` as `@legacy` in workspace AGENTS.md

### Priority 2: Bridge Construction (Week 1-2)
- [ ] Add `/v1/agent-runtime/health` and `/v1/agent-runtime/task` proxy routes in agentmesh Gateway
- [ ] Add `ToolRegistry.registerFromTaskDefinitions()` in toolkit for loading `.json` tasks
- [ ] Implement `TerminalTool` in toolkit with path sandbox

### Priority 3: Cron Migration (Week 2-4)
- [ ] Migrate 12 cron jobs from Hermes cron + `run-agent-task.sh` → agentmesh built-in scheduler
- [ ] Port `[SILENT]` protocol to agentmesh task result handling
- [ ] Port `execution_log.jsonl` to agentmesh event store

### Priority 4: Full Absorption (Week 4-8)
- [ ] Remove `server.py` from agent-runtime (only keep engine + tools as a library)
- [ ] Point `run-agent-task.sh` → agentmesh Gateway
- [ ] Archive agent-runtime directory
- [ ] Update AGENTS.md to remove agent-runtime from active projects

---

## Appendix A: Agent Runtime Dependency Graph

```
run-agent-task.sh (cron caller)
  │
  ├── source .zshrc
  ├── curl http://127.0.0.1:9876/health  ──┐
  │    └─ if fail: nohup python3 runtime.py ├── server.py
  │                           --server      │     │
  │                                         │     ├── config.py (port, model, paths, MCP endpoints)
  │    curl POST /run-task ─────────────────┘     ├── engine.py (AgentRuntime)
  │         {prompt, task}                        │     ├── _call_llm() → OpenAI API
  │                                               │     └── _execute_tool() → tools.py
  │                                               │           ├── terminal_run (subprocess)
  │                                               │           ├── file_read/write (sandbox)
  │                                               │           ├── sqlite_query (sandbox)
  │                                               │           ├── mcp_call (Agora→KOS/Minerva)
  │                                               │           │     └── degrade: _direct_mcp_call()
  │                                               │           ├── http_get/post
  │                                               │           └── send_message (iLink→WeChat)
  │                                               └── _log_execution() → execution_log.jsonl
  │
  └── echo result → stdout (→ Hermes cron pushes to WeChat)
```

## Appendix B: Task Classification by Delivery

| Delivery | Tasks | Count |
|----------|-------|-------|
| **local** (console output to cron) | WF-001, WF-002, WF-003, WF-006, WF-007, WF-008, WF-009, codexbar-quota, daily-summary | 9 |
| **origin** (WeChat push via cron) | WF-005, WF-010, WF-015 | 3 |

All 12 tasks produce text output. "origin" delivery means Hermes cron pushes the output to WeChat. "local" means it only writes to console/logs.

## Appendix C: Cron Schedule Summary

| Task | Frequency | Schedule | Expected Duration |
|------|-----------|----------|-------------------|
| WF-008 Kanban-SSB | Every 5 min | `*/5 * * * *` | ~10s |
| WF-006 感知管道 | Every hour | `0 * * * *` | ~30s |
| WF-005 HANDOFF | Every 2 hours | `12 */2 * * *` | ~15s |
| WF-007 安全检查 | Every 6 hours | `0 */6 * * *` | ~20s |
| codexbar-quota | Every hour | `5 * * * *` | ~10s |
| WF-001 KOS索引 | Daily 2am | `0 2 * * *` | ~60s |
| WF-003 健康检查 | Daily 10am | `0 10 * * *` | ~15s |
| WF-009 委员会周检 | Weekly Mon 9am | `0 9 * * 1` | ~30s |
| WF-002 Minerva研究 | Weekly Sun 3am | `3 3 * * 0` | ~120s |
| WF-010 宪法执行器 | Daily 4:22am | `22 4 * * *` | ~30s |
| WF-015 swarm-guardian | Mon/Wed/Fri 10am | `18 10 * * 1,3,5` | ~60s |
| daily-summary | Daily 8:37am | `37 8 * * *` | ~30s |

All durations are estimates. The total daily load on agent-runtime is approximately **5-8 minutes of LLM execution time** spread across the day.
