---
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.1
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-09-03
last_updated: 2026-09-03
bet_id: BET-Y1Q4-T1-04
risk_level: L2
human_gate: true
value_indicator_policy: false
source_design_sha256: cbdee89004d0156e262daa63a1c38cfd660c0d5efbf0fce1a8eec8a92027c30b
source_proposal_sha256: 26bd1b3df552e693f2ac2684df255436522ff816d7844459523fafe130587100
source_amendment_sha256: 5b1bb03274d8f7383b67f88953cf0c7074a571a9a1d5aebb1ab68bb234042409
implementation_authorized: true
---

# W0 Portfolio v2 Schema and Compatibility Design

## 1. Decision

Extend the existing `3y-bet-ledger.yaml` contract additively so it can express
Vision, Objective, Key Result, Campaign, Milestone, parent/child ownership,
outcome coverage, hypotheses, gates, guardrails, and replacement semantics.
The existing Ledger remains the only machine-readable portfolio SSOT.

No service, database, dispatcher, workflow engine, event ledger, or second
truth plane is introduced.

## 2. Goal and hypothesis

If the Ledger can validate the full strategic hierarchy before execution, it
can detect an uncovered objective before many individually compliant BETs are
marked done.

The observed baseline has valid dependency mechanics but no structured
Objective/KR/Milestone/parent coverage. The target is full coverage for every
new or modified non-terminal v2 BET while preserving legacy reads.

## 3. Data contract

The additive top-level contract is:

```text
meta + vision + objectives + campaigns + milestones + bets
```

Existing `meta.total_bets` remains an integer derived from `len(bets)`.

Each new or modified v2 BET must declare:

- `campaign_ref`;
- `objective_refs`;
- `kr_refs`;
- `parent_bet` when it is a child;
- `bet_type`;
- `hypothesis`, baseline and target;
- leading/lagging indicators;
- entry gate, guardrails, kill criteria and replacement policy.

## 4. Compatibility boundary

- Existing v1 commands keep reading the `bets` list.
- Existing status values remain unchanged.
- Historical terminal BETs without v2 fields are grandfathered read-only.
- New or modified non-terminal BETs fail closed when required v2 fields are
  missing.
- The initial W0 `portfolio_binding.schema_state=bootstrap_unenforced`
  declaration is not enforcement evidence.
- After this contract is implemented, a separate self-binding amendment must
  move the eight W0 BETs to enforced v2 without changing status, dependencies,
  accepted bindings, completion axes, or value evidence.
- Repository-wide `meta.total_bets` equality follows a staged order:
  compatibility warning, focused strict-fixture RED/GREEN, one separately
  claimed `meta.total_bets` repair derived from `len(bets)`, then strict mode.

## 5. Prospective write surfaces

- `bin/plan/portfolio_contract.py`
- `bin/plan/bet-ledger.py`
- `tests/test_bet_portfolio_contract.py`
- this Spec and its future implementation plan/retro
- `docs/plans/3y-bet-ledger.yaml`, limited to this child, the separately
  authorized W0 self-binding amendment, and the separately claimed single
  field `meta.total_bets` repair

## 6. Required verification

1. The current full v1 Ledger parses without semantic mutation.
2. A valid v2 fixture passes.
3. Missing/duplicate Vision, Objective, KR, Campaign, Milestone, or BET IDs are
   rejected with typed errors.
4. Invalid references, metric shapes, enums, timestamps, and boolean policy
   fields are rejected.
5. Compatibility mode reports the legacy `meta.total_bets` mismatch without
   blocking v1 reads; strict fixtures reject inequality; full-Ledger strict
   mode is enabled only after the one-field repair.
6. Every existing BET object remains semantically equal before and after
   parser adoption.
7. No import-time or filesystem write side effect occurs during validation.

## 7. Error and rollback contract

- Invalid shape: `PORTFOLIO_SCHEMA_INVALID`, halt.
- Missing objective: `OBJECTIVE_REF_MISSING`, halt.
- Missing KR: `KR_REF_MISSING`, halt.
- Legacy terminal incompleteness: warning only; never fabricate evidence.
- Any need for a database, service, second dispatcher, destructive migration,
  or incompatible existing CLI behavior triggers the circuit breaker.

Rollback disables v2 enforcement and reuses the unchanged v1 reader. It does
not delete v2 data or rewrite historical evidence.

## 8. Authority boundary

Version 1.0.0 established binding identity only. The principal's continuing
BET-execution authorization recorded on 2026-09-03 now authorizes this
specific child implementation, subject to a fresh BET-bound workflow, exact
claims, independent review, required checks, and exact-SHA post-merge
verification.

This authorization is limited to the first implementation delivery described
by the approved plan: `bin/plan/portfolio_contract.py`,
`bin/plan/bet-ledger.py`, and `tests/test_bet_portfolio_contract.py`. It
permits a pure additive validator, a compatibility-only CLI command, and the
specified RED-to-GREEN and no-side-effect tests. A later execution run must
still preserve all existing BET objects semantically and must stop if it needs
a service, database, dispatcher, destructive migration, or v1-incompatible
behavior.

This authorization does not authorize Ledger self-binding, the one-field
`meta.total_bets` repair, strict full-Ledger enforcement, projections, runtime
operations, W1-W6, any other W0 child, status changes, completion/value
evidence, or a terminal transition. Each remains a separately claimed and
fresh-workflow boundary.

## 9. 验收标准

| ID | assertion | evidence_type | verifier |
|---|---|---|---|
| AC-T1-04-01 | Current v1 Ledger parses without changing any existing BET object | structured_report | immutable semantic comparison |
| AC-T1-04-02 | Valid v2 fixtures pass and invalid entity/reference/metric/policy shapes fail with typed errors | negative_test | `tests/test_bet_portfolio_contract.py` |
| AC-T1-04-03 | Compatibility mode reports legacy total drift while focused strict fixtures reject it | test_report | compatibility/strict fixture pair |
| AC-T1-04-04 | One separately claimed `meta.total_bets` repair changes no BET object | structured_report | before/after top-level and BET comparison |
| AC-T1-04-05 | Strict full-Ledger mode becomes green only after the one-field repair | gate_report | `bet-ledger.py portfolio lint --strict` |
| AC-T1-04-06 | Validation produces no import-time or filesystem write side effect | side_effect_report | isolated filesystem fingerprint |

## 10. 反指标

- Number of newly supported fields or schema lines.
- Number of legacy warnings suppressed.
- A parser returning exit zero without negative fixtures.
- Updating `meta.total_bets` by hand to a convenient value.
- Any migration that makes tests green by rewriting historical BET evidence.

## 11. Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|---|---|---|
| 1 | 新 schema service/database/dispatcher vs additive Ledger contract | additive Ledger contract | 复用唯一 Ledger SSOT，避免第二真值面或调度面 |
| 2 | 破坏式 v2 migration vs v1 compatibility | additive compatibility | 保护现有消费者 |
| 3 | 历史 terminal 全量强制 vs grandfather | terminal grandfather | 不补造旧证据 |
| 4 | total equality 立即 strict vs staged | compatibility→repair→strict | 既有漂移不能锁死机制 BET |
| 5 | broad Ledger cleanup vs one-field repair | only `meta.total_bets` | 保持可审查范围 |
| 6 | validator 直接修复 vs separately claimed mutation | pure validator + 独立 workflow claim | 校验器没有写权限 |
| 7 | invalid v2 被兼容吞掉 vs typed halt | typed fail closed | 兼容仅覆盖既有 total drift，不掩盖合同错误 |
