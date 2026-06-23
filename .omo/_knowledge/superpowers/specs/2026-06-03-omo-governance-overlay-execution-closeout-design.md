---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# OMO governance overlay execution-closeout design

Date: 2026-06-03
Status: approved-by-user-default execution mode (user explicitly asked to continue without waiting for approval)
Scope: extend the governance overlay autopilot loop so an `in_progress` roadmap item can keep moving through execution tracking and eventual milestone closeout instead of stalling at `idle`

## 1. Context

The governance overlay now has two working layers:

1. shell status surfaces under `.omo/workers/governance-overlay/current.*`
2. a first execution loop via `python3 scripts/omo_worker.py task governance-overlay-run-next --omo-dir .omo --actor <ACTOR> [--now <ISO8601>]`

That loop already advanced `GOV-M1-EXECUTION-HARDENING` by promoting:

1. `D2-CI-E2E-TEST-ENV`
2. `D3-EU-PRICING-TEST`

and explicitly surfacing phase blockers for:

1. `P25-W1-E2E-INTEGRATION`
2. `P25-W2-DOCS-DEBT-CLOSURE`

The result is good progress, but it exposed the next missing seam:

> once a roadmap item becomes `in_progress`, the overlay shell currently loses the next executable action and falls back to `idle`.

That is the opposite of the user’s intent. The user asked for a loop that keeps iterating through milestones and task management automatically instead of stopping after the first mutation.

## 2. Problem statement

The current overlay status logic only treats `pending` roadmap items as candidates.

That means:

1. `pending` items can be selected and promoted
2. `blocked` items can be surfaced
3. but `in_progress` items are effectively invisible to the control loop

So after the first successful promotion:

1. the roadmap item stays `in_progress`
2. dependent roadmap items remain blocked
3. current status no longer exposes what to do next for the live `in_progress` item
4. `governance-overlay-run-next` has no structured way to continue toward completion

The missing capability is:

> turn `in_progress` roadmap items into first-class control-plane subjects with target-state synthesis, next-action derivation, and milestone closeout rules.

## 3. Scope decision

This slice still needs to stay narrow.

The loop should learn how to:

1. inspect target task lifecycle across `planned/`, `active/`, `done/`, and `blocked/`
2. describe the live state of an `in_progress` roadmap item
3. close a roadmap item when its targets are no longer future planned work
4. advance the overlay control state to the next roadmap item when the current one is done

This slice should **not** yet:

1. auto-launch external workers
2. infer file write scopes for dispatch
3. auto-close underlying implementation tasks
4. solve debt-bundle execution
5. build trend / burndown analytics

## 4. Goals

This slice should:

1. stop the overlay from stalling after the first successful `run-next`
2. make `in_progress` roadmap items visible in the canonical overlay surface
3. derive a real `next_action` for a live milestone
4. let `run-next` update milestone state based on actual task lifecycle
5. move overlay control forward when a roadmap item reaches completion

## 5. Non-goals

This slice does not:

1. replace the existing task lifecycle semantics
2. dispatch or launch workers automatically
3. bypass promotion approval or phase gates
4. mutate debt truth
5. decide when underlying active tasks are “done enough” beyond existing task truth

## 6. Approaches considered

### A. Keep `in_progress` items implicit and add a second command just for closeout

Behavior:

1. leave `governance-overlay-status` candidate logic unchanged
2. add a dedicated closeout command that separately scans for `in_progress` items

Pros:

- minimal shell changes

Cons:

- splits operator truth across two commands
- keeps `current.yaml` incomplete
- does not really solve the “what is next?” problem

This approach is rejected.

### B. Recommended: make `in_progress` roadmap items part of the canonical overlay status model

Behavior:

1. enrich `build_governance_overlay_status(...)`
2. expose `active_roadmap_item` plus per-target synthesized states
3. let `governance-overlay-run-next` operate on the active item before scanning new pending candidates
4. close and advance control state when the active item is complete

Pros:

- one canonical control surface
- `run-next` becomes a true loop, not a one-shot promoter
- deterministic and testable

Cons:

- requires a more explicit per-target state model
- needs careful closeout semantics

### C. Full orchestration now: dispatch, verify, review, and closeout in one slice

Behavior:

1. when tasks become active, auto-dispatch them
2. auto-track review/verification
3. auto-close roadmap items when evidence is complete

Pros:

- most ambitious automation jump

Cons:

- needs worker-selection policy, write-path policy, and review-closure policy
- too much new scope for one bounded slice

This approach is rejected for now.

## 7. Recommended design

Use **Approach B**.

Core principle:

> the overlay should know whether the current roadmap item is still promoting, waiting on active execution, blocked on remaining planned targets, or ready to close.

The loop must become milestone-aware, not just candidate-aware.

## 8. Canonical status model extension

Extend `build_governance_overlay_status(...)` so it no longer treats only `pending` items as meaningful.

The canonical packet should now include:

