---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# OMO promotion approval semantics design

Date: 2026-06-03
Status: approved-by-user-default execution mode (user explicitly waived intermediate review gates and requested direct spec/plan/execution)
Scope: tighten promotion eligibility so `human_approval_required: true` planned packets cannot become promotion-ready from backlog-presence approval refs alone

## 1. Context

OMO promotion now has four relevant surfaces:

1. `task promote-eval`
2. `task promote-apply`
3. `task promotion-history`
4. `task promotion-readiness`

The readiness slice made one governance blind spot explicit:

1. current Phase 17 packets are promotable now
2. deeper future packets are blocked today mostly by `phase_mismatch`
3. several future `human_approval_required: true` packets already have `approval_ref`
4. those refs point to `.omo/workers/runs/future-active-l2l3-pending-approval-2026-06-02.md`

That shared baseline note says:

1. it exists for **planning backlog presence only**
2. it **does not authorize execution or dispatch by itself**

Current promotion evaluation is still too weak for that reality:

```python
"approval_ready": (not task.get("human_approval_required")) or bool(task.get("approval_ref"))
```

That means once the phase gate advances, a `human_approval_required` task could become promotion-eligible on the strength of a shared non-execution baseline note. That is the wrong safety contract.

## 2. Why this slice now

After readiness landed, there are two plausible next directions:

1. richer analytics on top of `readiness.yaml`
2. tighten the approval semantics that readiness exposed

The second is more urgent because the current system can already describe the queue correctly, but it would evaluate some future high-risk packets incorrectly once their phase gate opens.

So the next smallest correct step is:

> make promotion approval semantics explicit before phase progression turns a shared baseline note into an accidental release token.

## 3. Goals

This design should:

1. distinguish backlog-presence approval from task-specific promotion approval
2. keep `human_approval_required: false` promotion behavior unchanged
3. tighten `promote-eval`, `promote-apply`, and `promotion-readiness` together through the same gate logic
4. use immutable approval artifacts, not inline task booleans
5. stay narrow enough for one implementation plan

## 4. Non-goals

This design does not:

1. add a full approval request workflow UI
2. redesign worker dispatch approval
3. auto-generate promotion approvals
4. change promotion history semantics
5. promote or dispatch any real packet automatically

## 5. Approaches considered

### A. Keep the current boolean `approval_ref` rule and document caution

Behavior:

1. leave promotion logic unchanged
2. rely on operators to remember that some approval refs are only advisory

Pros:

- no code change
- minimal immediate work

Cons:

- unsafe by construction
- keeps a known governance ambiguity in the core gate
- makes readiness surfaces misleading for future high-risk packets

This approach is rejected.

### B. Recommended: require a task-specific structured promotion approval artifact

Behavior:

1. treat backlog-presence notes as insufficient for `human_approval_required` promotion
2. require `approval_ref` to resolve to a structured immutable approval YAML with the right scope and task identity
3. let promotion evaluation fail closed when the ref is missing, mismatched, or the scope is not promotion

Pros:

- converts an implicit social rule into a machine-checkable gate
- keeps approval evidence immutable and auditable
- fixes `promote-eval`, `promote-apply`, and readiness in one place

Cons:

- adds one new artifact contract
- deeper human-approved packets will remain blocked until proper approval records exist

### C. Add inline task fields such as `promotion_approved: true`

Behavior:

1. put promotion approval state directly into the task YAML

Pros:

- easy to implement

Cons:

- approval evidence becomes mutable task state instead of immutable artifact
- duplicates approval facts inside the task packet
- loses auditable scope/reviewer context

This approach is rejected.

## 6. Recommended design

Use **Approach B**.

The core decision is:

> for `human_approval_required: true` planned packets, `approval_ref` only counts as promotion-ready if it points to a task-specific structured approval record whose scope explicitly authorizes `task.promote_apply`.

This keeps the promotion contract aligned with the shared baseline note:

1. backlog presence can still be documented
2. actual promotion release must be explicit, task-specific, and immutable

## 7. Approval artifact contract

