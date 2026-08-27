---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# OMO promotion approval history / index design

Date: 2026-06-03
Status: approved-by-user-default execution mode (user unavailable; continue with the previously established default of direct spec/plan/execution)
Scope: add a canonical promotion approval history/index surface that scans task-specific promotion approval artifacts and proposal state into one operator-facing history packet

## 1. Context

Promotion now has three canonical current-state surfaces:

1. promotion history: `.omo/workers/promotion/current.yaml`
2. promotion readiness: `.omo/workers/promotion/readiness.yaml`
3. promotion approval closure/status: `.omo/workers/promotion/approvals/current.yaml`

The remaining gap is on the approval side:

> there is still no canonical history/index surface for promotion approval artifacts themselves.

Operators can inspect a single current closure state, but they cannot yet answer:

1. how many promotion approval requests have ever been created?
2. which one is the latest?
3. which approval items are still requested, already approved, or fully verified?
4. what proposal status corresponds to each approval item?

Those facts are currently implicit in raw files under:

1. `.omo/workers/runs/*-promotion-approval-*.yaml`
2. `.omo/_truth/task-center/proposals/*-promotion-approval-*-proposal.yaml`

## 2. Why this slice now

After the approval closure slice, there are two plausible next moves:

1. jump straight to approval rollup/diff/trend analytics
2. first build a canonical approval history/index surface

The second is smaller and safer because:

1. analytics should not read raw filesystem folklore directly
2. promotion already followed this pattern on the promotion-envelope side (`current.yaml` first, then richer layers later)
3. an index/history surface is the missing stable input for any later diff/rollup work

## 3. Goals

This slice should:

1. expose all promotion approval artifacts in one canonical surface
2. include both approval status and proposal status per artifact
3. provide stable ordering and summary counts
4. ignore non-approval run artifacts
5. stay read-only; no mutation semantics in this slice

## 4. Non-goals

This slice does not:

1. add new approve/apply commands
2. change current closure surface semantics
3. create cross-run diff/trend analytics
4. snapshot immutable per-refresh runs
5. redesign approval YAML or proposal YAML schemas

## 5. Approaches considered

### A. Read raw files ad hoc whenever needed

Behavior:

1. operators glob `workers/runs/*-promotion-approval-*.yaml`
2. manually open matching proposals

Pros:

- no code change

Cons:

- no canonical source
- repeats parsing logic by hand
- unsafe foundation for later analytics

This approach is rejected.

### B. Recommended: add approval history/index current surface

Behavior:

1. scan all task-specific promotion approval YAML artifacts
2. derive linked proposal state
3. write one current history/index packet under `workers/promotion/approvals/history/`

Pros:

- smallest canonical read-side surface
- directly reusable by later rollup/diff
- mirrors existing promotion history pattern

Cons:

- one more generated surface to maintain
- does not yet answer trend questions across snapshots

### C. Jump straight to approval analytics

Behavior:

1. compute counts/trends directly from raw approval/proposal files

Pros:

- more immediately “insightful”

Cons:

- skips the stable index layer
- couples analytics to raw storage layout
- harder to validate incrementally

This approach is rejected for now.

## 6. Recommended design

Use **Approach B**.

The core decision is:

> add `task promotion-approval-history --omo-dir .omo [--now <ISO8601>]`, which scans all task-specific promotion approval artifacts and writes canonical history/index surfaces under `.omo/workers/promotion/approvals/history/`.

This keeps the approval line consistent with the rest of promotion:

1. raw run artifacts remain the durable source
2. current/history surfaces are the canonical operator view
3. richer analytics can layer on top later

## 7. Workflow contract

### 7.1 CLI surface

Add one new task-side command:

1. `python3 scripts/omo_worker.py task promotion-approval-history --omo-dir .omo [--now <ISO8601>]`

Behavior:

1. scan `.omo/workers/runs/*-promotion-approval-*.yaml`
2. ignore non-approval run artifacts
3. derive linked proposal state from `.omo/_truth/task-center/proposals/<APPROVAL_ID>-proposal.yaml`
4. write canonical current surfaces

### 7.2 Entry schema

Each history entry should include:

1. `approval_id`
2. `approval_ref`
3. `task_id`
4. `task_ref`
5. `requested_at`
6. `approval_status`
7. `proposal_id`
8. `proposal_ref`
9. `proposal_status`
10. `approver`
11. `approved_at`
12. `applied_at`
13. `readiness_ref`

## 8. Ordering and summary rules

Ordering should be:

1. newest `requested_at` first
2. tie-break by `approval_id`

The YAML packet should include:

1. `generated_at`
2. `latest_approval_id`
3. `latest_approval_ref`
4. `prior_approval_id`
5. `prior_approval_ref`
6. `approval_count`
7. `requested_count`
8. `approved_pending_apply_count`
9. `granted_count`
10. ordered `approvals[]`

Derived count rules:

1. `requested_count` = approval YAML `requested` + proposal `proposed`
2. `approved_pending_apply_count` = approval YAML still `requested` + proposal `approved`
3. `granted_count` = approval YAML `granted`

## 9. Surface contract

Write:

1. `.omo/workers/promotion/approvals/history/current.yaml`
2. `.omo/workers/promotion/approvals/history/current.md`

Markdown should summarize:

1. latest approval
2. prior approval
3. total approval items
4. one section per approval artifact showing task id, approval status, proposal status, and task ref

## 10. Error handling

Fail closed:

1. missing required approval fields should raise a clear error in the helper
2. missing proposal YAML should not drop the entry; render `proposal_status: missing`
3. malformed proposal YAML should surface as `proposal_status: invalid`
4. non-approval run artifacts must be ignored rather than causing parse failures

## 11. Testing

Add tests for:

1. empty history returns zero-count packet
2. entries sort newest-first by `requested_at`
3. missing required approval fields raise explicit errors
4. missing proposal YAML still keeps the entry with `proposal_status: missing`
5. CLI writes `history/current.yaml` + `.md`
6. docs mention the new approval history/index surface

## 12. Rollout

1. add pure helper for history packet building
2. add `task promotion-approval-history`
3. update docs/tests
4. hydrate live `history/current.*` from the existing `P19-W3-ARCHIVE-TS` approval artifact
5. run promotion-focused verification
