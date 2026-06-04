# OMO governance overlay autopilot loop design

Date: 2026-06-03
Status: approved-by-user-default execution mode (user unavailable; proceed with the established default of direct spec/plan/execution)
Scope: turn the governance overlay shell into a safe first-step autopilot loop that can automatically advance planned-task roadmap items while leaving debt bundles read-only for now

## 1. Context

The governance overlay shell now exists:

1. `.omo/_control/governance-overlay/current.yaml`
2. `.omo/_truth/governance-overlay/roadmap.yaml`
3. `.omo/_truth/governance-overlay/autopilot-policy.yaml`
4. `.omo/workers/governance-overlay/current.yaml`

It can already answer:

1. what milestone is current?
2. what roadmap items are eligible?
3. what is the next recommended action?

But it still stops at recommendation.

The missing capability is:

> turn `next_action` into a real, safe, automatic execution step.

## 2. Problem statement

The user asked for OMO to run this lane automatically, self-iterating through issues until the target is reached.

The shell alone does not do that. It only surfaces:

1. the top eligible roadmap item
2. the blocked items
3. the policy

So the next missing layer is an **execution loop** that:

1. selects the top eligible roadmap item
2. resolves it to concrete target refs
3. drives existing OMO task/promotion/approval machinery
4. records what happened
5. updates roadmap progress without introducing a second task SSOT

## 3. Scope decision

This could expand too broadly if it tries to automate every roadmap item type at once.

So the first loop must stay intentionally narrow:

1. **automate `task-bundle` and `phase-bridge` items that reference `.omo/tasks/planned/*.yaml`**
2. **do not auto-execute `debt-bundle` items yet**
3. **reuse the existing promotion / approval flows instead of inventing new mutation paths**

This is the smallest slice that gives the user real automatic forward motion.

## 4. Goals

This slice should:

1. add one governance autopilot command that advances the top eligible roadmap item
2. resolve roadmap items only through existing task truth
3. auto-request approval when a planned task requires it and approval is missing/invalid
4. auto-promote when a planned task is already eligible
5. write an explicit run record and update roadmap item status/progress

## 5. Non-goals

This slice does not:

1. auto-fix debt bundles
2. replace the existing promotion approval rules
3. bypass human approval gates
4. close underlying implementation tasks automatically after promotion
5. implement trend/burndown analytics

## 6. Approaches considered

### A. Shell out to existing CLI commands only

Behavior:

1. the loop runs `scripts/omo_worker.py` subcommands via subprocess
2. parses stdout to decide what happened

Pros:

- minimal new integration logic

Cons:

- brittle stdout coupling
- hard to test precisely
- duplicates parsing work

This approach is rejected.

### B. Recommended: thin in-process orchestration over existing OMO helpers

Behavior:

1. load governance overlay status
2. choose the top candidate
3. inspect each planned target ref
4. reuse existing promotion / approval helpers already wired in `scripts/omo_worker.py`
5. write one governance run artifact plus roadmap status updates

Pros:

- keeps one mutation path
- easier to test deterministically
- narrower than a full “all roadmap item types” engine

Cons:

- requires touching roadmap status mutation logic
- needs careful blocked-state semantics

### C. Full all-types autopilot from day one

Behavior:

1. auto-advance planned tasks
2. auto-handle debt bundles
3. auto-handle every future roadmap type

Pros:

- maximum ambition

Cons:

- too much surface area for a first loop
- mixes execution automation with debt lifecycle automation
- higher chance of unclear failure modes

This approach is rejected for now.

## 7. Recommended design

Use **Approach B**.

The core decision is:

> add a thin governance overlay autopilot loop that only advances the top eligible planned-task roadmap item and expresses all outcomes through existing promotion / approval mechanisms plus explicit roadmap/run records.

The design principle stays:

> **overlay chooses, task truth executes**

Meaning:

1. the overlay decides which roadmap item is next
2. task truth still determines whether concrete work is eligible, blocked, approval-gated, or promotable

