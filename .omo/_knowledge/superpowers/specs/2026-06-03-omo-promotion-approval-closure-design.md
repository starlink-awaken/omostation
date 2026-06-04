# OMO promotion approval closure / status surface design

Date: 2026-06-03
Status: approved-by-user-default execution mode (user remains unavailable; proceed with the previously established default of direct spec/plan/implementation)
Scope: close the promotion approval operator loop by adding a canonical status surface for requested/granted promotion approvals while continuing to use the existing generic governance approve/apply commands

## 1. Context

Promotion approval now has three working pieces:

1. strict promotion gate semantics (`approval_invalid` unless the approval YAML is task-specific, granted, and correctly scoped)
2. task-side request workflow (`task promotion-request-approval`)
3. generic truth-mutation governance commands (`scripts/omo_governance.py approve/apply`)

The missing operator seam is now narrower:

> after a request exists, how does an operator see which proposal to approve/apply, what state it is in, and whether the promotion gate has actually unblocked?

Today the answer is spread across several files:

1. planned task packet (`approval_ref`)
2. approval YAML (`approval_status`)
3. truth proposal YAML (`status`)
4. readiness surface (`approval_invalid` or not)

That is enough for power users, but not yet a canonical operator closure surface.

## 2. Why this slice now

After the request workflow landed, there are three plausible next moves:

1. add a promotion-specific approve/apply wrapper command
2. add a promotion approval status / closure surface while reusing existing governance commands
3. stop at docs-only operator guidance

The second is the smallest correct step because:

1. the governance primitives already exist and are tested
2. what is missing is visibility and a canonical operator path, not a new mutation primitive
3. duplicating approve/apply behind promotion-specific wrappers would widen the surface area before proving the thinner model is insufficient

## 3. Goals

This slice should:

1. provide one canonical read surface for promotion approval lifecycle state
2. make proposal discovery deterministic from the planned queue / approval artifacts
3. show whether a request is still blocked because it is only requested, approved-but-not-applied, or genuinely granted
4. keep mutation semantics on the existing governance commands
5. demonstrate a real requested -> approved/applied -> readiness-unblocked rehearsal

## 4. Non-goals

This slice does not:

1. add a new promotion-specific approve/apply mutation command
2. redesign `scripts/omo_governance.py`
3. add bulk approval for multiple tasks
4. change the promotion gate rules themselves
5. auto-refresh readiness on every governance mutation

## 5. Approaches considered

### A. Docs-only closure

Behavior:

1. document how to derive `proposal_id` from the request artifact
2. instruct operators to run generic governance commands by hand
3. rely on `promotion-readiness` alone to detect success

Pros:

- zero new code
- smallest possible delta

Cons:

- proposal discovery remains implicit
- no canonical promotion-side lifecycle surface
- hard to tell `proposed` vs `approved` vs `verified` without opening several files

This approach is rejected.

### B. Recommended: add promotion approval status / closure surface

Behavior:

1. derive lifecycle state from planned tasks that point at task-specific promotion approval YAML
2. expose approval record + proposal status + effective gate outcome in one canonical surface
3. keep approve/apply on the existing governance CLI

Pros:

- smallest slice that truly closes the operator loop
- avoids mutation duplication
- preserves the current control-plane separation: promotion owns request/read-side visibility, governance owns state mutation

Cons:

- operators still run two commands (`approve`, then `apply`) instead of one wrapper
- adds one more read-side surface under `workers/promotion/`

### C. Add promotion-specific approve/apply wrapper commands

Behavior:

1. `task promotion-approval-approve <TASK_ID> ...`
2. `task promotion-approval-apply <TASK_ID> ...`

Pros:

- shorter operator syntax
- promotion operators do not need to know about proposal ids

Cons:

- duplicates governance mutation semantics
- creates another path to the same state change
- higher maintenance surface before the thinner model has been exhausted

This approach is rejected for now.

## 6. Recommended design

Use **Approach B**.

The core decision is:

> add one canonical promotion approval status command and surface, while continuing to use `scripts/omo_governance.py approve/apply` for the actual state transitions.

That yields a clean separation:

1. `task promotion-request-approval` creates the request
2. `task promotion-approval-status` tells operators what exists and what is still blocked
3. `scripts/omo_governance.py approve/apply` performs the governed mutation
4. `task promotion-readiness` confirms whether the approval blocker is gone

## 7. Workflow contract

### 7.1 CLI surface

Add one new task-side command:

1. `python3 scripts/omo_worker.py task promotion-approval-status --omo-dir .omo [--task-id <TASK_ID>] [--now <ISO8601>]`

Behavior:

1. without `--task-id`, scan the planned queue and surface every task that points at a task-specific promotion approval YAML
2. with `--task-id`, return only the selected task’s promotion approval lifecycle entry
3. write canonical current surfaces under `.omo/workers/promotion/approvals/`

### 7.2 Derived fields

Each status entry should include:

1. `task_id`
2. `task_ref`
3. `approval_ref`
4. `approval_id`
5. `approval_status`
6. `proposal_id`
7. `proposal_ref`
8. `proposal_status`
9. `human_approval_required`
10. `eligible`
11. `blockers`

The derived rule is:

1. `approval_status: requested` + `proposal_status: proposed` -> still blocked
2. `approval_status: requested` + `proposal_status: approved` -> still blocked
3. `approval_status: granted` + proposal `verified` -> approval blocker removed
4. final `eligible` still depends on the existing promotion gate, so a task can remain blocked by `phase_mismatch` even after approval is granted

## 8. Data source contract

The status surface should derive from:

1. `.omo/tasks/planned/*.yaml`
2. task-specific approval YAML under `.omo/workers/runs/*-promotion-approval-*.yaml`
3. proposal YAML under `.omo/_truth/task-center/proposals/*.yaml`
4. existing `_promotion_eval(...)`

Proposal discovery should be deterministic:

1. if `approval_id` is `X`, then the proposal id is `X-proposal`
2. proposal ref is `.omo/_truth/task-center/proposals/<proposal_id>.yaml`

No new persisted index is required in this slice.

## 9. Surface contract

Write:

1. `.omo/workers/promotion/approvals/current.yaml`
2. `.omo/workers/promotion/approvals/current.md`

The YAML packet should contain:

1. `generated_at`
2. `approval_task_count`
3. `requested_count`
4. `approved_pending_apply_count`
5. `granted_count`
6. ordered `tasks[]`

Ordering rule:

1. blocked entries first
2. then by `proposal_status` in lifecycle order (`proposed`, `approved`, `verified`, `missing`)
3. then by `task_id`

Markdown should make the operator action obvious:

1. proposed -> “run governance approve”
2. approved -> “run governance apply”
3. verified/granted -> “approval blocker cleared; check readiness for remaining blockers”

## 10. Interaction with readiness

This slice does not change readiness semantics.

Instead it makes the handoff explicit:

1. before apply, readiness continues to show `approval_invalid`
2. after apply updates the approval YAML to `granted`, readiness should drop `approval_invalid`
3. any remaining blockers are outside approval (for example `phase_mismatch`)

This gives a deterministic, auditable operator flow:

1. request
2. status surface
3. governance approve
4. status surface
5. governance apply
6. readiness

## 11. Error handling

Fail closed:

1. if a planned task points at a missing approval YAML -> entry stays visible with `proposal_status: missing`
2. if approval YAML exists but is malformed -> entry stays visible with `blockers: [approval_invalid]`
3. if proposal YAML is missing -> status surface still renders the task and marks proposal missing
4. if `--task-id` is supplied for a planned task without task-specific approval -> reject explicitly

No silent dropping of broken request state.

## 12. Testing

Add tests for:

1. helper builds lifecycle entries for requested/proposed, requested/approved, and granted/verified states
2. CLI writes `approvals/current.yaml` + `.md`
3. `--task-id` rejects tasks without task-specific promotion approval
4. docs explain that promotion operators use status surface + generic governance approve/apply
5. real or synthetic closure path proves readiness drops `approval_invalid` after apply

## 13. Rollout

1. add pure helper for status packet construction
2. add `task promotion-approval-status`
3. document operator closure flow
4. rehearse approve/apply on the existing `P19-W3-ARCHIVE-TS` request
5. refresh readiness + approval status surfaces
6. run deterministic `.omo` verification