### 7.1 Add a dedicated promotion approval template

Create:

1. `.omo/workers/templates/worker-promotion-approval.yaml`

Do **not** overload `worker-approval-record.yaml` directly. That template is dispatch-oriented and assumes an active task / dispatch context. Promotion approval happens while the task is still in `tasks/planned/`.

### 7.2 Canonical promotion approval YAML

The task-specific approval record should look like:

```yaml
version: 1
approval_id: "P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z"
task_id: "P19-W3-ARCHIVE-TS"
approval_status: "granted"
requested_operation_level: "L2"
approval_scope: "task.promote_apply"
requested_at: "2026-06-03T00:00:00Z"
approved_at: "2026-06-03T00:05:00Z"
expires_at: null
approver: "human"
refs:
  task_ref: ".omo/tasks/planned/P19-W3-ARCHIVE-TS.yaml"
  readiness_ref: ".omo/workers/promotion/readiness.yaml"
evidence:
  request_evidence: []
  approval_evidence: []
```

Rules:

1. `task_id` must match the planned packet being evaluated
2. `approval_status` must be `granted`
3. `approval_scope` must be exactly `task.promote_apply`
4. `refs.task_ref` must point at the planned task packet
5. Markdown notes like `future-active-l2l3-pending-approval-2026-06-02.md` do not satisfy this contract

### 7.3 Artifact location

Store immutable promotion approval records under:

1. `.omo/workers/runs/<TASK_ID>-promotion-approval-<STAMP>.yaml`

That keeps them adjacent to promotion evidence and other operator-created run artifacts.

## 8. Promotion gate changes

### 8.1 Tighten `approval_ready`

For `human_approval_required: false`:

1. behavior stays unchanged
2. `approval_ready` remains `true`

For `human_approval_required: true`:

1. `approval_ref` missing -> blocker `approval_missing`
2. `approval_ref` present but not a valid promotion approval record -> blocker `approval_invalid`
3. valid structured promotion approval record -> `approval_ready: true`

### 8.2 Centralize the check

Do not implement separate approval semantics in each CLI branch.

Instead:

1. add one promotion approval evaluator helper
2. call it only from `_promotion_eval(...)`
3. let `promote-apply` and `promotion-readiness` inherit the stricter gate automatically

### 8.3 Readiness surface impact

`promotion-readiness` should continue to report the same task list, but future human-approved packets with only the shared baseline note should now show:

1. `eligible: false`
2. `blockers: ["phase_mismatch", "approval_invalid"]` today when both apply
3. `blockers: ["approval_invalid"]` once the phase gate opens but task-specific approval is still absent

That makes readiness more truthful instead of merely phase-aware.

## 9. Error handling

Fail closed:

1. unreadable or malformed approval YAML -> `approval_invalid`
2. mismatched `task_id` -> `approval_invalid`
3. wrong `approval_scope` -> `approval_invalid`
4. wrong `approval_status` -> `approval_invalid`

Do not silently downgrade malformed approvals into “probably okay”.

## 10. Testing

Add tests for:

1. `human_approval_required: true` + no `approval_ref` -> `approval_missing`
2. `human_approval_required: true` + shared backlog-presence markdown ref -> `approval_invalid`
3. valid task-specific promotion approval YAML -> eligible when other checks pass
4. readiness surface reports `approval_invalid` for future human-approved packets using the shared baseline note
5. docs explain the new distinction between backlog-presence approval and promotion approval

## 11. Rollout

1. land the approval evaluator helper + unit tests
2. tighten `_promotion_eval(...)`
3. update readiness/docs regressions
4. keep current queue data unchanged; only the interpretation changes
5. run canonical `.omo` verification

## 12. Success criteria

This slice is done when:

1. human-approved planned packets cannot become promotion-ready from backlog-presence notes alone
2. `promote-eval`, `promote-apply`, and `promotion-readiness` all agree on the stricter rule
3. readiness surfaces explicitly show `approval_invalid` where appropriate
4. the approval evidence required for future promotion is explicit and immutable
