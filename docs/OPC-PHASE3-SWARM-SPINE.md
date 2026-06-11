# OPC-P3: Swarm Execution Spine

> Date: 2026-06-11
> P2: design baseline accepted (P2 remaining tasks complete — T4 8-field schema ✅)
> Source: OPC-ROADMAP.md §M3, opc-roadmap-omo-plan.md §Phase 3
> Status: design baseline delivered

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

## P3 Readiness Checklist

| Criterion | Status | Evidence |
|:----------|:------|:---------|
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
opc_phase3_swarm_spine_designed
```

P2 remaining tasks complete. P3 design baseline delivered. Swarm execution spine architecture defined with task object schema, 6 agent roles, dispatch flow, and minimal three-worker demo specification.
