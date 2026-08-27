---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# OMO promotion readiness surface design

Date: 2026-06-03
Status: approved-by-user-default execution mode (user explicitly waived intermediate review gates and requested direct spec/plan/execution)
Scope: add a canonical derived readiness/current surface for planned task promotion so operators can see which packets are promotable now and which gates are blocking the rest

## 1. Context

The promotion workflow now has three working pieces:

1. `python3 scripts/omo_worker.py task promote-eval <TASK_ID> --omo-dir .omo`
2. `python3 scripts/omo_worker.py task promote-apply <TASK_ID> --promoted-by <ACTOR> --now <ISO8601> --omo-dir .omo`
3. `python3 scripts/omo_worker.py task promotion-history --omo-dir .omo [--now ...]`

That means OMO can:

1. evaluate one packet
2. promote one packet
3. summarize what promotions have already happened

The remaining operator gap is on the read side of the *planned* queue:

> which packets are promotable right now, and what exact gate blocks the rest?

Today that answer requires manual repetition:

1. list planned packets
2. inspect current phase
3. run `promote-eval` one task at a time
4. mentally compare blockers across tasks

That is not a stable governance surface.

## 2. Why this slice now

There were three realistic follow-ups after promotion history landed:

1. add richer history readers such as list/show/diff
2. add approval-gated promotion mechanics for deeper future phases
3. materialize current promotion readiness across the planned queue

The current queue makes the third option the most useful next step:

1. Phase 17 still has real planned packets that are near-field promotion candidates
2. many deeper packets already carry `approval_ref`, but most are still blocked first by the phase gate, not by missing visibility
3. operators currently lack one canonical answer for "what is promotable now?"

Because of that, readiness provides more immediate value than either richer history browsing or future-phase approval mechanics.

## 3. Goals

This design should:

1. create one canonical current surface for promotion readiness
2. reuse the existing `_promotion_eval(...)` contract instead of duplicating gate logic
3. show both promotable tasks and blocked tasks in one deterministic packet
4. preserve raw task packets as truth and derived readiness as refreshable state
5. support deterministic refresh with `--now`

## 4. Non-goals

This design does not:

1. redesign promotion eligibility rules
2. change the semantics of `promote-eval` or `promote-apply`
3. add approval-specific execution artifacts yet
4. add long-term trends or burndown analytics
5. mutate tasks automatically based on readiness output

## 5. Approaches considered

### A. Add richer history readers first

Behavior:

1. add `promotion-list`, `promotion-show`, or `promotion-diff` on top of the new history surface

Pros:

- easy extension of the work that just landed
- helpful once promotion volume grows

Cons:

- answers "what happened", not "what can happen next"
- provides limited value while there is only one promotion envelope
- does not reduce one-by-one `promote-eval` operator work

This approach is deferred.

### B. Recommended: add one readiness/current surface

Behavior:

1. scan all planned task packets
2. evaluate each with the existing promotion gate logic
3. write one canonical readiness packet plus one Markdown operator summary

Pros:

- immediately useful for the current Phase 17 planned queue
- reuses tested promotion evaluation logic
- gives later approval and campaign slices one stable read surface

Cons:

- adds another derived surface to refresh
- still leaves richer history browsing for a later slice

### C. Implement approval-gated promotion next

Behavior:

1. deepen approval semantics for promotion of future L2/L3 packets

Pros:

- addresses an important future governance seam
- likely needed before higher-risk phase promotion

Cons:

- current near-field queue is blocked more by phase progression than by missing approval mechanics
- would add mechanics before operators can see readiness across the whole queue
- lacks a strong immediate rehearsal candidate compared with readiness

This approach is deferred.

## 6. Recommended design

Use **Approach B**.

The core decision is:

> add a `task promotion-readiness` materializer that scans planned tasks, evaluates each through the existing promotion gate contract, and writes `.omo/workers/promotion/readiness.yaml` plus `.md`.

This is the smallest correct next step because:

1. it answers the next operational question after promotion history
2. it avoids new mutation behavior
3. it turns repeated one-off evals into one canonical governance surface

## 7. Architecture

### 7.1 Stay inside `scripts/omo_worker.py task`

Add one new read-side command:

