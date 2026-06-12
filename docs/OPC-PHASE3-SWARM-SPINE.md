# OPC-P3: Swarm Execution Spine

> Date: 2026-06-11
> P2: Gate C passed (C1+C2+C3+C4 closed, 21/21 tests pass)
> Source: OPC-ROADMAP.md §M3, opc-roadmap-omo-plan.md §Phase 3
> Status: implementation entry; Gate D opened (D1+D2 passed, D3-D5 not started)
> Tracking: `.omo/tasks/registry/done/OPC-P3-GATE-D-OPENING.yaml` (single source of truth)

---

## Current Implementation State (as of 2026-06-11)

| Sub-gate | Status | Evidence |
|:---------|:-------|:---------|
| **D1** Task Object Runtime Binding | ✅ **passed** | `.omo/tasks/registry/done/OPC-P3-D1/` |
| **D2** Dispatch and Heartbeat | ✅ **passed** | `.omo/tasks/registry/done/OPC-P3-D2/` (SUCCESS/RETRY/FAILURE 三路 runtime 实证) |
| **D3** Role Realization | 📋 not_started | — |
| **D4** Result Writeback and Audit | 📋 not_started | — |
| **D5** Minimal Demo | 📋 not_started | — |
| **Gate D** | ⏳ not_yet_passed | D1+D2 passed; D3-D5 未启动, 无 runtime 实证 |

**Strategic decision (D1+D2, 2026-06-11)**: Option B — thin P3 binding using omo + cockpit, skip swarm-engine
- Dispatch + retry 路径: `omo_worker_dispatch.dispatch_task` + `reclaim_task` (omo 本地)
- Workers registry: `.omo/_truth/registry/workers.yaml` (coder-001, coder-002 transports=cli_prompt)
- Swarm-engine organs.* imports 12 个 stub 缺口保留, 不修 (refactor regression 风险)
- aetherforge / runtime 不参与当前 P3 实施 (留 R57+ 切换)

> **之前的"Strategic options (deferred)" + "D1 Blockers" 已 obsolete**。GATE-D-OPENING.yaml 是当前唯一事实依据。

---

## Architecture: Target vs Current

### Target architecture (OPC-PHASE3 design baseline, §T2)

```
User Goal → OMO Task → swarm DAG → swarm-engine → runtime → gbrain → omo
```

### Current implementation path (D1+D2 thin binding, 2026-06-11)

```
User Goal → OMO Task → omo_worker_dispatch → workers.yaml → coder-001/002 (cli_prompt) → omo audit
```

**差异**: 当前路径不经过 swarm-engine / runtime / aetherforge。swarm-engine 12 个 stub 缺口 + KEI sandbox + aetherforge 集成 均未做。

### When to revisit architecture split (D3 entry decision)

D3 (Role Realization) 实施时, **必须显式选择**:

| Option | Approach | Risk | When to choose |
|:-------|:---------|:-----|:---------------|
| A. 继续 thin binding | 用 omo + cockpit 实施 6 角色 | Low — D1+D2 实证能跑 | **默认推荐** (保持当前路径, 避免回退) |
| B. 回到 target architecture | 修 swarm-engine organs.* imports 12 缺口 | High — refactor regression | swarm-engine 上游修复完成时 |
| C. 双轨并行 | thin binding 主线 + swarm-engine 备线, 失败回退 | Medium — 双维护成本 | D5 需 swarm-engine 核心能力时 |

**D3 entry 时 (本 session 后续)** 必须显式选定 Option A/B/C 并写入 GATE-D-OPENING.yaml 子任务。

---

## P3 红线 (from MASTER-PLAYBOOK §6.2 + OPC-ROADMAP §6)

- ❌ "do not write passed before runtime evidence exists"
- ❌ "no agent may apply for a later sub-gate while an earlier one is still open"
- ❌ "swarm-engine D1 修复不在 P3 范围, 避免 refactor regression"
- ❌ "禁止同时声明 D1 blocked 和 D1 passed" (本文档之前冲突, 已收口)
- ❌ "禁止重提 strategic options as open question" (D1+D2 已选定 Option B)

