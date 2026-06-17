---
plane: knowledge
type: design
status: active
freshness: 2026-05-31
maintainer: codebuddy
---

# Phase 5 Hermes Compatibility Contract

> **Status**: Frozen for Phase 5 execution.
>
> **Decision**: Direction A — Hermes downgrades from scheduler backbone to ingress + memory layer.
>
> **Rationale**: See `hermes-convergence-strategy.md` §4 and §6. Direction B (full absorption) is deferred to Phase 6+ evaluation.
>
> **Ownership**: This contract governs what Hermes may and may not do during Phase 5. Violations must be escalated to the Phase 5 coordinator.
> 本文档是历史阶段的兼容性契约记录，保留当时的 Hermes 收敛边界、迁移约束和保留项，不是当前调度 ownership、当前入口拓扑或当前执行许可 SSOT。
> 当前事实与执行请回到 `/.omo/goals/current.yaml`、`/.omo/state/system.yaml`、`/.omo/tasks/active/`、`/.omo/PROJECTS.yaml` 以及当前架构文档。

---

## 1. Scope Boundary

### 1.1 IN — Retained with full operational status

| # | Scope | Description | Criticality | Owner |
|---|-------|-------------|-------------|-------|
| 1 | **WeChat/IM ingress** | Hermes WeChat/IM → Gateway webhook (`POST /hermes/task`) continues as a supported OMO entry path | P0 | Gateway team |
| 2 | **Layered memory** | Hermes memory system (cross-session profile, environment facts, learned skills) continues to operate. Consumed via MCP by Task Center and Skill Federation in Wave 3+ | P1 | Hermes ops |
| 3 | **API key fallback** | `~/.hermes/auth.json` and `.env` continue as a fallback source for API keys, used when OMO native secret store is unavailable or undefined | P1 | Ops |

### 1.2 OUT — No new investment, no new dependencies

| # | Scope | Migration target | Deadline | Rationale |
|---|-------|-----------------|----------|-----------|
| 1 | **Scheduler backbone** | agentmesh built-in scheduler | Wave 1 exit | Hermes cron 已暴露 179 条断裂 symlink，与 agentmesh 调度器功能重叠 |
| 2 | **Cron job definition** | agentmesh scheduling definitions | Wave 1 exit | 12 个 cron jobs 不再定义在 Hermes 中 |
| 3 | **Task-definition ownership** | Task Center `task_definitions` | Wave 1 exit | symlink 不再新增，存量逐步迁移 |
| 4 | **MCP tool source** | kairon agent-runtime MCP | Wave 3 exit | Hermes MCP 工具与 agent-runtime 重叠，由 agent-runtime 统一管理 |
| 5 | **Kanban / scheduling visualization** | OMO event bus | Wave 2 exit | 调度可视化不依赖 `hermes kanban`，统一到 OMO 仪表板 |

### 1.3 MAINTENANCE ONLY — Keep running, do not extend

The following continue to run for backward compatibility, but must not receive new features or new bridge entries:

| # | Item | Keep condition | Removal trigger |
|---|------|---------------|-----------------|
| 1 | Existing `~/.hermes/scripts/` bridge symlinks for kairon / gbrain / SharedBrain | Active project needs | Task Center `task_definitions` covers the same capability |
| 2 | Existing Hermes cron definitions for the 12 known jobs | No functional alternative | agentmesh scheduler coverage verified for ≥ 7 days |
| 3 | Existing Hermes MCP tools exposed through Hermes memory | OMO native memory API unavailable | Wave 3 Skill Federation delivers consumption path |

---

## 2. Integration Contracts

### 2.1 Ingress Contract — WeChat/IM → Gateway

**Agent**: `agentmesh packages/gateway/src/hermes/routes.ts`

**Contract**:
- `POST /hermes/task` — WeChat/IM webhook endpoint, accepts `{ prompt, message, text }`, returns `{ task_id, status }`
- `GET /hermes/task/:id` — task status query
- `GET /hermes/tasks` — task listing (max 200 in-memory tasks)
- `GET /hermes/health` — health check

**Stability**: This contract is frozen for Phase 5. Backward-incompatible changes require Phase 5 coordinator approval.

**Monitoring**: Gateway logs (INFO level) record every Hermes task submission and completion/failure.

### 2.2 Memory Consumption Contract — MCP Interface

**Consumer**: Task Center (Wave 3), Skill Federation (Wave 3+)

**Contract terms**:
- Hermes layered memory is accessed via MCP tools, not direct filesystem reads
- Memory read operations are synchronous, best-effort, non-blocking
- Write operations to Hermes memory are PREFERRED through OMO native components; Hermes write is fallback only
- Memory schema and query semantics are defined by Hermes upstream; OMO consumes as-is

**Bounded commitment**: OMO allocates no development budget to extend or stabilize Hermes memory. If Hermes memory becomes unreliable, OMO falls back to a local SQLite cache (scope: Phase 6 evaluation).

### 2.3 Fallback Dependency Contract — API Key Resolution

