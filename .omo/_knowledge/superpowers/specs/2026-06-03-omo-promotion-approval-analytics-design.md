# OMO promotion approval analytics / rollup design

Date: 2026-06-03
Status: approved-by-user-default execution mode (user unavailable; continue with the previously established default of direct spec/plan execution)
Scope: add a canonical promotion approval analytics / rollup surface on top of the existing approval current/history/readiness surfaces so operators can see actionable queues, blocker distributions, and stale approval pressure without reading raw artifacts

## 1. Context

Promotion approval now has two canonical read-side surfaces:

1. current closure/status: `.omo/workers/promotion/approvals/current.yaml`
2. history/index: `.omo/workers/promotion/approvals/history/current.yaml`

Together they answer:

1. what approval-bearing tasks currently exist?
2. what is each task’s approval/proposal state?
3. what approval artifacts have been created over time?

But there is still no higher-level operator analytics surface that answers:

1. what needs action right now?
2. which blockers dominate the approval queue?
3. how many approvals are stalled at `proposed` vs `approved` vs `granted`?
4. which requests are becoming stale by age?

Those questions should not require:

1. manually reading both current and history packets
2. scanning raw `workers/runs/*-promotion-approval-*.yaml`
3. reconstructing urgency by hand

## 2. Why this slice now

After approval history landed, there are three plausible follow-ups:

1. jump straight to snapshot-based diff/trend reporting
2. add a bounded approval analytics / rollup surface on top of current/history/readiness
3. stop and leave operators with current + history only

The second is the smallest correct next step because:

1. current/history are now stable inputs
2. operators still lack one canonical “what do I do next?” surface
3. snapshot/diff semantics can come later, but should build on a rollup layer first

## 3. Goals

This slice should:

1. provide one canonical approval analytics packet derived from existing promotion surfaces
2. summarize action queues for `approve`, `apply`, and `re-check readiness`
3. expose blocker distributions across approval-bearing tasks
4. classify request age so stale approvals become obvious
5. stay read-only and consume canonical surfaces rather than raw artifacts whenever possible

## 4. Non-goals

This slice does not:

1. add new mutation commands
2. redesign approval/history/current packet schemas
3. persist immutable time-series snapshots
4. implement promotion approval trend charts
5. change readiness or governance semantics

## 5. Approaches considered

### A. Recommended: add approval analytics / rollup current surface

Behavior:

1. read `approvals/current.yaml`
2. read `approvals/history/current.yaml`
3. read `promotion/readiness.yaml` for blocker alignment
4. write one analytics packet under `.omo/workers/promotion/approvals/analytics/`

Pros:

- builds only on canonical read surfaces
- makes the next operator action explicit
- bounded enough to implement/test in one slice

Cons:

- adds one more generated surface
- does not yet provide cross-refresh trend deltas

### B. Jump straight to diff / trend reporting

Behavior:

1. compare one refresh to another
2. expose queue movement and deltas over time

Pros:

- higher long-term insight ceiling

Cons:

- no stable analytics baseline yet
- needs snapshot/version semantics that do not exist today
- larger scope than needed for the current gap

This approach is rejected for now.

### C. Leave analytics implicit in current/history

Behavior:

1. operators read `approvals/current.yaml`
2. operators manually infer action queues and staleness

Pros:

- zero new code

Cons:

- repeat manual reasoning every time
- no canonical blocker histogram or age buckets
- weak foundation for future diff/trend work

This approach is rejected.

## 6. Recommended design

Use **Approach A**.

The core decision is:

> add `task promotion-approval-analytics --omo-dir .omo [--now <ISO8601>]`, which derives one analytics / rollup packet from canonical approval current/history/readiness surfaces and writes operator-facing outputs under `.omo/workers/promotion/approvals/analytics/`.

The analytics layer should answer three operator questions in one place:

1. **what needs action now?**
2. **where is the queue getting stuck?**
3. **which requests are aging into attention?**

## 7. Data source contract

The analytics helper should derive from:

1. `.omo/workers/promotion/approvals/current.yaml`
2. `.omo/workers/promotion/approvals/history/current.yaml`
3. `.omo/workers/promotion/readiness.yaml`

Readiness is included because:

1. `approvals/current.yaml` already carries `blockers`
2. `promotion/readiness.yaml` remains the canonical gate-wide source
3. the analytics layer should align its blocker histogram with readiness rather than inventing a parallel notion

Raw approval artifacts should not be the primary input for this slice.

## 8. Analytics packet contract

Write:

1. `.omo/workers/promotion/approvals/analytics/current.yaml`
2. `.omo/workers/promotion/approvals/analytics/current.md`

The YAML packet should include:

1. `generated_at`
2. `approval_task_count`
3. `history_approval_count`
4. `requested_count`
5. `approved_pending_apply_count`
6. `granted_count`
7. `missing_proposal_count`
8. `eligible_after_approval_count`
9. `blocked_after_approval_count`
10. `action_queues`
11. `blocker_histogram`
12. `proposal_status_histogram`
13. `approval_age_buckets`
14. ordered `tasks[]`

### 8.1 Action queues

`action_queues` should expose:

1. `approve_now[]` — approval-bearing tasks where proposal is `proposed`
2. `apply_now[]` — approval-bearing tasks where proposal is `approved`
3. `check_readiness[]` — approval-bearing tasks already `granted`, where approval blocker is gone but other blockers may remain

Each queue entry should minimally include:

1. `task_id`
2. `approval_id`
3. `proposal_id`
4. `blockers`

### 8.2 Blocker histogram

`blocker_histogram` should count blocker occurrences across approval-bearing tasks, for example:

1. `phase_mismatch`
2. `approval_invalid`
3. any future readiness blocker names already emitted by the promotion gate

### 8.3 Proposal status histogram

`proposal_status_histogram` should count:

1. `proposed`
2. `approved`
3. `verified`
4. `missing`
5. `invalid`

### 8.4 Approval age buckets

Age should be based on `requested_at` relative to `generated_at`.

Keep it intentionally simple:

1. `lt_1d`
2. `d1_to_d3`
3. `d3_plus`

Only open requests (`approval_status: requested`) should contribute to age buckets. Granted items should not count as stale open approvals.

## 9. Task ordering

`tasks[]` should be ordered for operator usefulness:

1. open requests needing action first (`proposed`, then `approved`)
2. then granted items
3. within each class, older open requests first
4. final tie-break by `task_id`

Each analytics task entry should include:

1. `task_id`
2. `approval_id`
3. `approval_status`
4. `proposal_status`
5. `requested_at`
6. `task_age_bucket`
7. `eligible`
8. `blockers`
9. `next_action`

`next_action` should be one of:

1. `approve`
2. `apply`
3. `check_readiness`
4. `none`

## 10. Markdown contract

Markdown should make queue state obvious at a glance:

1. headline counts
2. action queue summary
3. blocker histogram
4. age bucket summary
5. one section per task with `next_action`

The tone should remain operator-facing and terse, similar to the existing promotion surfaces.

## 11. Error handling

Fail closed on missing canonical inputs:

1. missing `approvals/current.yaml` should raise a clear error
2. missing `approvals/history/current.yaml` should raise a clear error
3. missing `promotion/readiness.yaml` should raise a clear error

Do not silently rebuild those surfaces inside this helper. Operators should run the upstream surfaces explicitly.

For malformed canonical input:

1. raise explicit field-level errors
2. do not silently coerce unknown status values into success-shaped defaults

## 12. Testing

Add tests for:

1. analytics packet over empty approval data
2. action queue classification (`approve`, `apply`, `check_readiness`)
3. blocker histogram aggregation
4. age bucket classification from `requested_at`
5. CLI writes `analytics/current.yaml` + `.md`
6. docs mention the new analytics surface

## 13. Rollout

1. add pure helper `scripts/omo_promotion_approval_analytics.py`
2. add `task promotion-approval-analytics`
3. update docs/tests
4. hydrate live `analytics/current.*` from the current promotion approval surfaces
5. run promotion-focused verification

## 14. Future follow-up

Once this rollup layer exists, future slices can stay narrower:

1. approval diff between refreshes
2. trend/burndown surfaces
3. SLA or escalation policies for stale requests

Those should build on analytics/current rather than re-reading raw approval artifacts.
