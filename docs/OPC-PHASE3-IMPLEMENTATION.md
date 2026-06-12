# OPC-P3: Swarm Execution Spine — Implementation Baseline

> Date: 2026-06-11
> P2: T4 completed, implementation in progress
> Source: OPC-ROADMAP.md §M3, opc-roadmap-omo-plan.md §Phase 3
> Status: implementation entry; Gate D opened (D1+D2 passed, D3-D5 not started)
> Source-of-truth: `.omo/tasks/registry/done/OPC-P3-GATE-D-OPENING.yaml`

---

## Current P2 State (carried in, ACTUAL)

| Task | Status | Note |
|:----|:------|:-----|
| T4 8-field metadata | ✅ completed | All searches tagged with full schema |
| T3 all-search route | ✅ implemented | `bos://memory/local/all-search` in POC_SERVICES |
| T3 multi-zone (KOS/vault) | 📝 deferred | Requires running kairon subprocess |
| Gate C | ✅ **passed** | C1+C2+C3+C4 closed, 21/21 tests (DO NOT mark as pending) |

---

## P3: Swarm Execution Spine — Architecture

### Architecture

```
User Goal
  │
  ▼
OMO Task ("decompose P2 into implementation tasks")
  │  decompose (planner)
  ▼
Swarm DAG (3 worker nodes)
  │
  ├── Worker 1: researcher  —  search cockpit + BOS
  ├── Worker 2: reviewer    —  code review + lint check
  └── Worker 3: verifier    —  test suite run
  │
  ▼
Dispatch → runtime worker → execute → result
  │                                  │
  ┌──────────────────────────────────┘
  │ result → OMO audit → task status update
  │ failure → retry (max 3x) → dead → OMO debt
  ▼
```

### Task Object

```yaml
id: TASK-xxx
status: planned | assigned | running | completed | failed | dead
priority: P0-P3
owner: researcher | planner | coder | reviewer | operator | critic
retries: 0-3
input: {uri, args}
output: {result, artifacts}
audit: {started, heartbeat_last, heartbeat_count, failures}
debt: {trigger_count, max_failures: 3}
```

### Component Boundaries

| Component | Role | Implementation |
|:----------|:-----|:---------------|
| OMO | Task creation, goal decomposition | `.omo/tasks/`, `system.yaml` |
| swarm-engine | Task market, DAG, dispatch | `projects/swarm-engine/` |
| aetherforge | Product aggregation API | `projects/aetherforge/` |
| runtime | Execution isolation, KEI | `projects/runtime/` |
| agora | Agent capability discovery | `project/agora/` (BOS registry) |
| metaos | High-risk execution gates | `projects/metaos/` |

### Six Agent Roles

| Role | System | Budget | Slot |
|:-----|:-------|:------|:----:|
| researcher | kairon KOS, cockpit local | Low | 2 |
| planner | swarm-engine, OMO | Medium | 1 |
| coder | runtime sandbox | High | 2 |
| reviewer | cockpit code analyze | Medium | 1 |
| operator | runtime KEI, cron-service | Medium | 1 |
| critic | metaos, model-driven | Low | 1 |

### Failure Protocol

1. Heartbeat: 30s intervals
2. 2 missed heartbeats → worker marked failed
3. Immediate retry (max 3 attempts)
4. Exhausted → task dead, OMO debt registered
5. Peer review: planer → coder → reviewer → verifier (independent)

---

## P3 Task Registry

| Task ID | Title | Status |
|:--------|:------|:------|
| OPC-P3-01 | Swarm task object schema | ✅ design complete |
| OPC-P3-02 | Component boundary map (6 owners) | ✅ design complete |
| OPC-P3-03 | 6 agent role definitions | ✅ design complete |
| OPC-P3-04 | Worker dispatch + heartbeat + retry | ✅ design complete |
| OPC-P3-05 | Three-worker demo specification | ✅ design complete |

---

## Signal

```
opc_phase3_implementation_entry
```

P3 design baseline complete. Implementation requires swarm-engine/runtime/aetherforge activation.

### Current Panorama

```
OPC-P0  ✅ passed          Gate A: passed
OPC-P1  ✅ conditional     Gate B: accepted
OPC-P1.5 ✅ baseline       Gate B2: accepted
OPC-P2  ⏳ in progress     Gate C: evidence submitted
OPC-P3  ⏳ design ready    Gate D: awaiting
OPC-P4  ⬜                 model gateway + compute
```
