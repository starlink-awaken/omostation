---
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-09-03
last_updated: 2026-09-03
bet_id: BET-Y1Q4-T1-09
risk_level: L2
human_gate: true
value_indicator_policy: false
source_design_sha256: cbdee89004d0156e262daa63a1c38cfd660c0d5efbf0fce1a8eec8a92027c30b
source_proposal_sha256: 26bd1b3df552e693f2ac2684df255436522ff816d7844459523fafe130587100
source_amendment_sha256: 5b1bb03274d8f7383b67f88953cf0c7074a571a9a1d5aebb1ab68bb234042409
implementation_authorized: false
---

# W0 Portfolio v2 Dogfood Canary Design

## 1. Decision

Close W0 only after one value-exempt mechanism BET traverses the full new
portfolio chain and every required negative case fails closed. This canary
does not create or start W1-W6.

## 2. Canonical chain

```text
Vision pointer
→ Objective/KR
→ Campaign/Milestone
→ child BET
→ accepted Spec
→ WorkPacket
→ WorkflowRun
→ verify/closeout
→ completion matrix
→ retro
→ KR evidence
→ Milestone derived=met
→ Cockpit/CLI digest parity
```

The canary is infrastructure evidence. Its value axis remains NOT_PROVEN and
it cannot advance a personal-value KR.

## 3. Negative cases

The gate must fail after independently removing or corrupting each of:

- Objective/KR binding;
- required BET coverage;
- accepted Spec digest;
- WorkPacket identity;
- WorkflowRun binding;
- verification evidence;
- completion-axis derivation;
- retro;
- projection source digest;
- required human final verdict at Vision scope.

Fixtures are isolated and never mutate production Ledger, Goals, OMO runtime,
or outcome evidence.

## 4. Prospective write surfaces

- a dedicated value-exempt canary fixture and structured report selected in
  writing-plans
- W0 parent/child retros
- `docs/plans/3y-bet-ledger.yaml`, limited to separately authorized W0
  completion transitions
- this Spec and its future implementation plan/retro

No W1-W6 BET or value sample is in scope.

## 5. Required verification

1. The positive chain passes at an immutable tree.
2. Every negative mutation produces its typed failure.
3. CLI and Cockpit projection digests match.
4. The canary creates no personal decision outcome.
5. Parent close is blocked until every implementation child is terminal and
   all W0 Milestones are derived as met.
6. Required checks, post-merge exact-SHA replay, and clone cleanup succeed.

## 6. Error and rollback contract

Any false positive, mutable-ref dependency, projection inference, negative
case passing, or value-axis change halts W0 closeout. Rollback removes only
the canary delivery and never deletes durable governance evidence.

## 7. Authority boundary

This accepted Spec establishes binding identity only. It does not authorize
writing-plans, canary implementation, completion transitions, W1-W6, runtime
mutation, or value evidence. Writing-plans requires a separate post-binding
authorization.

## 8. 验收标准

| ID | assertion | evidence_type | verifier |
|---|---|---|---|
| AC-T1-09-01 | One value-exempt mechanism BET traverses the complete immutable portfolio chain | canary_report | W0 dogfood report |
| AC-T1-09-02 | Every listed identity/evidence/projection corruption fails with its typed error | negative_test | canary mutation matrix |
| AC-T1-09-03 | CLI and Cockpit consume the same source digest | integration_test | cross-entry digest assertion |
| AC-T1-09-04 | Canary creates no personal decision outcome or value promotion | evidence_partition_report | outcome/value before-after comparison |
| AC-T1-09-05 | Parent close is blocked until every child and all four Milestones pass | derived_gate | parent closeout negative/positive pair |
| AC-T1-09-06 | Required CI, exact-SHA replay and canonical clone cleanup succeed | delivery_receipt | GitHub and lifecycle receipts |

## 9. 反指标

- A single positive path without the complete negative matrix.
- PR, CI, worker completion or static digest used as live canary proof.
- Number of assertions or generated reports.
- Any synthetic/personal-value sample created for the mechanism canary.
- Parent status advanced while Product Milestone or another child is absent.

## 10. Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|---|---|---|
| 1 | static proof vs full dogfood chain | full chain | 防止引擎存在但旅程断裂 |
| 2 | positive-only vs mutation matrix | positive + all negatives | 防止 false-green |
| 3 | product outcome vs value-exempt canary | value-exempt | 治理机制不冒充个人价值 |
| 4 | mutable branch vs immutable tree | immutable tree | 保证可重复验证 |
| 5 | partial child close vs four-Milestone gate | all children + four Milestones | Product child不可遗漏 |
| 6 | canary service/database/dispatcher vs existing Ledger/Workflow/Cockpit chain | reuse canonical chain | 不增加第二真值或执行面 |
| 7 | Agent close vs principal final verdict | human final verdict required | canary 不能自行宣告愿景完成 |
