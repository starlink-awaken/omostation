---
schema_version: specification/v1
spec_version: 1.0.0
title: Reconcile current completion evidence digests for T10-02 and T10-06
bet_id: BET-Y1Q3-T10-97
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-30
last-reviewed: 2026-08-30
risk_level: L1
human_gate: false
type: ssot
last_updated: 2026-09-03
---

# Reconcile current completion evidence digests for T10-02 and T10-06

## Intent

Repair eight stale file-digest references in the already completed T10-02 and
T10-06 completion matrices after the canonical `maturity-scorecard.py` file
changed, without changing either BET's completion meaning or value verdict.

## Contract

- Update only the four references to `bin/gac/maturity-scorecard.py` in each
  of T10-02 and T10-06: engineering diff/rollback, operational live canary,
  and value real signal.
- Use the current canonical file digest measured from the fixed mainline tree;
  do not edit the referenced file or replace any evidence artifact.
- Preserve all BET statuses, dates, dependencies, value samples, attestations,
  Documents content, runtime payloads, and unrelated ledger records.
- The completion matrices must derive their existing `outcome_accepted` state
  again after the eight references are reconciled.

## Acceptance

1. All eight selected references resolve to the current
   `maturity-scorecard.py` SHA.
2. T10-02 and T10-06 remain semantically unchanged and derive
   `outcome_accepted`.
3. `bet-ledger lint`, focused evidence assertions, doc-ssot, and governance
   verification pass with no additional changed files.
