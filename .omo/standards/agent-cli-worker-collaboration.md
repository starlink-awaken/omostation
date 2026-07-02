---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-22
---

# Agent CLI Worker Collaboration Standard

> Status: active | Version: v1.0 | Scope: external agent CLI workers
> Related: `.omo/tasks/README.md`, `.omo/standards/operation-levels.md`,
> `.omo/standards/agent-registry-heartbeat.md`,
> `.omo/_knowledge/summaries/agent-task-contract.md`

---

## 1. Purpose

This standard defines how external agent CLIs join OMO collaboration as
**workers** without breaking task SSOT, operation-level gates, or review
discipline.

Current worker set:

- `codebuddy`
- `reasonix`

Future agent CLIs may be added through the same registry and handoff flow.

## 2. Core Rules

1. **Task YAML remains the only task SSOT.**
2. **Coordinator owns scheduling, review, requeue, and phase promotion.**
3. **Workers only act inside declared task scope and declared write paths.**
4. **External workers default to L1 max execution authority.**
5. **L2/L3 operations require explicit human approval and coordinator release.**
6. **Sensitive capabilities remain blocked by default.**
7. **Every worker run must leave reusable evidence and knowledge artifacts.**

## 3. Collaboration Topology

```text
Coordinator
  -> .omo/tasks/active/*.yaml               # task SSOT
  -> .omo/workers/registry.yaml             # worker capabilities + policy
  -> .omo/workers/templates/*               # handoff envelope + prompt contract
  -> external worker CLI                    # codebuddy / reasonix / future workers
  -> task evidence + review notes
  -> review / requeue / archive
```

## 4. Roles

### 4.1 Coordinator

Usually human or a governance/orchestrator agent.

Responsibilities:

- choose the worker
- prepare the handoff envelope
- enforce operation-level gates
- monitor heartbeat / progress lease
- review results
- move tasks to `done/` or `blocked/`
- synchronize `.omo/state/system.yaml`, `.omo/goals/current.yaml`, and `convergence.yaml`

### 4.2 Worker

Worker is an execution-only role.

Allowed:

- read task-specific context
- write only task-declared outputs
- update its assigned task to `in_progress` or `review`
- emit evidence, partial progress, and blocked reports

Not allowed:

- declare phase completion
- update global state files
- enable blocked capabilities
- execute undeclared L2/L3 operations
- silently expand scope

### 4.3 Reviewer

Reviewer may be the coordinator or a dedicated review agent.

Responsibilities:

- verify evidence
- check gate compliance
- confirm no cross-task contamination
- close out or requeue the task

## 5. Worker Lifecycle

```text
register -> assign -> acknowledge -> execute -> checkpoint -> review -> close/requeue
```

### 5.1 Register

Worker must exist in `.omo/workers/registry.yaml` with:

- worker ID
- transport modes
- allowed operation level
- allowed write scope
- heartbeat policy
- stall policy

### 5.2 Assign

Coordinator creates or updates:

- task YAML in `.omo/tasks/active/`
- worker task envelope
- worker prompt
- worker dispatch record under `.omo/workers/runs/`

### 5.3 Acknowledge

Coordinator preclaims the task lease before worker execution.

Coordinator sets:

- `status: in_progress`
- `assigned_to: <worker-id>`
- `started_at`
- `dispatch_id`
- `run_ref`

Worker then acknowledges against the dispatch record or live session, but does
not own the first task-state transition.

### 5.4 Execute

Worker runs within:

- declared read budget
- declared write scope
- declared operation level
- declared evidence requirements

### 5.5 Checkpoint

Worker must emit progress before lease expiry. A checkpoint may be:

- file write
- evidence note
- test result
- partial implementation
- blocked report

### 5.6 Review

Worker moves the task to `review` with evidence attached.

### 5.7 Close or Requeue

Only coordinator/reviewer may:

- move task to `done/`
- move task to `blocked/`
- reassign to another worker
- reopen for remediation

## 5.8 Operational Artifacts

Each worker run should have explicit artifacts:

- task envelope
- prompt contract
- dispatch record
- reclaim note, if the worker stalls

This keeps reassignment auditable and reduces knowledge loss during recovery.

## 6. Knowledge Sharing Contract

External workers do not keep private context as the only source of truth. Every
run must materialize a reusable handoff bundle.

### 6.1 Required Knowledge Inputs

Each worker assignment must include a knowledge pack with:

