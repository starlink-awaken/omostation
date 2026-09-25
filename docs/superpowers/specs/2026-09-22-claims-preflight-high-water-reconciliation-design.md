---
schema: md/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
schema_version: specification/v1
spec_version: 1.0.0
title: Claims preflight high-water filename reconciliation
bet_id: BET-Y2Q2-T10-156
created: '2026-09-22'
implementation_authorized: true
value_indicator_policy: false
risk_level: L1
human_gate: false
---


# Claims preflight high-water filename reconciliation

## Problem

The production Claims Authority runtime uses
`agents/_shared/runtime/omo-claims-authority-r0/high-water.json`. The WP1 Task
16 preflight instead tests `highwater.json`. On a clean exact-main clone, the
preflight therefore reports:

- `runtime_state.store_exists=true`
- `runtime_state.highwater_exists=false`
- `authority_store_asymmetric_presence`

Fresh evidence at `origin/main@c8c80c2ffdc1e8d68ffe53bac1f619eb4d5e79d2`
confirmed zero dirty root/child files and no closure drift. The asymmetry is a
preflight filename contract defect, not a real partial authority store.

## Change

Align the preflight observer with the production runtime filename:

1. Read `authority_dir/high-water.json`.
2. Keep the existing store and activation-witness paths unchanged.
3. Continue to treat exactly-one-missing store/high-water pair as asymmetric.
4. Treat both-missing as pristine and both-present as initialized.
5. Add `high_water_exists` as the canonical runtime-state field.
6. Retain `highwater_exists` as a read-only compatibility field until the next
   schema major, so current dashboard consumers fail safe rather than disappear.
7. Add focused RED/GREEN tests for loose-only, high-water-only, legacy-only,
   both-present, and both-missing authority layouts.

## Required implementation surfaces

- `bin/gac/claims-shadow-preflight.py`
- `tests/unit/test_claims_shadow_preflight.py`
- `docs/plans/3y-bet-ledger.yaml`
- the matching new BET retrospective

## Acceptance

1. Focused preflight tests pass.
2. A clean exact-main clone preflight no longer reports
   `authority_store_asymmetric_presence`.
3. The remaining blocker is only
   `operation_specific_host_authorization_unproven`, unless a real store defect
   is introduced.
4. Panorama Task 16 projection remains fail-closed and does not activate Claims
   Authority.
5. Ledger lint and governance gates pass.

## Non-goals

- Do not rename, move, initialize, repair, or quarantine the production store.
- Do not activate Claims Authority or approve lifecycle operations.
- Do not rewrite historical receipts or claim the lifecycle classes are proven.
- Do not change broker semantics, branch protection, CI, or another dashboard
  surface.

## Rollback

Revert the preflight filename and compatibility field changes plus the focused
test. Claims Authority remains shadow-active/read-only throughout.

## Review gate

This Spec is draft-only and is not implementation-authorized. It must remain
unbound until the human review verdict and a fresh accepted-binding transaction
exist.
