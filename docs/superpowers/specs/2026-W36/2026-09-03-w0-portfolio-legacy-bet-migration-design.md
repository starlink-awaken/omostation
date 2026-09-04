---
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-09-03
last_updated: 2026-09-03
bet_id: BET-Y1Q4-T1-07
risk_level: L2
human_gate: true
value_indicator_policy: false
source_design_sha256: cbdee89004d0156e262daa63a1c38cfd660c0d5efbf0fce1a8eec8a92027c30b
source_proposal_sha256: 26bd1b3df552e693f2ac2684df255436522ff816d7844459523fafe130587100
source_amendment_sha256: 5b1bb03274d8f7383b67f88953cf0c7074a571a9a1d5aebb1ab68bb234042409
implementation_authorized: false
---

# W0 Legacy BET Migration Design

## 1. Decision

Inventory every Ledger BET and generate a deterministic classification
manifest before any migration. Historical terminal objects are referenced,
not rewritten. Non-terminal objects are applied only in separately authorized
batches of at most eight.

## 2. Classification contract

Each observed BET receives exactly one proposed disposition:

- `reuse`: historical delivery can serve as a prerequisite;
- `continue`: non-terminal work maps directly to W1-W6;
- `merge`: multiple candidates cover one KR;
- `defer`: useful but outside the funded Milestone;
- `stop`: no longer serves the Vision and requires explicit closure review.

The manifest records the immutable Ledger/source digest and the measured count
at execution time; it does not trust an older hard-coded total.

## 3. Migration invariants

- Every existing BET ID is preserved.
- Every existing status is preserved unless separately authorized.
- Every accepted binding, dependency, timestamp, retro, completion axis and
  value evidence object is preserved.
- Historical terminal incompleteness remains visible and is not repaired with
  fabricated evidence.
- `--dry-run` produces zero working-tree mutation.
- `--apply` without an exact batch authorization fails closed.

## 4. Prospective write surfaces

- `bin/plan/portfolio_migration.py`
- `tests/test_bet_portfolio_migration.py`
- `docs/generated/bet-portfolio-migration-manifest.yaml`
- this Spec and its future implementation plan/retro

The implementation BET does not own changes to the existing BET objects. Each
apply batch needs a separate claimed Ledger scope and human review.

## 5. Required verification

1. The manifest covers every current Ledger BET exactly once.
2. Historical done and blocked objects are byte/semantic equal.
3. Every non-terminal BET receives one disposition and rationale.
4. Classification order and bytes are deterministic.
5. Source digest drift blocks apply.
6. More than eight requested object mutations is rejected.
7. Unapproved status, binding, dependency, completion, or value changes are
   rejected.

## 6. Error and rollback contract

`MIGRATION_SCOPE_DRIFT`, `PORTFOLIO_CONCURRENT_UPDATE`, or an unclassified
object halts the batch. Rollback removes only the v2 fields added by the exact
batch and never rewrites business truth.

## 7. Authority boundary

This accepted Spec establishes binding identity only. It does not authorize
writing-plans, manifest implementation, migration apply, existing-BET
mutation, W1-W6, or value changes. Writing-plans requires a separate
post-binding authorization.

## 8. 验收标准

| ID | assertion | evidence_type | verifier |
|---|---|---|---|
| AC-T1-07-01 | Manifest covers every implementation-time Ledger BET exactly once | structured_report | ID set/count comparison |
| AC-T1-07-02 | Every terminal and blocked object remains semantically unchanged | immutable_diff | per-object base/current comparison |
| AC-T1-07-03 | Every non-terminal object has one proposed disposition and rationale | structured_report | classification completeness check |
| AC-T1-07-04 | Identical input produces byte-identical manifest | replay_receipt | repeated dry-run hash |
| AC-T1-07-05 | Source digest drift, missing batch authority or more than eight changes blocks apply | negative_test | migration guard fixtures |
| AC-T1-07-06 | No unapproved status, dependency, binding, completion or value mutation occurs | structural_report | allowlisted semantic delta |

## 9. 反指标

- Number or percentage of BETs classified as stop, merge or done.
- Reducing the Ledger by deleting history or evidence.
- A complete-looking manifest that omits blocked or malformed objects.
- Faster migration by increasing the authorized batch size.
- Treating an Agent classification as a business closure decision.

## 10. Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|---|---|---|
| 1 | auto-migrate vs manifest-first | manifest-first | 人类先审业务去留 |
| 2 | rewrite terminal history vs reference | reference only | 保护历史真值 |
| 3 | one large batch vs batches ≤8 | small batches | 保持可审查和可回滚 |
| 4 | fixed count vs implementation-time measure | dynamic immutable measure | 避免活文档漂移 |
| 5 | missing authority fallback vs halt | fail closed | 防止批量越权 |
| 6 | migration service/database/dispatcher vs Ledger-derived manifest | deterministic manifest | 复用唯一 Ledger SSOT，不建第二控制面 |
| 7 | Agent apply vs separately claimed human-reviewed batch | no autonomous apply | 分类建议没有业务真值修改权限 |
