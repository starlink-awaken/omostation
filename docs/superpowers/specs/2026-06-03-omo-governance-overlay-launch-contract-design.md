# OMO governance overlay launch contract design

Date: 2026-06-03
Status: approved-by-user-default execution mode (user explicitly asked to continue without waiting for approval)
Scope: extend the governance overlay from dispatch-aware orchestration into launch-ready orchestration by making task-declared write scope a first-class control-plane contract

## 1. Context

The governance overlay already has four working layers:

1. a separate governance-only roadmap lane under `.omo/_truth/governance-overlay/roadmap.yaml`
2. a canonical read-side shell under `.omo/workers/governance-overlay/current.*`
3. an autopilot loop via `python3 scripts/omo_worker.py task governance-overlay-run-next --omo-dir .omo --actor <ACTOR> [--now <ISO8601>]`
4. dispatch / verify control actions for the current active roadmap item

That loop has already promoted and dispatched:

1. `D2-CI-E2E-TEST-ENV`
2. `D3-EU-PRICING-TEST`

The control-plane seam is working, but live execution exposed the next real gap:

> the overlay can safely preclaim and dispatch active work, but it still cannot safely decide when a task is launch-ready for autonomous code execution.

Today `dispatch_task(...)` derives `allowed_write_paths` from task `deliverables`, but the current active GOV-M1 tasks have no declared `deliverables`, so their worker envelopes were emitted with:

1. `required_deliverables: []`
2. `allowed_write_paths: []`

That means the overlay can mutate task lifecycle into `in_progress`, yet it still lacks a machine-readable contract proving that an external worker may edit the code paths needed to finish the task.

## 2. Problem statement

The current system has two coupled problems.

### A. Launch readiness is implicit

The worker registry already says external workers run in `task_declared_only` write mode, but the overlay does not yet treat task-declared write scope as an explicit launch gate.

As a result:

1. the overlay can dispatch a task with empty `allowed_write_paths`
2. the active roadmap status still renders that task as `active_in_progress`
3. the control surface falls back to `monitor:<ROADMAP_ITEM_ID>` even when the worker packet is not actually launch-safe

### B. Missing contract is not surfaced as a canonical blocker

`deliverables` already exist in the task schema and are already consumed by `dispatch_task(...)`, but when they are absent the system only emits an empty scope. It does not yet classify that condition as a first-class governance blocker.

The missing capability is:

> make launch readiness and contract gaps explicit in the overlay status model, and only allow autonomous launch when the task packet declares a safe write contract.

## 3. Scope decision

This slice should stay bounded.

It should:

1. promote task-declared write scope into a first-class launch contract
2. distinguish `dispatched-but-not-launch-ready` from `running`
3. auto-launch only when the task contract is complete and policy allows it
4. produce canonical contract-gap outcomes when the task is missing deliverables/write scope

It should not:

1. infer broad write permissions from heuristics
2. create a second task SSOT outside the task YAML
3. auto-close implementation tasks or roadmap items in the same slice
4. solve debt-bundle execution or future trend analytics
5. rewrite old tasks opportunistically without an explicit coordinator action

## 4. Goals

This slice should:

1. stop treating empty-scope dispatches as if they were fully running work
2. preserve the repository rule that external workers only write to task-declared paths
3. let the overlay move from `dispatch` to `launch` when the task packet is complete
4. let the overlay stop and explain itself when the task packet is incomplete
5. keep all decisions inside canonical OMO surfaces rather than hidden runtime conventions

## 5. Non-goals

This slice does not:

1. teach the overlay to guess missing deliverables from acceptance criteria
2. bypass human gates or L2/L3 restrictions
3. authorize writes to `.omo/state/system.yaml`, `.omo/goals/current.yaml`, or `convergence.yaml`
4. replace existing promotion approval or review semantics
5. invent a generalized planner for all future roadmap item types

## 6. Approaches considered

### A. Heuristic scope inference from `acceptance_criteria`, `test_plan`, and source docs

Behavior:

1. if `deliverables` are missing, derive candidate write paths from task prose
2. auto-launch with those inferred paths

Pros:

- fastest route to more automation

Cons:

- unsafe and non-deterministic
- violates the registry rule that workers write only to task-declared scope
- silently converts ambiguous prose into write authority

This approach is rejected.

### B. Recommended: explicit launch contract using existing task `deliverables`

Behavior:

1. keep `deliverables` as the canonical task-level write contract
2. compute launch readiness from `deliverables` + derived `allowed_write_paths` + dispatch artifact state
3. auto-launch only when the contract is explicit and policy allows it
4. surface contract gaps as canonical overlay states and run artifacts

Pros:

- preserves SSOT
- no new parallel registry of writable paths
- keeps auto-execution fail-closed
- directly matches existing worker envelope and schema semantics

Cons:

- some active tasks will stop at a contract-gap state until their packets are repaired
- requires richer status synthesis than the current `active_in_progress`

### C. Governance overlay allowlist per roadmap item

Behavior:

1. keep tasks unchanged
2. define writable paths in overlay roadmap/control files
3. let overlay inject those into dispatch/launch packets

Pros:

- avoids touching task packets

Cons:

- creates a second writable-scope truth source
- drifts from worker registry `task_declared_only`
- makes tasks less portable and harder to reason about in isolation

This approach is rejected.

## 7. Recommended design

Use **Approach B**.

Core principle:

> the only safe source of autonomous write authority is the task packet itself.

The overlay should not guess what a worker may change. It should read the task contract, classify whether the task is launch-ready, and either:

1. auto-launch when the contract is explicit
2. or surface a contract-gap blocker when it is not

## 8. Canonical launch contract

The canonical launch contract remains inside the task YAML:

