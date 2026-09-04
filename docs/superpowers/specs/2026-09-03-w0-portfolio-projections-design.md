---
schema_version: specification/v1
spec_version: 1.0.1
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-09-03
last-reviewed: 2026-09-03
bet_id: BET-Y1Q4-T1-08
risk_level: L2
human_gate: false
value_indicator_policy: false
source_design_sha256: cbdee89004d0156e262daa63a1c38cfd660c0d5efbf0fce1a8eec8a92027c30b
source_proposal_sha256: 26bd1b3df552e693f2ac2684df255436522ff816d7844459523fafe130587100
source_amendment_sha256: 5b1bb03274d8f7383b67f88953cf0c7074a571a9a1d5aebb1ab68bb234042409
implementation_authorized: true
---

# W0 Portfolio Projection Design

## 1. Decision

### Implementation authorization (1.0.1)

Principal session authorization 2026-09-04 ("go，先pr合并提交。然后依次推进吧，需要人类的，我给你授权") releases human_gate and authorizes implementation for remaining W0 Portfolio children in safer order. T1-08 may generate Markdown and leave broker-unowned .omo targets unavailable until a separate broker amendment.


Generate three single-direction projections from the Ledger:

- `.omo/goals/current.yaml` for current Objective/KR/Milestone context;
- `docs/plans/3Y-BET-PORTFOLIO.md` for the human-readable portfolio;
- `.omo/_control/portfolio-status.json` for Cockpit consumption.

None is a reverse writer or independent truth source.

## 2. Projection ownership

`portfolio_projection.py` computes canonical bytes and source digests. It may
write the repository Markdown view through its explicit apply path. The two
`.omo` outputs are broker-owned and must be atomically applied through the
registered OMO state/projection broker; direct `write_text` is forbidden.

## 3. Determinism and freshness

- All projections carry the same Ledger source digest.
- Two runs on identical input are byte-identical.
- `--check` returns nonzero on any byte or digest drift.
- Dirty runtime state never changes portfolio completion.
- Missing or stale inputs appear as unavailable, never as healthy or complete.

## 4. Prospective write surfaces

- `bin/plan/portfolio_projection.py`
- `bin/plan/bet-ledger.py`
- `tests/test_bet_portfolio_projection.py`
- `.omo/goals/current.yaml` through its registered broker
- `.omo/_control/portfolio-status.json` through its registered broker
- `docs/plans/3Y-BET-PORTFOLIO.md`
- this Spec and its future implementation plan/retro

## 5. Required verification

1. Three outputs share one exact source digest.
2. Regeneration is byte-stable.
3. One-byte drift is detected.
4. `.omo` direct-I/O static and negative tests reject direct writers.
5. Missing runtime state produces explicit unavailable fields.
6. Projection fields cannot be consumed as authority for a reverse Ledger
   mutation.

## 6. Error and rollback contract

`PROJECTION_DRIFT` halts admission. Broker failure leaves the previous
projection intact and reports unavailable; it never partially publishes.
Rollback regenerates from Ledger or restores the last digest-bound projection,
without touching Ledger data.

## 7. Authority boundary

This accepted Spec establishes binding identity only. It does not authorize
writing-plans, code, broker writes, projection generation, Ledger changes,
W1-W6, or runtime/value mutation. Writing-plans requires a separate
post-binding authorization.

## 8. 验收标准

| ID | assertion | evidence_type | verifier |
|---|---|---|---|
| AC-T1-08-01 | Goals, Markdown and control outputs share one exact Ledger source digest | structured_report | three-output digest comparison |
| AC-T1-08-02 | Identical source input generates byte-identical outputs | replay_receipt | repeated generation hash |
| AC-T1-08-03 | One-byte projection drift is detected by `--check` | negative_test | corrupted-output fixture |
| AC-T1-08-04 | `.omo` outputs can be applied only through registered brokers | negative_test | direct-I/O rejection tests |
| AC-T1-08-05 | Missing/stale source is reported unavailable, never inferred complete | boundary_test | unavailable input fixture |
| AC-T1-08-06 | No projection can authorize a reverse Ledger mutation | contract_test | read-only consumer assertion |

## 9. 反指标

- Number of generated files, fields or dashboard cards.
- Fresh timestamps without matching source digest.
- Projection health used as proof that source truth is correct.
- A successful direct filesystem write to a broker-owned `.omo` path.
- UI rendering success without deterministic regeneration.

## 10. Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|---|---|---|
| 1 | Goals 独立写 vs Ledger projection | one-way projection | 消除双写 |
| 2 | generator 直写 `.omo` vs broker | registered broker | 遵守状态所有权 |
| 3 | mutable runtime 推断 vs Ledger digest | immutable source digest | 防止瞬态假完成 |
| 4 | stale fallback success vs unavailable | explicit unavailable | 不把缺证据当健康 |
| 5 | bidirectional sync vs no reverse writer | no reverse writer | 保持唯一 SSOT |
| 6 | projection service/database/dispatcher vs generator + registered broker | reuse existing pipeline | 不建立第二状态或调度面 |