**Chain**:
```
agentmesh secret_resolver → OMO native secret store → ~/.hermes/auth.json → .env
```

**Contract**:
1. All new code must attempt OMO native secret store first
2. `~/.hermes/auth.json` is fallback-only, not primary
3. `.env` is the last resort, not an installation requirement
4. No new code should hardcode fallback to Hermes secrets path; use `secret_ref` abstraction

---

## 3. Ownership Handoff Plan

### 3.1 Wave 1 — Scheduler Convergence

| What moves | From | To | Verification |
|-----------|------|----|-------------|
| 12 cron job definitions | Hermes cron | agentmesh scheduler definitions | agentmesh scheduler runs ≥ 7 days no Hermes cron gaps |
| Active project bridge symlinks | `~/.hermes/scripts/` | Task Center `task_definitions/` | `find ~/.hermes/scripts/ -xtype l` returns 0 |
| Task definition SSOT | Hermes kanban + symlinks | Task Center truth plane | No new symlink added to `~/.hermes/scripts/` since Phase 5 start |

### 3.2 Wave 3 — Tool Source Convergence

| What moves | From | To | Verification |
|-----------|------|----|-------------|
| MCP tool collection | Hermes MCP | kairon agent-runtime MCP | All agentmesh skills use agent-runtime MCP exclusively |
| Memory consumption | Direct Hermes calls | OMO native memory API (with Hermes MCP fallback) | Task Center reads Hermes memory through OMO layer |

### 3.3 Retention Continuity

| Path | Phase 5 status | Phase 6+ evaluation |
|------|---------------|---------------------|
| WeChat/IM → Gateway | Retained as-is | Evaluate Direction B (full absorption) |
| Hermes memory → MCP | Consumed as-is | Evaluate native OMO memory or full migration |
| API key fallback | Retained as-is | Evaluate removal after secret store hardening |

---

## 4. Non-Negotiables

1. **No new shadow SSOT** — All live facts about task definitions, scheduling, and tool sources must reside in OMO-native components. Hermes indexes reference, not own.
2. **No secret values in Hermes-mediated paths** — API keys transit via `secret_ref` through the OMO resolver chain. Hermes `auth.json` is a local fallback, not a distributed secret source.
3. **No Hermes as scheduler backbone for new work** — All new scheduling/task-definition/skill-declaration work must use OMO-native components (agentmesh scheduler, Task Center). Existing Hermes cron jobs are in maintenance-only mode.
4. **Trace continuity is mandatory** — Hermes-submitted tasks must carry `trace_id` through Gateway → Task Center → delivery, identical to CLI-submitted tasks.

---

## 5. Evidence Cross-Reference

### Evidence 1: Retained scope is limited to ingress + memory + bounded fallback

The IN scope (§1.1) defines exactly three retained items:
- WeChat/IM ingress (§2.1 — integration contract frozen)
- Layered memory consumed via MCP (§2.2 — best-effort consumption)
- API key fallback (§2.3 — chain with explicit priority)

All other Hermes capabilities are either OUT (§1.2 — with migration targets and deadlines) or MAINTENANCE ONLY (§1.3 — keep running, no new investment).

### Evidence 2: Hermes no longer described as scheduler backbone for new work

- §1.2 OUT item #1 explicitly removes scheduler backbone from Hermes scope
- §4 Non-negotiable #3 prohibits Hermes as scheduler backbone for new work
- All new scheduling work routes through agentmesh built-in scheduler (not Hermes cron)
- Wave 1 ownership handoff (§3.1) migrates all existing scheduler responsibilities away from Hermes

---

## 6. Verification

The following checks validate this contract:

```bash
# Evidence 1: No live docs imply Hermes as SSOT or scheduler backbone
grep -rn "hermes" .omo/plans/ --include="*.md" -l | while read f; do
  grep -qi "scheduler\|backbone\|ssot\|core SSOT" "$f" && echo "CHECK: $f"
done

# Evidence 2: No new hermes bridge symlinks since contract freeze
find ~/.hermes/scripts/ -xtype l | wc -l

# Evidence 3: Gateway Hermes routes unchanged
cd projects/agentmesh && git diff --name-only HEAD -- packages/gateway/src/hermes/routes.ts
```

---

## 7. References

| File | Relation |
|------|----------|
| `hermes-convergence-strategy.md` | Strategy input that produced Direction A |
| `hermes-research-notes.md` | Raw research notes from initial Hermes audit |
| `phase5-program-architecture.md` §3.3, §6.4 | Architecture contracts that Hermes must satisfy |
| `phase5-entry-gate-checklist.md` EG-3 | Entry gate items this contract satisfies |
| `projects/agentmesh/packages/gateway/src/hermes/routes.ts` | Ingress implementation |
| `projects/kairon/packages/agent-runtime/src/agent_runtime/engine.py` | MCP tool source (future owner) |

---

*Contract frozen: 2026-05-31 · Maintainer: codebuddy · Review cycle: Phase 5 Wave 0 exit*