---

## T0 — P2 Remaining Tasks (Verified)

| Task | Status | Evidence |
|:----|:------|:---------|
| P2-T4: source metadata 8-field schema | ✅ completed | `storage.py` — local search now returns all 8 fields: `_source`, `_source_path`, `_zone`, `_type`, `_freshness`, `_owner`, `_reuse_policy`, `_retrieved_at` |
| P2-T3: multi-zone all-search route | 📝 planned | `bos://memory/local/all-search` route design exists, implementation deferred |

---

## T1 — Swarm Task Object

### Task Lifecycle

```
planned → assigned → running → completed
                          │
                          └→ failed → retry (max 3x) → dead → debt
```

### Task Object Schema

```yaml
id: "TASK-xxx"
title: "task description"
status: planned|assigned|running|completed|failed|dead
priority: P0|P1|P2|P3
owner: agent-role
phase: P2|P3|P4|...
created: ISO8601
assigned: ISO8601|null
completed: ISO8601|null
retries: 0..3
parent: null | Decomposition parent task ID
children: [] | Decomposed child task IDs
input: {uri: ..., args: {...}} | Task input contract
output: {result: ..., artifacts: [...]} | Task output contract
audit:
  started: ISO8601
  heartbeat_last: ISO8601
  heartbeat_count: N
  failures: [{timestamp, error, retry}]
debt:
  trigger_count: N
  max_failures: 3
  on_exhaust: "register_debt"
```

---

## T2 — Swarm Boundary

### Architecture ownership

| Component | Owner | Role |
|:----------|:------|:-----|
| Task creation and decomposition | **OMO** | User goal → OMO task → swarm DAG |
| Task market and DAG semantics | **swarm-engine** | Dispatch, routing, conflict detection |
| Product aggregation API | **aetherforge** | Cockpit/swarm integration surface |
| Execution isolation and sandboxing | **runtime** | Worker process, KEI, matrix scheduling |
| High-risk execution gates | **OMO + metaos** | Gate checks, immune response, debt registration |
| Agent capability discovery | **agora** | BOS URI registry, tool discovery |
| Result writeback and audit | **OMO** | Audit log, debt register, phase state |

### Cross-boundary protocols

```
OMO Task →(decompose)→ swarm DAG
  │
swarm DAG →(dispatch)→ runtime worker
  │
runtime worker →(execute)→ result
  │
result →(writeback)→ OMO audit + task status update
  │
failure →(debt)→ OMO debt register
```

---

## T3 — Agent Role Set

| Role | Responsibility | System | Model Budget |
|:-----|:--------------|:-------|:-----------|
| **Researcher** | Collect information, search memory zones, synthesize findings | kairon KOS, gbrain, cockpit local | Low — search-only |
| **Planner** | Decompose goals into tasks, estimate effort, assign agents | swarm-engine, OMO | Medium |
| **Coder** | Write, review, and modify code | runtime sandbox, git | High |
| **Reviewer** | Review code, verify correctness, enforce standards | cockpit code analyze, lint | Medium |
| **Operator** | Execute deployment, infrastructure, and data operations | runtime KEI, cron-service | Medium |
| **Critic** | Analyze retrospective, identify improvement opportunities | metaos, model-driven | Low |

### Role Assignment Rules

1. Every task has exactly one assigned role at creation
2. Roles are capability-based — a single agent instance may fill multiple roles
3. Role assignment is recorded in task audit trail
4. High-risk tasks require OMO gate approval before execution

---

## T4 — Worker Dispatch

### Dispatch Flow

