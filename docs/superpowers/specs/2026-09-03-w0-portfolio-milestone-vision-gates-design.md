---
schema_version: specification/v1
spec_version: 1.0.1
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-09-03
last-reviewed: 2026-09-03
bet_id: BET-Y1Q4-T1-06
risk_level: L2
human_gate: false
value_indicator_policy: false
source_design_sha256: cbdee89004d0156e262daa63a1c38cfd660c0d5efbf0fce1a8eec8a92027c30b
source_proposal_sha256: 26bd1b3df552e693f2ac2684df255436522ff816d7844459523fafe130587100
source_amendment_sha256: 5b1bb03274d8f7383b67f88953cf0c7074a571a9a1d5aebb1ab68bb234042409
implementation_authorized: true
---

# W0 Portfolio Milestone and Vision Gates Design

## 1. Decision

### Implementation authorization (1.0.1)

Principal session authorization 2026-09-04 (safer Wave order after self-binding #3085 and T1-07 #3087) authorizes read-only Milestone/Vision predicate implementation. No agent may write completion/value state.


Extend the existing chain-bind mechanism with pure, derived predicates for
BET, Milestone, Campaign, Objective, and Vision completion. Higher-level
status is never advanced merely because leaf activities are done.

## 2. Completion hierarchy

BET completion requires verified done conditions, verification commands,
closed workflow identity, matching retro, scope compliance, no P0 guardrail
breach, and a valid completion-axis derivation.

Milestone completion requires every mandatory BET to be done or replaced,
every required KR to be proven, zero unresolved blocker, and zero P0 breach.

Vision completion additionally requires all required Objectives/Campaigns,
twelve consecutive real-value weeks, weekly accepted outputs and acceptance
rate thresholds, edit-burden improvement, real-signal-only evidence, and the
human principal's final verdict.

## 3. Value firewall

- `value_indicator_policy=false` BETs may reach `delivery_accepted` but cannot
  advance value KRs.
- PRs, CI, tests, worker completion, synthetic samples, or transport receipts
  cannot substitute for a principal-bound decision outcome.
- KR `proven` is validator-derived from canonical evidence; no Agent or
  projection writes it directly.

## 4. Prospective write surfaces

- `bin/plan/chain_bind.py`
- `bin/plan/chain-bind-check.py`
- `bin/plan/bet-ledger.py`
- `tests/test_chain_bind.py`
- `tests/test_bet_portfolio_completion.py`
- this Spec and its future implementation plan/retro

## 5. Required verification

1. All leaf BETs done with one required KR unproven must fail Milestone close.
2. A value-exempt delivery cannot advance a value KR.
3. A failed BET with a valid completed replacement can conserve coverage.
4. An eleven-week window must fail the twelve-week Vision gate.
5. Synthetic or unbound human evidence must fail the value gate.
6. Missing human final verdict must fail Vision close.
7. Existing start/closeout/retro fixtures remain compatible.

## 6. Error and rollback contract

False close returns `MILESTONE_FALSE_CLOSE`; an incomplete observation window
returns `VISION_WINDOW_INCOMPLETE`; proxy evidence returns
`VALUE_PROXY_REJECTED`. All errors are read-only decisions and do not mutate
BET, KR, workflow, or evidence state.

Rollback removes the new higher-level gate while retaining current BET-level
chain-bind behavior and all recorded evidence.

## 7. Authority boundary

This accepted Spec establishes binding identity only. It does not authorize
writing-plans, gate implementation, completion transitions, value evidence,
W1-W6, or runtime operations. Writing-plans requires a separate post-binding
authorization.

## 8. 验收标准

| ID | assertion | evidence_type | verifier |
|---|---|---|---|
| AC-T1-06-01 | Leaf BET completion cannot close an unproven KR or Milestone | negative_test | false-close fixture |
| AC-T1-06-02 | Value-exempt delivery cannot advance a value KR | negative_test | value-firewall fixture |
| AC-T1-06-03 | Completed replacement can conserve required coverage | unit_test | replacement completion fixture |
| AC-T1-06-04 | An incomplete twelve-week window cannot close Vision | boundary_test | eleven/twelve-week fixture pair |
| AC-T1-06-05 | Synthetic, unbound-human or proxy evidence is rejected | negative_test | evidence-partition fixtures |
| AC-T1-06-06 | Human final verdict is mandatory and existing chain-bind behavior remains compatible | regression_test | self-check plus final-verdict fixture |

## 9. 反指标

- Number of BETs or Milestones marked done.
- A high governance score without proven KR evidence.
- PR, CI, test or worker completion used as personal value.
- Shortening the observation window to reach Vision sooner.
- Silently converting unavailable evidence into zero or success.

## 10. Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|---|---|---|
| 1 | 手工高层状态 vs pure derived state | pure derived | 防止自报完成 |
| 2 | leaf done 推进 KR vs evidence-driven KR | evidence-driven | 任务完成不等于结果 |
| 3 | value-exempt 可计价值 vs firewall | 固定 NOT_PROVEN | 防止工程冒充价值 |
| 4 | 单点成功 vs continuous window | twelve-week window | 证明持续性 |
| 5 | Agent final close vs human verdict | human final verdict required | 保持个人主权 |
| 6 | 新 completion service/database/dispatcher vs existing chain-bind | extend pure validators | 复用 Ledger/chain-bind SSOT 与既有执行链 |
| 7 | 缺少窗口或证据时推断通过 vs typed halt | typed fail closed | unavailable 不等于 zero 或 success |
