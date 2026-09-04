---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-14
---

# Agent CLI Worker Collaboration Standard

> Status: active | Version: v1.2 | Scope: external agent CLI workers
> Related: `.omo/tasks/README.md`, `.omo/standards/operation-levels.md`,
> `.omo/standards/agent-registry-heartbeat.md`,
> `.omo/_knowledge/summaries/agent-task-contract.md`

---

## 1. Purpose

This standard defines how external agent CLIs join OMO collaboration as
**workers** without breaking task SSOT, operation-level gates, or review
discipline.

Current worker set:

- admitted by the existing runtime contract: `codebuddy`, `reasonix`, `pi`,
  `oh-my-pi`, `codex`
- declared candidates: `opencode`, `claude-code`, `crush`,
  `grok`, `mimo`, `agy`, `kilo`

Future agent CLIs may be added through the same registry and handoff flow.

`declared` and `observed` do not mean `admitted`. A candidate remains disabled
until the coordinator supplies a complete transport contract, verifies the
worker, and explicitly promotes its policy record.

The historical `bin/_archive/capability-router.py` is not a consumer of the v2
registry. It remains archived and must not be revived as a fallback: it expects
the retired shell-string `launch` field and has no admission or observation
contract.

`bin/ssot/pi-adapter.py` is likewise not a Pool transport and must not be used
as a fallback. It is an uncontrolled historical entrypoint; its convergence is
tracked independently from the admitted Pi worker transport.

The admitted Codex production transport is the Orca-managed interactive Codex
TUI, observed through `bin/gac/orca-codex-supervisor.py`. Every provider approval
must remain visible for a human click in the retained terminal. An unresolved
approval is `awaiting_human_action`, not success and not a terminal failure.
`bin/gac/codex-worker-adapter.py` remains a bounded diagnostic adapter: its
`codex exec --approve-for-me --ephemeral --ignore-user-config --json` path cannot
carry a human approval response or resume the same ephemeral session, so it must
fail closed on an approval request and must not be used as the T1-18 production
execution path. Controller approval and provider approval are separate evidence
fields.
The flag is not permission to use `--dangerously-bypass-approvals-and-sandbox`,
change the sandbox, add arbitrary arguments, or run outside task-declared write
surfaces. The adapter must fail closed on timeout, malformed output,
process-group leaks, receipt failure, or workspace identity failure.

## 2. Core Rules

1. **Task YAML remains the only task SSOT.**
2. **Coordinator owns scheduling, review, requeue, and phase promotion.**
3. **Workers only act inside declared task scope and declared write paths.**
4. **External workers default to L1 max execution authority.**
5. **L2/L3 operations require explicit human approval and coordinator release.**
6. **Sensitive capabilities remain blocked by default.**
7. **Every worker run must leave reusable evidence and knowledge artifacts.**
8. **Provider/worker discovery is read-only and never dispatches a worker.**
9. **Unknown or stale quota remains unknown; proxy values are forbidden.**
10. **Capability requirements are explicit when worker policy requires them.**
    Any declared `capabilities` or `required_capabilities` field on a task,
    workflow packet, or admission grant must be a non-empty list of non-empty
    strings. Workers with `require_explicit_capabilities: true` reject dispatch
    when all three surfaces omit capability requirements.
11. **Transport acknowledgement is not readiness.** `ready`, `tui-idle`,
    `input_accepted`, process start, and exit 0 remain distinct from a valid
    final model output, candidate collection, and independent verification.
12. **Supervised providers may escalate.** A controller release authorizes the
    bounded attempt, not every provider-side tool request. Any later provider
    confirmation remains human-owned and must be observed or time out honestly.

### 2.1 Agent Pool Projection

The agent pool is a read-only union, not another scheduler or source of truth:

```text
CapabilityProvider M2 + capability-providers.yaml  # static CLI/provider facts
workers.yaml                                        # identity + authority policy
CodexBar                                            # sanitized quota observation
cc-switch                                           # catalog observation; no safe CLI in v1
AetherForge -> omlxc                                # governed local compute route + health
                         |
                         v
agent-pool-observe.py -> checksummed manifest       # observation, not admission
                         |
                         v
existing coordinator -> task/Mesh/lease/review      # only governed execution path
```

Cloud model inventory may be observed through cc-switch after a safe,
non-secret CLI contract exists. Until then it is explicitly unavailable to
automation. Local inference must route through
`bos://compute/aetherforge/infer`; direct OpenCode-to-local-port bindings are
not a governed compute path.

CodexBar is an observation adapter only. Its raw output, account identity,
email and credentials must never be persisted. `omlxc status` proves only
compute health; it proves neither provider quota nor a successful model call.
The embedded manifest digest detects accidental corruption. A verifier that
must detect replacement also needs the separately recorded expected digest;
the checksum is not a signature or proof of origin.

## 3. Collaboration Topology

