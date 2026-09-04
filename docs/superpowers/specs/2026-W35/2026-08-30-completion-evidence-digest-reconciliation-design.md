---
schema_version: specification/v1
spec_version: 1.0.0
title: Completion evidence digest reconciliation
bet_id: BET-Y1Q3-T10-91
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
risk_level: L1
human_gate: false
type: ssot
last_updated: 2026-09-03
---

# Completion evidence digest reconciliation

## Intent

Repair stale file digests in the completion matrices of already completed BETs
after their evidence files changed in later governed work.

## Contract

- The evidence file bytes are authoritative; recompute their SHA-256 values
  before editing the ledger.
- Update only the stale `maturity-scorecard.py` references for T4-04, T10-02,
  and T10-06.
- Preserve every status, completion date, attestation, value verdict, and
  unrelated evidence reference.
- Require `bet-ledger lint` and each affected completion matrix to validate
  after the repair.

## Acceptance

1. All eight stale references resolve to the current scorecard digest.
2. The affected matrices derive their declared accepted state again.
3. No implementation, user data, Documents, client state, or runtime payload
   is changed.