1. `deliverables` = required writable outputs
2. derived `allowed_write_paths` = coordinator projection of those deliverables into worker-safe write roots

No new write-authority field is introduced in this slice.

Interpretation rules:

1. `deliverables` must remain explicit, stable, and writable
2. an empty `deliverables` list means the task is **not launch-ready for autonomous code change**
3. `allowed_write_paths` remain derived, not authored separately
4. the worker registry rule `write_scope.mode: task_declared_only` remains authoritative

## 9. Launch-readiness synthesis

Add a helper that classifies the active task’s launch contract:

1. `launch_ready`
2. `dispatch_only`
3. `contract_gap`

Recommended evaluation inputs:

1. task `deliverables`
2. derived `allowed_write_paths`
3. current dispatch artifact, if present

Decision rules:

1. if `deliverables` is empty -> `contract_gap`
2. if `deliverables` exists but derived `allowed_write_paths` is empty -> `contract_gap`
3. if the task has no dispatch artifact yet and the contract is valid -> `launch_ready` for dispatch+launch
4. if the task has a dispatch artifact with `dispatch_state: dispatched` and a valid contract -> `dispatch_only` ready to move into launch
5. if the task has a dispatch artifact in `checkpointed`, `completed`, or `reclaimed`, launch readiness is governed by the existing dispatch state machine rather than by re-dispatching

## 10. Active target state model extension

Extend the active-task synthesis so the overlay can distinguish:

1. `active_pending`
2. `active_dispatch_blocked`
3. `active_dispatched`
4. `active_running`
5. `active_review`

Rules:

1. `status: pending` in `tasks/active/` remains `active_pending`
2. `status: in_progress` with no dispatch artifact remains `active_running` only as a compatibility fallback
3. `status: in_progress` with `dispatch_state: dispatched` and contract gap -> `active_dispatch_blocked`
4. `status: in_progress` with `dispatch_state: dispatched` and valid launch contract -> `active_dispatched`
5. `status: in_progress` with `dispatch_state: checkpointed` -> `active_running`
6. `status: review` remains `active_review`

This prevents the current false signal where a task looks fully in progress even though it was only preclaimed with zero write scope.

## 11. Overlay `next_action` changes

Update `build_governance_overlay_status(...)` so active roadmap items may now emit:

1. `dispatch:<TASK_ID>`
2. `launch:<TASK_ID>`
3. `contract:<TASK_ID>`
4. `verify:<TASK_ID>`
5. `monitor:<ROADMAP_ITEM_ID>`

Priority order for an active roadmap item:

1. if any target is `active_pending` and launch contract is valid -> `dispatch:<TASK_ID>`
2. if any target is `active_pending` and launch contract is missing -> `contract:<TASK_ID>`
3. if any target is `active_dispatched` -> `launch:<TASK_ID>`
4. if any target is `active_dispatch_blocked` -> `contract:<TASK_ID>`
5. if any target is `active_review` -> `verify:<TASK_ID>`
6. if any target is `active_running` -> `monitor:<ROADMAP_ITEM_ID>`
7. else keep the existing `advance` / `close` / `block` semantics

This makes the overlay truthful about what is actually missing.

## 12. `run-next` behavior changes

`governance-overlay-run-next` should stay a single control-plane command, but its `continue_active` mode should gain two new execution branches.

### A. Contract-gap handling

When `next_action_before_run` is `contract:<TASK_ID>`:

1. do not dispatch or launch
2. write a run artifact with `summary: contract_gap`
3. record why the task is not launch-ready:
   - missing `deliverables`
   - or derived empty `allowed_write_paths`
4. keep the roadmap item `in_progress`

This is a fail-closed stop, not a silent fallback.

### B. Launch handling

When `next_action_before_run` is `launch:<TASK_ID>`:

1. read the active task and current dispatch artifact
2. verify the launch contract is still valid
3. execute the existing worker launch path
4. write run artifact summary `launched`
5. keep the roadmap item `in_progress`

This slice may implement launch in one of two safe ways:

1. preferred: extend the coordinator so the original dispatch can be launched from its stored prompt/envelope
2. acceptable fallback: when the task is still only `active_pending`, combine dispatch and launch into one step by calling `dispatch_task(..., launch=True, ...)`

The important invariant is the same:

> autonomous launch happens only when the task-declared contract is explicit and non-empty.

## 13. Task contract repair policy

This slice should not guess missing contracts, but it should make repair actionable.

Recommended operator surface:

1. run artifact includes `task_id`, `reason`, and current `deliverables`
2. overlay status detail names the exact contract gap
3. future slices may add a dedicated contract-repair helper, but this slice only needs canonical surfacing and fail-closed gating

For the currently active GOV-M1 tasks, this means:

1. `D2-CI-E2E-TEST-ENV` and `D3-EU-PRICING-TEST` should stop looking like ordinary running work
2. they should surface as contract-gap tasks until their packets declare explicit deliverables/write scope

## 14. Testing strategy

Add focused regressions for:

1. overlay status renders `contract:<TASK_ID>` for active tasks with missing deliverables
2. overlay status renders `launch:<TASK_ID>` for dispatched tasks whose launch contract is valid
3. `governance-overlay-run-next` writes `contract_gap` artifacts instead of dispatching/launching when scope is empty
4. `governance-overlay-run-next` launches a task only when `deliverables` produce non-empty `allowed_write_paths`
5. active target synthesis distinguishes `active_dispatch_blocked` from `active_running`

## 15. Expected outcome

After this slice:

1. the governance overlay will stop pretending that every dispatched task is fully executing
2. fully automatic execution will become safe for tasks that already declare explicit deliverables
3. tasks without explicit write contracts will fail closed with a canonical contract-gap outcome
4. the next bounded slice can focus on worker result ingestion / verify-closeout, not on write-scope ambiguity