```
OMO Task: "Decompose P2 design into implementation tasks"
  │ planner role
  ▼
swarm-engine: create DAG with 3 worker nodes
  │
  ├── T1: "Implement source_path metadata" → researcher role
  ├── T2: "Code review the metadata changes" → reviewer role
  └── T3: "Verify all tests pass" → reviewer role
  │
  ▼
dispatch: T1 assigned → runtime worker
  │ heartbeat: every 30s
  ▼
execute: worker code changes → write to git
  │ result: {commit: "abc123", changed_files: [...]}
  ▼
writeback: result → OMO audit
  │ task status: completed
  ▼
T2 assigned: reviewer reviews code
  │ result: {approved: true, comments: [...]}
  ▼
T3 assigned: verify tests pass
  │ result: {passed: true, coverage: 85%}
  ▼
DAG complete: OMO task → completed
```

### Heartbeat and Failure Protocol

- Heartbeat: every 30s, worker signals alive
- Missed 2 heartbeats → worker marked as failed
- Failure: immediate retry (max 3x)
- Exhausted retries: task → dead, OMO debt registered
- Dead task: human review required before retry

---

## T5 — Minimal Demo Specification

### Demo: "What OPC phases are currently active?"

```
Goal: Answer user query, decompose into 3 worker tasks

Worker 1 (researcher):
  input:  {query: "OPC phase status"}
  action: search cockpit local + POC_SERVICES + AGENTS.md
  output: {phases: [{P0: done}, {P1: conditional}, {P1.5: baseline}, {P2: design}]}

Worker 2 (reviewer):
  input:  {claim: Worker 1 output}
  action: verify against docs/OPC-*-*.md and .omo/state/system.yaml
  output: {verified: true, corrections: []}

Worker 3 (researcher → summary):
  input:  {verified_phases: Worker 2 corrected output}
  action: format human-readable summary
  output: {summary: "P0-P2 are active. P3 is next. kairon/gbrain debts are registered."}

Result → writeback to OMO audit
```

### Acceptance Criteria

- A goal decomposes into at least 3 worker tasks ✅
- Worker tasks have owner/status/input/output/audit ✅
- Failure creates retry or debt ✅

---

## P3 Readiness Checklist (实际状态, 2026-06-11)

| Criterion | Status | Evidence |
|:----------|:------|:---------|
| P2 Gate C passed | ✅ | `OPC-P2-GATE-C.yaml` (C1+C2+C3+C4 closed, 21/21 tests) |
| P2-T4 8-field metadata schema | ✅ | `storage.py` — all 8 fields in local search output |
| D1 Task Object Runtime Binding | ✅ **passed** | `OPC-P3-D1/` (runtime evidence) |
| D2 Dispatch and Heartbeat | ✅ **passed** | `OPC-P3-D2/` (SUCCESS/RETRY/FAILURE 三路) |
| D3 Role Realization | 📋 not_started | — |
| D4 Result Writeback and Audit | 📋 not_started | — |
| D5 Minimal Demo | 📋 not_started | — |

----------|:------|:---------|
| P2 design baseline accepted | ✅ | Gate C doc revision accepted |
| P2-T4 8-field schema complete | ✅ | `storage.py` — all 8 P2 metadata fields in local search output |
| Swarm task object defined | ✅ | §T1 |
| Swarm boundary defined | ✅ | §T2 |
| Agent role set defined | ✅ | §T3 (6 roles) |
| Worker dispatch designed | ✅ | §T4 |
| Minimal demo specified | ✅ | §T5 |

---

## Signal

```
opc_phase3_gate_d_opened
opc_phase3_subgate_d1_passed
opc_phase3_subgate_d2_passed
opc_phase3_subgate_d3_not_started
opc_phase3_subgate_d4_not_started
opc_phase3_subgate_d5_not_started
opc_phase3_gate_d_not_yet_passed
```

Signal 命名规范: `opc_phaseN_gate_XN_subgate_YN_<status>`
- `_passed` / `_not_started` / `_not_yet_passed` (only these 3)
- 禁止模糊 signal (e.g. "design ready", "implementation entry", "baseline delivered" 不带 gate)

**Gate D 收口 signal** (待 D3+D4+D5 全部 passed): `opc_phase3_gate_d_passed`

**当前已发出 signal (2026-06-11)**: `opc_phase3_subgate_d1_passed`, `opc_phase3_subgate_d2_passed`, `opc_phase3_gate_d_opened`
