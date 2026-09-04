---
schema_version: governance-waiver-evidence/v1
owner: human-principal
lifecycle: contract
last_updated: 2026-08-28
created: 2026-08-28
expires_when: bootstrap PR merges or closes
value_indicator_policy: false
title: Product P0 Spec Bootstrap Workflow Waiver
type: doc
lifecycle: history
last_updated: 2026-08-28
---

# Product P0 Spec Bootstrap Workflow Waiver

## User authorization

> 本次 Product P0 父 BET 与六个 child Spec/WorkPacket 自举跳过 workflow start，允许使用 AGCP_REQUIREMENT_ITERATION_GATE=0；仅限七份已列明的 Product P0 Spec、docs/plans/3y-bet-ledger.yaml 仅新增 BET-Y1Q3-T4-02 至 BET-Y1Q3-T4-08，以及 .omo/_truth/governance-evidence/waiver-2026-08-28-product-p0-spec-bootstrap.md 记录本句；不得修改其他 BET、completion/value evidence、实现代码、gitlink 或运行态。

Authorization date: 2026-08-28.

## Reason

`agent-workflow start` requires an already-existing BET with one accepted Spec binding. Creating the first parent/child BET and accepted Spec set is therefore a bounded self-bootstrap cycle. This waiver authorizes only that initial declaration; every implementation, test, submodule pointer, operational canary, value observation and closeout must use normal governed workflow runs and exact claims.

## Exact allowed paths

- `docs/superpowers/specs/2026-08-28-product-p0-truth-loop-design.md`
- `docs/superpowers/specs/2026-08-28-product-p0-wp1-honest-scene-gate-design.md`
- `docs/superpowers/specs/2026-08-28-product-p0-wp2-honest-agent-cell-receipt-design.md`
- `docs/superpowers/specs/2026-08-28-product-p0-wp3-canonical-outbox-publisher-design.md`
- `docs/superpowers/specs/2026-08-28-product-p0-wp4-principal-authority-binding-design.md`
- `docs/superpowers/specs/2026-08-28-product-p0-wp5-human-adjudication-value-design.md`
- `docs/superpowers/specs/2026-08-28-product-p0-wp6-physical-recovery-drill-design.md`
- `docs/plans/3y-bet-ledger.yaml` only for new entries `BET-Y1Q3-T4-02` through `BET-Y1Q3-T4-08`
- `.omo/_truth/governance-evidence/waiver-2026-08-28-product-p0-spec-bootstrap.md`

## Explicitly prohibited

- changes to any pre-existing BET;
- any `completion_evidence`, value evidence or BET status outside the seven new candidate entries;
- implementation code, tests, generated projections or gitlinks;
- services, databases, schedules, user configuration or any other runtime state;
- claiming Product P0, any child BET, or principal-bound value complete.

## Execution constraint

`AGCP_REQUIREMENT_ITERATION_GATE=0` may be set only for the bounded bootstrap commit and its exact verification. It is not inherited by subsequent workflow starts or implementation work.
