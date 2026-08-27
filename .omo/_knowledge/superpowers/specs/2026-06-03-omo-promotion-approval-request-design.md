---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# OMO promotion approval request workflow design

Date: 2026-06-03
Status: approved-by-user-default execution mode (user explicitly waived intermediate review gates and requested direct spec/plan/execution)
Scope: add a task-side request workflow that creates task-specific requested promotion approval artifacts and governance proposals for planned packets requiring human approval

## 1. Context

Promotion approval semantics are now strict:

1. `human_approval_required: true` planned packets cannot become promotion-ready from shared backlog-presence notes alone
2. `approval_ref` must point to a task-specific promotion approval YAML
3. readiness now reports `approval_invalid` for high-risk future packets that only have the shared markdown note

That closed the safety gap, but it left the next workflow gap open:

> how does an operator create the task-specific approval artifact that the stricter gate now requires?

Today there is a template:

1. `.omo/workers/templates/worker-promotion-approval.yaml`

and there is a validator:

1. `scripts/omo_promotion_approval.py`

But there is no operator command that:

1. creates the requested approval record
2. points the task at that record
3. creates the governance proposal that a human can later approve/apply

So the system currently knows how to *consume* promotion approval, but not how to *request* it.

## 2. Why this slice now

After tightening approval semantics, there are two plausible next steps:

1. enrich reporting/analytics around `approval_invalid`
2. create the workflow that can resolve `approval_invalid`

The second is more important because the system now intentionally blocks future human-approved packets until they have task-specific approval evidence. The next smallest correct step is to create that evidence-request path.

## 3. Goals

This design should:

1. create one explicit request command for promotion approval
2. emit immutable requested approval YAML under `.omo/workers/runs/`
3. update the planned task’s `approval_ref` to point at the new requested artifact
4. create one governance proposal that can later flip the request to granted
5. stay narrow enough for one implementation plan

## 4. Non-goals

This design does not:

1. auto-grant promotion approval
2. create a human review UI
3. redesign `propose_truth_mutation(...)`
4. add promotion dispatch/execution behavior
5. bulk-request approval for multiple tasks at once

## 5. Approaches considered

### A. Keep the workflow manual

Behavior:

1. operators hand-copy the YAML template
2. operators patch `approval_ref` manually
3. operators hand-author the truth-mutation proposal

Pros:

- no code change
- flexible for power users

Cons:

- too easy to make inconsistent artifacts
- repeats the same bookkeeping by hand
- undermines the stricter safety contract with ad hoc operator work

This approach is rejected.

### B. Recommended: add one explicit request command

Behavior:

1. create one task-specific requested approval record
2. update the planned task to point at it
3. create one governance proposal targeting the approval record

Pros:

- smallest workflow that resolves the newly introduced `approval_invalid` state
- keeps approval evidence immutable and proposal-driven
- follows the existing admission approval pattern

Cons:

- still needs a later human approve/apply step outside this slice
- adds one more task-side command to `omo_worker.py`

### C. Add a direct grant command

Behavior:

1. create the approval record already in `granted` state

Pros:

- shortest path from invalid to ready

Cons:

- bypasses the governance proposal chain
- collapses request and release into one operation
- too permissive for the control-plane conventions already used elsewhere

This approach is rejected.

## 6. Recommended design

Use **Approach B**.

The core decision is:

> add `task promotion-request-approval <TASK_ID> --requested-by <ACTOR> --now <ISO8601> --omo-dir .omo`, which writes a task-specific requested approval YAML, updates the task’s `approval_ref`, and creates a governance proposal that targets that YAML.

This keeps the promotion path consistent with the existing control-plane model:

1. operator requests
2. immutable record is written
3. human governance approves/applies later
4. promotion gate starts accepting the artifact only after it becomes `granted`

## 7. Workflow contract

### 7.1 CLI surface

Add one new task-side command:

1. `python3 scripts/omo_worker.py task promotion-request-approval <TASK_ID> --requested-by <ACTOR> --now <ISO8601> --omo-dir .omo`

The command should be deterministic through required `--now`, just like `promote-apply`.

### 7.2 Input requirements

The command should fail closed unless all of the following are true:

1. the task exists under `.omo/tasks/planned/`
2. `human_approval_required: true`
3. task status is still `candidate` or `pending`
4. the current `approval_ref` is missing or points to a non-task-specific baseline note

It should reject tasks that:

1. do not require human approval
2. are already pointing at a task-specific promotion approval YAML
3. are no longer in planned

## 8. Artifact contract

### 8.1 Approval record path

Write the requested record to:

1. `.omo/workers/runs/<TASK_ID>-promotion-approval-<STAMP>.yaml`

### 8.2 Approval record contents

The command should write a packet like:

```yaml
version: 1
approval_id: "P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z"
task_id: "P19-W3-ARCHIVE-TS"
approval_status: "requested"
requested_operation_level: "L2"
approval_scope: "task.promote_apply"
requested_at: "2026-06-03T00:00:00Z"
approved_at: null
expires_at: null
approver: null
refs:
  task_ref: ".omo/tasks/planned/P19-W3-ARCHIVE-TS.yaml"
  readiness_ref: ".omo/workers/promotion/readiness.yaml"
evidence:
  request_evidence: []
  approval_evidence: []
```

### 8.3 Task mutation

After writing the record, update the planned task’s `approval_ref` to point at it.

This is important because:

1. the task packet is the canonical place the promotion gate reads from
2. readiness must immediately stop reading the shared baseline note for that task

## 9. Governance proposal contract

The command should also create:

1. `.omo/_truth/task-center/proposals/<APPROVAL_ID>-proposal.yaml`

using `propose_truth_mutation(...)`.

The proposal should:

1. target the new approval YAML
2. request `approval_status: granted`
3. record `requested_by`
4. include a verification plan built around `task promote-eval` and/or `task promotion-readiness`

This mirrors the existing admission approval request pattern.

## 10. Interaction with the stricter promotion gate

Immediately after request creation:

1. the task’s `approval_ref` becomes task-specific
2. the gate still reads `approval_status: requested`
3. so readiness should continue to show `approval_invalid` until governance actually grants the proposal

This is intentional:

1. request creation is not release
2. the stricter gate should remain fail-closed until approval becomes granted

## 11. Error handling

Fail closed:

1. if the task already has a task-specific promotion approval YAML -> reject duplicate request
2. if writing the approval record fails -> do not update the task
3. if writing the task update fails -> do not claim proposal creation succeeded
4. if proposal creation fails -> leave the approval YAML and task ref in place only if both were already written successfully, and surface the failure explicitly

No silent fallback to the shared backlog note.

## 12. Testing

Add tests for:

1. command rejects non-human-approval tasks
2. command writes requested approval YAML + updates task `approval_ref` + creates proposal
3. duplicate task-specific request is rejected
4. readiness continues to show `approval_invalid` while the approval record is still `requested`
5. docs mention the request command and its relation to task-specific promotion approval

## 13. Rollout

1. land a pure helper that builds the requested record and proposal payload
2. add the CLI command in `omo_worker.py`
3. update docs and readiness regressions
4. run deterministic `.omo` verification

## 14. Success criteria

This slice is done when:

1. operators can request promotion approval without manual YAML authoring
2. planned tasks now point at task-specific requested approval artifacts
3. governance proposals are emitted automatically for later human release
4. readiness stays fail-closed until those proposals are actually granted/applied