```text
Coordinator
  -> .omo/tasks/active/*.yaml               # task SSOT
  -> .omo/_truth/registry/workers.yaml      # worker identity + authority policy
  -> .omo/workers/templates/*               # handoff envelope + prompt contract
  -> external worker CLI                    # admitted workers only
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

Worker must exist in `.omo/_truth/registry/workers.yaml` with:

- worker ID
- transport modes
- allowed operation level
- allowed write scope
- declared capabilities and whether explicit capability requirements are mandatory
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

For a Workflow Mesh admitted run, the acknowledgement must also be durable in
OMO. The worker or coordinator calls `omo worker mesh-ack` with the exact
`workflow_run_id`, `trace_id`, `dispatch_id`, `step_run_id`, `admission_id` and
worker ID. This appends `WorkerAcknowledged` and establishes the first lease;
updating the YAML dispatch record alone is insufficient evidence.

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

## 5.9 Workflow Mesh Event Contract

The durable worker control-plane sequence is:

```text
StepDispatched
  -> WorkerAcknowledged
  -> WorkerLeaseRenewed *
  -> WorkerLeaseExpired
  -> WorkerReclaimed (optional successor)
```

The lifecycle APIs are exposed as `omo worker mesh-ack`, `mesh-heartbeat`,
`mesh-expire`, and `mesh-reclaim`. `omo worker mesh-watchdog` scans the same
Workflow Mesh event log for expired live leases. It is read-only by default;
only `--apply` may append `WorkerLeaseExpired`, and it never chooses a
successor or appends `WorkerReclaimed`. The governed `omo worker
mesh-watchdog-run` adapter is the cadence-facing entry point: the existing
`omo daemon` invokes it once per tick, while cron/launchd may invoke it once
for an explicit run. A non-blocking process lock prevents overlap; every run
persists a privacy-safe summary to `.omo/_log/`, and ledger or scan failure is
reported as failed/degraded. All calls carry the same admission and StepRun
context. A repeated call with the same idempotency key is successful only when
its payload is identical; an owner mismatch, premature expiry, or reclaim
before expiry is rejected. The OMO event log and projection are the source of
truth; dispatch YAML remains the human-readable handoff artifact.

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

The durable lease contract is enforced by OMO Workflow Mesh. The existing OMO
daemon owns cadence and can run the default dry-run scan on every tick. A
scheduler or operator can run `omo worker mesh-watchdog-run --json` for a
durable preview and `omo worker mesh-watchdog-run --apply --json` for the
explicit expiry write:

- **heartbeat/checkpoint**: every 5 minutes (via `mcp.tool: heartbeat` or material write).
- **warning**: at 15 minutes.
- **stale**: at the dispatch lease deadline, `mesh-watchdog --apply` appends `WorkerLeaseExpired` with an explicit observation time.
- **reclaim**: after expiry, append `WorkerReclaimed` with a successor dispatch; no silent lease deletion is allowed.

The watchdog is intentionally not a scheduler implementation or a reclaim
policy. Existing cron/launchd/daemon infrastructure owns cadence; OMO owns
the state transition and its evidence. The runner does not execute workers,
choose successors, or create a second scheduler.

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

### 10.3 Pi

- preferred role: bounded local reasoning and verification worker
- transport: one CLI prompt argv through `bin/gac/pi-worker-adapter.py`; the
  adapter preserves its isolated AetherForge → omlxc coding route
- runtime: no tools and no session persistence
- default authority: L0; no file-write, code-change, or test-execution capability
- evidence: admission smoke retains its receipt; formal OMO dispatch retains
  the dispatch and stdout artifacts and does not pass an adapter receipt

### 10.4 Oh My Pi

- preferred role: bounded local reasoning and verification worker
- transport: one CLI prompt argv through `bin/gac/omp-worker-adapter.py`; the
  adapter pins OMP 16.1.16 and routes only through AetherForge → omlxc coding
- runtime: no tools, LSP, PTY, extensions, skills, rules, or persisted session
- default authority: L0; no file-write, code-change, or test-execution capability
- evidence: admission smoke retains a privacy-safe digest receipt; formal OMO
  dispatch retains the dispatch and stdout artifacts

## 11. Onboarding a New Worker

To add a new worker CLI:

1. add a disabled declaration to `.omo/_truth/registry/workers.yaml`
2. add the static provider/argv contract to
   `.omo/_truth/registry/capability-providers.yaml`
3. obtain a current observation receipt; do not copy runtime facts into either registry
4. add and verify the governed transport contract
5. coordinator/reviewer explicitly promotes the worker to `admitted` and enables it
6. declare capabilities, write scope, heartbeat and stall policy
7. run one low-risk pilot task and collect evidence before broad use

Observation or a smoke receipt is not admission: the coordinator/reviewer must
still make the explicit registry promotion in step 5.

## 12. Minimal Success Criteria

This framework is working when:

- task SSOT stays in task YAML
- worker runs are reproducible from handoff artifacts
- stalled workers can be reclaimed without losing context
- L2/L3 actions cannot bypass approval
- knowledge survives worker replacement
- future worker CLIs can be added without redesigning the flow