## 8. Command surface

Add one new command:

1. `python3 scripts/omo_worker.py task governance-overlay-run-next --omo-dir .omo --actor <ACTOR> [--now <ISO8601>]`

Behavior:

1. refresh the governance overlay status in-memory
2. select the first `autopilot_candidate`
3. resolve its `target_refs`
4. for each planned task target, run the existing promotion / approval decision tree
5. write one run artifact
6. update roadmap item status/progress
7. regenerate `.omo/workers/governance-overlay/current.*`

## 9. Supported target type

First version supports only:

1. refs under `.omo/tasks/planned/*.yaml`

If a candidate contains any other ref kind, the loop should:

1. not mutate the target
2. mark the roadmap item blocked with reason `unsupported_target_ref`
3. continue to the next cycle later

This is how `debt-bundle` stays read-only for now.

## 10. Planned-task decision tree

For each target planned task:

1. if the task file is missing → record `missing_target_ref`
2. if `promote-eval` would be ineligible for a non-approval reason (for example `phase_mismatch`) → record blocked outcome
3. if the task requires human approval and approval is missing/invalid → create a task-specific approval request
4. if the task is already approval-granted and otherwise eligible → promote it
5. if the task does not require approval and is eligible → promote it

This means the loop can produce three success-shaped outcomes:

1. `promoted`
2. `approval_requested`
3. `blocked`

## 11. Roadmap item status model

The roadmap registry should now use explicit execution-facing status values:

1. `pending`
2. `in_progress`
3. `blocked`
4. `done`

Rules:

1. first successful mutation (`promoted` or `approval_requested`) moves item to `in_progress`
2. unsupported refs or all-target blocked outcomes move item to `blocked`
3. item becomes `done` only when all of its planned task refs are no longer pending planned work

For first version, “no longer pending planned work” means:

1. the ref no longer exists in `tasks/planned/`, or
2. the corresponding task now exists in `tasks/active/` or `tasks/done/`

## 12. Run record

Each loop execution should write a governance run artifact:

1. `.omo/workers/runs/governance-overlay-<STAMP>.yaml`

It should record:

1. `run_id`
2. `overlay_id`
3. `roadmap_item_id`
4. `actor`
5. `started_at`
6. `completed_at`
7. `target_results[]`
8. `summary`

Each `target_results[]` entry should include:

1. `target_ref`
2. `task_id`
3. `result` (`promoted`, `approval_requested`, `blocked`, `unsupported_target_ref`, `missing_target_ref`)
4. `detail`

## 13. Governance status regeneration

After each loop run:

1. rewrite the roadmap registry if statuses changed
2. regenerate `.omo/workers/governance-overlay/current.yaml`
3. regenerate `.omo/workers/governance-overlay/current.md`

This keeps the overlay shell and the loop consistent.

## 14. Error handling

Fail closed:

1. if no candidate exists, do not mutate anything; write a no-op run with summary `idle`
2. if the top candidate contains unsupported refs, mark it blocked rather than guessing
3. if a target planned task requires approval, never auto-promote around the gate
4. if roadmap mutation fails, surface the error and do not silently continue

## 15. Testing

The implementation plan should cover:

1. no-op behavior when no eligible candidates exist
2. auto-request path for approval-gated planned tasks
3. auto-promote path for approval-free eligible planned tasks
4. blocked path for unsupported refs / missing refs
5. roadmap status mutation and run artifact creation
6. CLI/docs coverage

## 16. Rollout

Rollout should happen in bounded order:

1. add pure autopilot loop helper
2. add CLI command
3. add roadmap status mutation + run artifact writing
4. update docs/tests
5. rehearse one real governance overlay cycle

## 17. Success criteria

This slice is successful when:

1. OMO can run one governance overlay cycle automatically
2. the top roadmap candidate advances without manual file hunting
3. approval-gated tasks generate requests instead of stalling silently
4. the overlay status surface updates after the run
5. debt bundles remain safely out of execution scope until a later slice