- task YAML path
- relevant source docs
- current `.omo/state/system.yaml`
- current `.omo/goals/current.yaml`
- relevant standards
- prior evidence or failure notes
- explicit non-goals and blocked domains

### 6.2 Required Knowledge Outputs

Each worker run must produce:

- result summary
- changed files list
- evidence list
- unresolved risks
- next handoff recommendation

### 6.3 Knowledge Persistence Rule

Reusable facts must land in one of:

- task YAML `evidence`
- review note
- summary/report under `.omo/`
- implementation artifact itself

No task may depend on hidden chat state alone.

## 7. Gate and Permission Model

### 7.1 Default Authority

External workers are **L1 by default**.

This means they may:

- read freely inside approved context
- perform low-risk writes inside declared output paths
- prepare L2/L3 plans, tests, and dry-run evidence

This means they may **not**:

- execute L2/L3 changes without explicit approval
- modify blocked connectors or sensitive domains
- change global governance state

### 7.2 L2/L3 Handling

For L2/L3 tasks, worker behavior is split:

1. prepare plan / patch / evidence
2. stop before the gated action
3. request release from coordinator
4. only proceed after approval is explicitly recorded

Approval record must include:

- task ID
- dispatch ID
- worker ID
- operation level
- exact action to release
- approval timestamp
- approver
- approval scope
- approval status
- expiry, if any

### 7.3 Sensitive Capability Policy

The following remain blocked unless separately released:

- Apple ecosystem connectors
- WeChat access
- SMB/NAS operations
- family profile / schedule / health domains
- media indexing
- high-autonomy triggers
- destructive backup/restore

Workers may design or document these, but may not activate or execute them.

## 8. Anti-Stall and Anti-Deadlock Rules

This framework extends the existing read-budget and heartbeat standards.

### 8.1 Read Budget

Every worker prompt must declare:

```text
READ_BUDGET: 5
```

After the budget is exhausted, the worker must produce one of:

- a write
- a partial result
- a blocked report
- a concrete replan

### 8.2 Progress Lease & Auto-Reap

Default execution lease enforced by MCP-Native Reaper:

- **heartbeat/checkpoint**: every 5 minutes (via `mcp.tool: heartbeat` or material write).
- **warning**: at 15 minutes.
- **stale**: at 20 minutes (`lease_expired`).
- **auto-reap**: at 30 minutes (`reclaim_due`), the `omo_worker.py` Auto-Reaper will forcibly terminate the lease and trigger `AUTO_RECLAIM_TIMEOUT`.

### 8.3 Stuck Worker Recovery

If a worker stalls:

1. capture current stdout/log/result
2. preserve partial output
3. mark task `review` or prepare a blocked note
4. release the worker lease
5. reassign with the last partial context included

### 8.4 Duplicate Claim Prevention

Only one active execution lease per task.

If two workers claim the same task:

- coordinator freezes both writes
- preserves both partial results
- selects a single continuation path

## 9. Write Scope Policy

Worker writes must be constrained by the task envelope.

Allowed write zones:

- task-declared implementation files
- task YAML owned by the assignment
- evidence and summary files explicitly declared by coordinator

Forbidden write zones for workers:

- `.omo/state/system.yaml`
- `.omo/goals/current.yaml`
- `convergence.yaml`
- unrelated task YAMLs
- blocked capability configs not in the approved task scope

## 10. Current Worker Profiles

### 10.1 codebuddy

- preferred role: implementation-heavy worker
- transport: CLI prompt, ACP stdio, ACP streamable-http
- strengths: multi-step execution, resumable sessions, swarm support
- default authority: L1

### 10.2 reasonix

- preferred role: focused execution / diagnosis worker
- transport: CLI prompt, ACP stdio
- strengths: task execution, code-mode workflows, ACP agent mode
- default authority: L1

## 11. Onboarding a New Worker

To add a new worker CLI:

1. add entry to `.omo/workers/registry.yaml`
2. define transport mode and launch command
3. declare capabilities and write scope
4. assign default max operation level
5. declare heartbeat + stall policy
6. run one low-risk pilot task
7. collect evidence before broad use

## 12. Minimal Success Criteria

This framework is working when:

- task SSOT stays in task YAML
- worker runs are reproducible from handoff artifacts
- stalled workers can be reclaimed without losing context
- L2/L3 actions cannot bypass approval
- knowledge survives worker replacement
- future worker CLIs can be added without redesigning the flow