1. `active_roadmap_item` (nullable)
2. `active_target_states[]` for the current `in_progress` item
3. `next_action`

Rules:

1. only one roadmap item should be considered active at a time in v1
2. if an `in_progress` item exists, it takes precedence over pending candidates
3. pending candidates are considered only when there is no active item

## 9. Target-state synthesis

For each target ref in the active roadmap item, derive a machine-readable state.

Supported synthesized states:

1. `planned_pending`
2. `planned_blocked`
3. `active_pending`
4. `active_in_progress`
5. `active_review`
6. `done`
7. `unsupported_target_ref`
8. `missing_target_ref`

Resolution rules:

1. if the ref is not under `.omo/tasks/planned/*.yaml` → `unsupported_target_ref`
2. if the same filename exists under `tasks/done/` → `done`
3. else if it exists under `tasks/blocked/` → `planned_blocked`
4. else if it exists under `tasks/active/` → derive `active_pending` / `active_in_progress` / `active_review` from `task.status`
5. else if it still exists under `tasks/planned/` → `planned_pending`
6. else → `missing_target_ref`

This gives the overlay a stable view even after tasks move between directories.

## 10. Next-action derivation

`next_action` should prefer the current active roadmap item over new pending roadmap items.

Rules for an active roadmap item:

1. if any target state is `active_pending` → `execute:<TASK_ID>`
2. else if any target state is `active_in_progress` or `active_review` → `monitor:<ROADMAP_ITEM_ID>`
3. else if any target state is `planned_pending` → `advance:<ROADMAP_ITEM_ID>`
4. else if all target states are `done` → `close:<ROADMAP_ITEM_ID>`
5. else if all target states are terminal blockers (`planned_blocked`, `unsupported_target_ref`, `missing_target_ref`) → `block:<ROADMAP_ITEM_ID>`

Rules when no active roadmap item exists:

1. keep the current pending-candidate logic from the first autopilot slice

## 11. `run-next` behavior change

`governance-overlay-run-next` should now have two phases:

### Phase A — active item continuation

If an `in_progress` roadmap item exists:

1. synthesize target states
2. if all are `done`, mark the roadmap item `done`
3. if all are terminal blockers and none are active/done, mark the roadmap item `blocked`
4. otherwise keep it `in_progress` and write a progress-shaped run artifact

### Phase B — pending candidate advancement

Only when there is no active roadmap item:

1. run the existing promotion / approval logic from the first loop slice

This keeps one command while turning it into a real loop.

## 12. Control-state advancement

When an active roadmap item becomes `done`, update `.omo/_control/governance-overlay/current.yaml`:

1. set `current_milestone` to the next pending roadmap item id, or `null` if none remain
2. set `next_milestone` to the following pending roadmap item id, or `null`
3. update `updated_at`

Do not mutate `current_phase`.

This preserves the original shell rule:

> separate governance lane, shared truth, no numbered-phase pollution.

## 13. Roadmap closeout semantics

A roadmap item becomes `done` when all target refs have left future planned work.

In this slice that means every target is one of:

1. `done`
2. `active_pending`
3. `active_in_progress`
4. `active_review`

No — that would be too weak, because active tasks are not completed work.

So the correct closeout rule is stricter:

1. every target must be `done`, or
2. every non-done target must be explicitly terminal-blocked and the roadmap item is therefore `blocked`, not `done`

Therefore:

1. active tasks keep the roadmap item `in_progress`
2. only done tasks contribute to roadmap item completion

## 14. Run artifact extension

Keep the existing `.omo/workers/runs/governance-overlay-<STAMP>.yaml` path, but extend its payload.

Additional fields:

1. `mode` (`advance_pending` or `continue_active`)
2. `target_state_summary`
3. `control_updates`

For `continue_active` runs, `target_results[]` should carry the synthesized per-target state rather than promotion-only outcomes.

## 15. Error handling

Fail closed:

1. missing control/roadmap/policy inputs still fail hard
2. unsupported target refs never get auto-mutated
3. ambiguous multi-active-roadmap situations fail with an explicit error instead of guessing

Do not add silent fallbacks.

## 16. Testing strategy

Add three layers of tests:

1. helper tests for target-state synthesis and next-action derivation
2. CLI tests for `governance-overlay-run-next` when continuing an active roadmap item
3. docs regressions for the updated operator contract

Need explicit cases for:

1. `active_pending` target produces `next_action=execute:<TASK_ID>`
2. `done` active roadmap item is closed and control milestone advances
3. fully terminal-blocked active roadmap item becomes `blocked`

## 17. Success criteria

This slice is successful when:

1. `governance-overlay/current.yaml` exposes the live `in_progress` roadmap item
2. `next_action` no longer falls back to `idle` while the current roadmap item still has unfinished targets
3. `governance-overlay-run-next` can close a finished roadmap item and advance control state
4. the overlay continues to govern future work without touching numbered phase state
