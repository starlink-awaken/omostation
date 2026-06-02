# OMO future backlog governance design

Date: 2026-06-02
Status: approved direction (user accepted continuation with the recommended strict-active-only model)
Scope: normalize how future-phase backlog is represented in `.omo` so `tasks/active/` returns to being the current executable queue, while future-phase work moves to a separate planned surface and `state/system.yaml` stays a derived summary instead of a backlog blob

## 1. Context

The current `.omo` task model has a semantic split that is no longer internally consistent:

1. `.omo/tasks/README.md` defines `tasks/active/` as the current active queue for work that is executing or ready to execute.
2. `.omo/standards/task-gate-model.md` defines `task.status` as the canonical truth field and gate facts as derived evidence, which implies queue placement should also remain semantically clean.
3. `.omo/state/system.yaml` currently derives `active_tasks` and `next_active_tasks`, but the live surface also carries a long future-phase backlog list that includes P17-P25 packets.
4. `.omo/_knowledge/management/omo-convergence-audit-2026-05-31.md` already identifies this as a governance debt: backlog should not keep living as a blob inside `state/system.yaml`; it should move to per-task or registry-style artifacts.
5. `.omo/_knowledge/design/debt-cleanup-plan.md` makes `O1-orphaned_tasks` structure completion a Phase 17 exit condition.

The immediate symptom was just repaired in verification:

1. active task schema debt was backfilled so current files validate again.
2. phase closeout tests were generalized so future-phase backlog no longer falsely looks like stale current-phase work.

That repair was necessary, but it was not the final design. The deeper problem remains:

> today, `tasks/active/` is acting both as the current executable queue and as a long-horizon backlog container.

If that dual meaning stays in place, the system will keep re-creating shadow queue behavior even when individual tests are green.

## 2. Goals

This design should:

1. restore `tasks/active/` to a single clear meaning: current executable queue
2. move future-phase backlog into a separate truth surface
3. keep `state/system.yaml` derived rather than turning it into a backlog registry
4. preserve the Wave 2 rule that canonical task truth lives in task files, not in summary blobs
5. make phase-closeout and queue-validation rules easier to reason about and test
6. support Phase 17 debt governance without inventing another shadow queue

## 3. Non-goals

This design does not:

1. redesign the canonical task schema itself
2. change the `task.status` enum
3. replace dispatch, review, or approval artifacts
4. define the full execution content of every P17-P25 packet
5. change human ownership of `.omo/goals/current.yaml`
6. introduce forecasting or prioritization math for backlog ordering

## 4. Approaches considered

### A. Recommended: strict-active-only plus a separate planned backlog surface

Behavior:

1. `tasks/active/` contains only `pending`, `in_progress`, or `review` packets that are allowed to be worked now.
2. future-phase work moves to a separate truth surface such as `tasks/planned/`.
3. `state/system.yaml` reports summary counts and references, not embedded future-phase backlog lists.
4. promotion into `tasks/active/` becomes an explicit governance step instead of an implicit side effect of planning.

Pros:

- the queue meaning matches `tasks/README.md`
- aligns with the Wave 2 truth-vs-derived model
- removes backlog blob pressure from `state/system.yaml`
- makes future-phase backlog visible without pretending it is already active
- gives verification a cleaner invariant surface

Cons:

- requires a one-time migration of future-phase packets out of `tasks/active/`
- requires `sync_omo_state.py`, docs, and tests to learn the new planned surface

### B. Hybrid near-term preheat queue

Behavior:

1. `tasks/active/` keeps current-phase work plus a small, explicitly approved next-phase preheat slice.
2. deeper future backlog still moves to a separate planned surface.

Pros:

- preserves some early visibility for immediately upcoming packets
- can model real preheat work when the next phase must start fast

Cons:

- reintroduces ambiguity around what "active" means
- requires a second rule set for exceptions
- is easier to misuse until strong guardrails exist

This approach is deferred unless strict-active-only proves too rigid in live use.

### C. Keep future backlog inside `tasks/active/` and just document it better

Pros:

- least migration work
- minimal short-term churn

Cons:

- keeps the semantic contradiction in place
- guarantees future drift between queue meaning and system summaries
- preserves the exact shape of shadow queue debt that Phase 17 is supposed to remove

This approach is rejected.

## 5. Recommended design

Use **Approach A**.

The core decision is:

> `tasks/active/` becomes the current executable queue again, and future-phase backlog moves to a dedicated planned truth surface so queue semantics, state summaries, and governance tests all describe the same reality.

This is the right design because:

1. it restores a clean boundary between truth and derived summaries
2. it lets `state/system.yaml` go back to summary duty instead of acting like a registry
3. it prevents future-phase planning artifacts from being mistaken for already-active work
4. it directly fulfills the Phase 17 `O1-orphaned_tasks` cleanup direction

## 6. Architecture

### 6.1 Queue layers

The task layout should become:

```text
tasks/
├── active/    # executable now
├── planned/   # future-phase or not-yet-promoted backlog
├── blocked/   # blocked executable work
└── done/      # completed work
```

Definitions:

1. `active/` contains tasks that may be executed now under current governance rules.
2. `planned/` contains future-phase packets, pre-gate packets, and backlog that is intentionally visible but not yet executable.
3. `blocked/` remains for executable work that cannot currently proceed.
4. `done/` remains the archive for completed work.

### 6.2 Canonical truth stays in task files

The new `planned/` surface is not a summary index. It follows the same per-task YAML truth style as `active/`.

That means:

1. each future packet still has a real task file
2. `task.status` remains canonical within the file
3. queue placement communicates execution eligibility, not an alternate lifecycle vocabulary

In other words:

1. `pending` in `planned/` means "planned but not yet promoted"
2. `pending` in `active/` means "ready to be picked up in the active queue"

The status enum does not change; queue placement supplies the extra execution-context meaning.

### 6.3 Promotion rule becomes explicit

Promotion from `planned/` to `active/` happens only when all of the following are true:

1. the packet is inside the current authorized execution horizon
2. its phase/milestone is now eligible under the current gate
3. any required approval reference exists
4. the packet has the schema fields required for active execution

This keeps future packets visible without falsely implying that execution may already begin.

### 6.4 `state/system.yaml` becomes a summary surface again

`state/system.yaml` should stop embedding long future-backlog lists as if they are active queue facts.

Instead, it should derive and expose:

1. `active_tasks` count from `tasks/active/`
2. `planned_tasks` count from `tasks/planned/`
3. `blocked_tasks` count from `tasks/blocked/`
4. `next_active_tasks` as a derived shortlist based on promotion rules
5. optional reference fields that point to planned backlog surfaces rather than copying them inline

The summary may still expose a compact preview, but the source of truth must remain the task files.

### 6.5 Phase-closeout rules simplify

Once future-phase packets no longer live in `active/`, closeout and validation rules become simpler:

1. current phase or earlier incomplete work must not linger in the wrong queue
2. future-phase packets belong in `planned/` unless a documented near-term exception exists
3. `active/` is no longer allowed to function as a catch-all staging area

## 7. Data flow

The intended control flow is:

1. humans or coordinators define future packets under `tasks/planned/`
2. `sync_omo_state.py` derives counts and previews from `active/`, `planned/`, `blocked/`, and `done/`
3. when a packet becomes eligible, governance promotes it from `planned/` to `active/`
4. execution uses the existing active-task lifecycle (`pending -> in_progress -> review -> done` or `blocked`)
5. completion still archives into `done/`

This keeps planning, execution, and summary derivation in separate layers.

## 8. Validation and testing

The design should add or update tests in four areas:

1. **schema validation**
   - `active/` requires full active-execution fields
   - `planned/` allows future packets without pretending they are already dispatched
2. **state derivation**
   - `sync_omo_state.py` counts `planned_tasks` separately from `active_tasks`
   - `next_active_tasks` is derived from promotion logic, not copied from backlog blobs
3. **phase closeout**
   - completed or current-phase stale tasks are still rejected when misplaced
   - future-phase packets in `planned/` no longer trigger false stale-active failures
4. **documentation contract**
   - `.omo/tasks/README.md` and `.omo/AGENT.md` clearly distinguish `active/` from `planned/`

## 9. Migration plan

Migration should be one bounded governance slice owned by `P17-DEBT-GOVERNANCE-GATE-RULES` or its immediate follow-on.

Recommended migration order:

1. add the `planned/` surface and document its contract
2. teach validation code which rules apply to `planned/` versus `active/`
3. move future-phase packets from `active/` into `planned/`
4. update `sync_omo_state.py` to derive separate counts and previews
5. update phase-closeout tests and worker/queue docs
6. run full `.omo` verification and refresh derived state artifacts

This order reduces risk because validation and derivation learn the new surface before the queue migration lands.

## 10. Error handling and failure policy

This design should fail closed on contradictory queue semantics.

Examples:

1. a task in `active/` that lacks required active schema fields should remain invalid
2. a task in `planned/` that claims live dispatch/review linkage should be rejected unless promotion has occurred
3. `state/system.yaml` derivation should not silently treat planned backlog as active work

The goal is to surface queue ambiguity as a governance error, not to smooth over it in summaries.

## 11. Risks and mitigations

### Risk 1: operators miss the old one-place-to-look active list

Mitigation:

1. keep `state/system.yaml` previews explicit
2. document `planned/` prominently in `.omo/tasks/README.md` and `.omo/AGENT.md`
3. expose a derived "upcoming planned packets" preview so visibility stays high

### Risk 2: `planned/` becomes a second shadow queue

Mitigation:

1. keep it as a truth surface with per-task files, not a prose list
2. make promotion rules explicit and testable
3. avoid adding custom status vocabulary inside planned files

### Risk 3: migration churn touches many task files at once

Mitigation:

1. separate spec/plan/migration clearly
2. migrate in one bounded slice with verification immediately afterward
3. avoid mixing unrelated task-content edits with queue relocation

## 12. Decision summary

The approved direction is:

1. adopt **strict-active-only**
2. introduce a dedicated planned truth surface for future-phase backlog
3. stop using `state/system.yaml` as a backlog blob carrier
4. make promotion into `active/` an explicit governance step

That is the smallest design that resolves the current contradiction without weakening the Wave 2 task model.