1. `python3 scripts/omo_worker.py task promotion-readiness --omo-dir .omo --now <ISO8601>`

`--now` is optional and follows the same deterministic-refresh pattern already used for promotion history.

### 7.2 Raw truth stays in planned packets and goals state

The readiness surface is derived from:

1. `.omo/tasks/planned/*.yaml`
2. `.omo/goals/current.yaml`
3. the existing promotion gate rules already encoded in `_promotion_eval(...)`

The readiness surface is not a new source of truth; it is a refreshable operator packet.

### 7.3 Add a dedicated derived surface under `.omo/workers/promotion/`

Write:

1. `.omo/workers/promotion/readiness.yaml`
2. `.omo/workers/promotion/readiness.md`

`current.yaml` remains the history surface for completed promotions.
`readiness.yaml` becomes the current surface for planned promotion eligibility.

### 7.4 Canonical YAML contract

`readiness.yaml` should look like:

```yaml
generated_at: "2026-06-03T00:00:00Z"
current_phase: 16
target_phase: 17
ready_count: 3
blocked_count: 29
tasks:
  - task_id: "P17-W1-ARCHITECTURE-FOUNDATION"
    task_ref: ".omo/tasks/planned/P17-W1-ARCHITECTURE-FOUNDATION.yaml"
    phase: 17
    status: "pending"
    risk_level: "L1"
    allowed_operation_level: "L1"
    human_approval_required: false
    approval_ref: null
    eligible: true
    blockers: []
    checks:
      queue_membership_ok: true
      status_ok: true
      phase_ok: true
      approval_ready: true
      target_path_clear: true
      active_schema_ready: true
    errors: []
```

Rules:

1. `tasks` contains every planned task, not just eligible ones
2. entries are ordered with eligible tasks first, then by `phase`, then `task_id`
3. `ready_count` counts `eligible: true`
4. `blocked_count` counts `eligible: false`
5. `checks`, `blockers`, and `errors` are copied from the existing promotion eval result, not reinterpreted

### 7.5 Markdown view is operator-facing

`readiness.md` should be a compact summary, for example:

```md
# Task Promotion Readiness

Generated at: 2026-06-03T00:00:00Z
Current phase: 16
Target phase: 17
Ready tasks: 3
Blocked tasks: 29

## Ready: P17-W1-ARCHITECTURE-FOUNDATION

task_ref=.omo/tasks/planned/P17-W1-ARCHITECTURE-FOUNDATION.yaml
phase=17
blockers=none

## Blocked: P18-W1-NEURAL-CENTER

task_ref=.omo/tasks/planned/P18-W1-NEURAL-CENTER.yaml
phase=18
blockers=phase_mismatch
```

The Markdown view is a readable projection only; YAML remains the machine-facing packet.

## 8. Implementation boundary

Version 1 should stay narrow:

1. add one pure rendering/helper module, `scripts/omo_promotion_readiness.py`
2. add one CLI materializer in `scripts/omo_worker.py`
3. add focused tests for helper, CLI wiring, and docs
4. hydrate the live readiness surface from the current queue

Do not add:

1. promotion auto-selection
2. promotion campaign batching
3. per-blocker aggregate analytics
4. trend/history snapshots for readiness

## 9. Error handling

Fail closed:

1. if a planned task is malformed, surface the existing eval failure rather than hiding it
2. if packet writing fails, exit non-zero and do not claim readiness output succeeded
3. if no tasks are ready, still write a valid readiness packet with `ready_count: 0`

## 10. Testing

Add tests for:

1. empty planned queue -> valid zero-count readiness packet
2. mixed eligible and blocked tasks -> deterministic ordering and counts
3. CLI command writes `.omo/workers/promotion/readiness.yaml` and `.md`
4. deterministic `--now` support
5. worker docs mention the new readiness surface

## 11. Rollout

1. land helper + tests
2. land CLI + docs + deterministic `--now`
3. materialize readiness from the live queue
4. run canonical `.omo` verification

## 12. Success criteria

This slice is done when:

1. one command regenerates a canonical readiness packet for all planned tasks
2. operators can see current promotable tasks without repeated one-by-one evals
3. deterministic refresh is available for clean verification
4. `.omo` regression coverage protects the new surface and docs
