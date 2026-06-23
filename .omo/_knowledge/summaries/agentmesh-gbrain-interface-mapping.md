---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R2: summaries/ 根目录历史快照批量归档, 当前状态以 .omo/state/system.yaml + .omo/tasks/active/ 为准"
---
# Phase 11 Wave 1 — agentmesh ↔ gbrain interface mapping (T1.7–T1.8)

> Scope: `projects/agentmesh/` and `projects/gbrain/`
> Goal: identify the **real integration seam** between the agent execution mesh and the knowledge brain

## Executive summary

The current coupling between **agentmesh** and **gbrain** is primarily **protocol-level**, not package-level:

- **gbrain** exposes a large operations surface through **MCP stdio / MCP HTTP** plus CLI commands
- **agentmesh** provides the gateway/router/scheduler/model-orchestrator side of agent execution
- both sides depend on **`@modelcontextprotocol/sdk`**
- no direct in-repo TypeScript package dependency from `gbrain` to an `agentmesh` package was surfaced in the quick scan; the relationship is described as **“gbrain MCP server for integration with Agora / agentmesh WorkspaceMCPClient”**

That means the safest Wave 1 contract boundary is:

1. **tool registry / operation schema**
2. **transport mode** (stdio vs HTTP MCP)
3. **identity / auth / remote-vs-local trust semantics**
4. **routing expectations** (who decides source/brain/model/provider)

## Surface map

| Area | gbrain evidence | agentmesh evidence | Mapping |
|---|---|---|---|
| MCP entrypoint | `src/mcp-entry.ts` (“MCP stdio server entry point”) | package root script `"mcp": "bun run apps/server/src/mcp/index.ts"` | Shared MCP transport seam |
| Tool registry | `src/core/operations.ts` (3,841 lines; large op registry) + `src/mcp/server.ts` builds tool defs from `operations` | gateway/toolkit/model-orchestrator packages in monorepo | gbrain is the tool/brain provider; agentmesh is a likely consumer/router |
| Shared dispatch semantics | `src/mcp/dispatch.ts` | `packages/gateway`, `packages/model-orchestrator`, `packages/toolkit`, `apps/server` | contract-level integration, not shared source |
| HTTP/stdio serving | `src/commands/serve.ts`, `src/mcp/http-transport.ts`, `src/mcp/server.ts` | monorepo scripts: `start`, `gateway`, `mcp`, `cli` | transport ownership exists on both sides |
| Search / doctor / operations | many CLI commands (`doctor`, `search`, `tools-json`, `serve`) | gateway/router/scheduler/task-manager/event-bus surfaces under `src/core/*` | gbrain = knowledge/tool backend, agentmesh = execution/runtime routing |

## gbrain interface facts

| File | Lines | Why it matters |
|---|---:|---|
| `src/core/operations.ts` | 3,841 | canonical operation registry exposed to CLI + MCP |
| `src/mcp/dispatch.ts` | 283 | single dispatch seam for stdio + HTTP MCP |
| `src/mcp/server.ts` | 104 | stdio MCP server that exports tool defs from `operations` |
| `src/mcp-entry.ts` | 24 | explicit entrypoint; comment references integration with Agora / agentmesh WorkspaceMCPClient |

## Concrete coupling points (evidence)

- **agentmesh → Agora fallback discovery**: `WorkspaceMCPClient` shells out to Agora when no explicit service list is available:
  - `projects/agentmesh/packages/toolkit/src/integrations/WorkspaceMCPClient.ts:226-248` spawns `agora list --json` and maps services into `WorkspaceMCPService` entries.
- **gbrain MCP tool surface is generated from operations**:
  - `projects/gbrain/src/mcp/server.ts:20-22` returns `tools: buildToolDefs(operations)` for `tools/list`.
  - `projects/gbrain/src/core/operations.ts` exports `operations: Operation[] = [...]` with **75 operations** in the registry.
- **gbrain storage backend supports Postgres + PGLite (custom engine, not TypeORM)**:
  - `projects/gbrain/src/core/postgres-engine.ts` imports `postgres` (postgres.js) and implements `PostgresEngine`.
  - `projects/gbrain/src/core/pglite-engine.ts` implements the `pglite` engine using `@electric-sql/pglite`.

Top-level source areas observed in `gbrain/src/`: `commands`, `core`, `mcp`, `types`, `eval`, `assets`.

## agentmesh interface facts

| Area | TS files | Why it matters |
|---|---:|---|
| `packages/toolkit` | 356 | largest shared utility/tool surface |
| `packages/gateway` | 91 | execution gateway / transport edge |
| `packages/model-orchestrator` | 41 | provider/model orchestration surface |
| `packages/core-types` | 18 | contract/types layer |
| `apps/server` | 6 | server runtime entry |
| `apps/cli` | 1 | CLI entry |

The monorepo root also exposes scripts for `build`, `gateway`, `mcp`, `cli`, and `start`, reinforcing that **agentmesh owns runtime orchestration surfaces**, not the knowledge operations themselves.

## Integration observations

1. **Protocol beats package dependency**: the evidence points to MCP as the dominant seam. That is good for decoupling, but it means compatibility must be enforced via **tool schemas + dispatch behavior**, not import-time type safety.
2. **gbrain is richer on operation semantics**: `operations.ts` is already large and central; downstream runtimes should avoid re-encoding gbrain semantics elsewhere.
3. **agentmesh owns routing/runtime composition**: gateway/router/scheduler/task-manager/event-bus files are concentrated on its side.
4. **Trust boundary matters**: `projects/gbrain/AGENTS.md` explicitly distinguishes trusted local CLI callers from remote/untrusted MCP callers. Any agentmesh ↔ gbrain contract needs to preserve that boundary instead of flattening it.

## Wave 1 recommendation

For Phase 11 baseline purposes, treat the interface contract as:

- **Transport**: MCP stdio + MCP HTTP
- **Schema authority**: gbrain `operations`
- **Runtime authority**: agentmesh gateway/router/model-orchestrator
- **Auth / trust**: gbrain remote/local `OperationContext` boundary remains authoritative

This is the minimum stable seam to carry into deeper Wave 2/3 integration work.
