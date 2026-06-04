# OMO planned-to-active promotion workflow design

Date: 2026-06-03
Status: approved-by-user-default execution mode (user explicitly waived intermediate review gates and requested direct spec/plan/execution)
Scope: add a coordinator-owned, fail-closed promotion workflow for moving one planned packet at a time from `.omo/tasks/planned/` into `.omo/tasks/active/`, plus one controlled low-risk rehearsal on the new queue model

## 1. Context

The strict-active-only migration is now complete:

1. `.omo/tasks/active/` is the current executable queue.
2. `.omo/tasks/planned/` holds future backlog and not-yet-promoted packets.
3. `state/system.yaml` now derives separate `active_tasks` and `planned_tasks` counts and queue previews.

That resolved the queue-placement problem, but it intentionally left one follow-on gap:

> how does a packet move from `planned/` to `active/` without falling back to ad-hoc coordinator file moves?

Two existing standards already constrain the answer:

1. `.omo/standards/agent-cli-worker-collaboration.md` states that the coordinator owns scheduling, review, requeue, and phase promotion.
2. `.omo/standards/capability-metamodel.md` states that live SSOT promotion requires human approval and a promotion envelope.

So the next slice is not "invent a new task model". It is:

1. define the narrowest legitimate promotion path
2. record promotion as a governed artifact
3. prove the path with one low-risk rehearsal

## 2. Goals

This design should:

1. make `planned -> active` promotion explicit and reproducible
2. keep promotion coordinator-owned
3. fail closed when a packet is not eligible for promotion
4. preserve the existing task schema and status enum
5. support one real rehearsal without reopening `active/` as a backlog pool

## 3. Non-goals

This design does not:

1. build a broad promotion product surface for every future lifecycle action
2. add worker self-promotion
3. add bulk promotion of multiple packets at once
4. infer promotion from free-text plans or indexes
5. auto-dispatch a packet immediately after promotion
6. redesign approval routing for all L2/L3 systems

## 4. Approaches considered

### A. Full CLI-first promotion surface

Behavior:

1. add a substantial new `task promote` command family
2. support eval, apply, rollback, listing, and history immediately

Pros:

- more complete command surface from day one
- easier to extend later if adopted broadly

Cons:

- too much scope for the next slice
- risks turning a governance workflow into a prematurely productized CLI
- higher chance of coupling unrelated lifecycle concerns together

This approach is deferred.

### B. Recommended: governed workflow plus one controlled rehearsal

Behavior:

1. add the smallest promotion helpers needed for coordinator-owned execution
2. require a promotion envelope artifact before the queue move
3. promote one packet at a time
4. prove the path with a low-risk rehearsal

Pros:

- matches the current governance standards
- keeps scope narrow and testable
- creates reusable artifacts without requiring a large new surface

Cons:

- not a complete lifecycle framework yet
- future expansions may still want a richer command surface later

### C. One-off rehearsal only

Behavior:

1. do a manual packet move once
2. record evidence afterward

Pros:

- fastest path to a demo

Cons:

- leaves no formal promotion workflow behind
- risks turning a one-off workaround into the new implicit process

This approach is rejected.

## 5. Recommended design

Use **Approach B**.

The core decision is:

> add a coordinator-owned, CLI-light promotion workflow that evaluates one planned packet, emits a promotion envelope artifact, applies the queue move only if all gates pass, refreshes derived state, and records one rehearsal against a low-risk Phase 17 packet.

This is the smallest correct next step because:

1. it honors the existing coordinator-owned promotion rule
2. it records promotion as first-class governance evidence
3. it proves the new queue contract can be advanced safely without reopening backlog drift

## 6. Architecture

### 6.1 Promotion stays inside the existing `scripts/omo_worker.py task` surface

Do not introduce a brand-new top-level CLI.

Add two narrow task subcommands under the existing worker CLI:

1. `python3 scripts/omo_worker.py task promote-eval <TASK_ID> --omo-dir .omo`
2. `python3 scripts/omo_worker.py task promote-apply <TASK_ID> --promoted-by <ACTOR> --now <ISO8601> --omo-dir .omo`

Why this boundary:

1. it keeps promotion inside the same coordinator task-management surface as validation
2. it avoids inventing a separate domain just for one governance transition
3. it keeps the workflow narrow enough for one implementation plan

### 6.2 Promotion is a queue move, not a status rewrite

Promotion does **not** invent a new status.

Instead:

1. the packet must already be `candidate` or `pending` in `planned/`
2. successful promotion moves the file into `active/`
3. its status remains `pending` after promotion
4. the promotion envelope ref is appended to `handoff_refs`
5. dispatch fields remain unset until the normal execution claim happens later

This keeps the canonical status model intact and makes queue placement carry the execution-eligibility meaning.

### 6.3 Promotion requires a promotion envelope artifact

Before a queue move is applied, create one YAML artifact under `.omo/workers/runs/`:

```yaml
version: 1
promotion_id: "<TASK_ID>-promotion-<TIMESTAMP>"
task_id: "<TASK_ID>"
task_ref_before: ".omo/tasks/planned/<TASK_ID>.yaml"
task_ref_after: ".omo/tasks/active/<TASK_ID>.yaml"
promotion_status: "approved"
promoted_by: "<coordinator-id>"
promoted_at: "<ISO8601>"
phase_gate:
  current_phase: 16
  target_phase: 17
  allowed_by_rule: true
approval:
  required: false
  approval_ref: null
checks:
  queue_membership_ok: true
  status_ok: true
  active_schema_ready: true
  approval_ready: true
  target_path_clear: true
rollback:
  supported: true
  rollback_action: "move task back to .omo/tasks/planned/ and rerun sync"
refs:
  state_ref: ".omo/state/system.yaml"
  goals_ref: ".omo/goals/current.yaml"
```

This envelope is the durable proof that the coordinator evaluated promotion rather than silently moving a file.

### 6.4 Eligibility is explicit and fail-closed

`promote-eval` must reject promotion unless all checks pass.

Required checks:

1. the task exists under `.omo/tasks/planned/`
2. the task status is `candidate` or `pending`
3. the task phase is exactly `state.current_phase + 1`
4. the task has the fields required for active execution packets (`source_docs`, `entry_gate`, `evidence_required`, `test_plan`, and any active-schema requirements already enforced by the validator)
5. if the packet requires approval, `approval_ref` already exists
6. the destination file path under `.omo/tasks/active/` does not already exist

The explicit `target_phase == current_phase + 1` rule is intentionally narrow for Version 1. It prevents accidental promotion of deeper future backlog such as Phase 18+ packets while the current system is still at Phase 16 closeout / Phase 17 entry.

### 6.5 `promote-apply` owns the reversible queue move

`promote-apply` should:

1. run the same eligibility checks as `promote-eval`
2. write the promotion envelope artifact
3. append the envelope ref to the task's `handoff_refs`
4. move the task file from `planned/` to `active/`
5. run `sync_omo_state.py --omo-dir .omo`
6. print the envelope ref and the new task ref

If any step fails:

1. the command exits non-zero
2. no half-written queue state is left behind
3. if the move already occurred but sync fails, the command must move the task back to `planned/` before exiting

### 6.6 Rehearsal is part of the slice, not separate future work

The implementation must end with one controlled rehearsal.

Rehearsal candidate:

1. `ORPHANED-TASKS-STRUCTURED-REGISTRY`

Why this packet:

1. it is Phase 17
2. it is `L1`
3. it is governance-local rather than cross-runtime infrastructure
4. it exercises the new promotion path on a real packet without forcing a high-risk rollout

Expected rehearsal result:

1. the packet moves from `planned/` to `active/`
2. a promotion envelope artifact exists under `.omo/workers/runs/`
3. the active task now points back to that envelope through `handoff_refs`
4. `state/system.yaml` reflects the changed counts and previews

## 7. Data flow

The intended Version 1 flow is:

1. coordinator selects one planned packet
2. `promote-eval` checks queue membership, phase horizon, approval, and active-schema readiness
3. `promote-apply` writes the promotion envelope, records its ref on the task, and performs the queue move
4. state sync refreshes `active_tasks`, `planned_tasks`, `next_active_tasks`, and `next_planned_tasks`
5. queue-hygiene tests treat future-phase pending packets in `active/` as valid only when a promotion envelope ref is present in `handoff_refs`
6. rehearsal evidence points to the envelope and the refreshed live state

This keeps promotion visible at both the truth layer (task file location) and the delivery layer (run artifact).

## 8. Error handling

Promotion must fail closed on all ambiguity.

Examples:

1. task missing from `planned/` -> reject
2. task already present in `active/` -> reject
3. phase mismatch (`task.phase != current_phase + 1`) -> reject
4. missing approval for an approval-required packet -> reject
5. validator says the packet is not active-ready -> reject
6. sync failure after move -> rollback the move and exit non-zero

The system should never leave a packet in an uncertain "maybe promoted" state.

## 9. Testing

The implementation plan should include tests for:

1. `promote-eval` rejects a Phase 18+ packet while current phase is 16
2. `promote-eval` rejects an approval-required packet without `approval_ref`
3. `promote-apply` creates the promotion envelope, records it in `handoff_refs`, and moves a valid Phase 17 packet from `planned/` to `active/`
4. failed promotion rolls back any partial move
5. queue-hygiene tests allow promoted future-phase pending packets only when the envelope ref is present
6. rehearsal updates `state/system.yaml` counts and previews correctly
7. docs record the new promotion workflow without changing the canonical full verify command

## 10. Risks and mitigations

### Risk 1: promotion becomes a hidden second dispatch path

Mitigation:

1. keep promotion separate from dispatch
2. leave status as `pending`
3. require the normal execution claim later

### Risk 2: future phases start leaking into active again

Mitigation:

1. enforce `task.phase == current_phase + 1` in Version 1
2. keep promotion one-packet-at-a-time
3. preserve the existing active/planned queue tests

### Risk 3: envelope artifact drifts from actual queue move

Mitigation:

1. write the envelope inside the same apply path
2. include both before/after task refs in the artifact
3. refresh state immediately after the move

## 11. Decision summary

The approved direction is:

1. no large new promotion product surface yet
2. coordinator-owned promotion only
3. explicit promotion envelope artifact required
4. one-packet fail-closed promotion workflow under the existing worker task CLI
5. one real rehearsal using `ORPHANED-TASKS-STRUCTURED-REGISTRY`

That is the smallest design that turns promotion into a governed action instead of a manual queue mutation.
