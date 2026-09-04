---
schema_version: specification/v1
spec_version: 1.0.0
title: Restore T10-93 ledger entry dropped from the mainline merge tree
bet_id: BET-Y1Q3-T10-95
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
risk_level: L1
human_gate: false
type: ssot
last_updated: 2026-09-03
---

# Restore T10-93 ledger entry dropped from the mainline merge tree

## Intent

Restore the T10-93 BET record that exists in the immutable delivery head but
is absent from current `origin/main`, so the family runtime quarantine
evidence and its governing ledger entry are both discoverable and dependency
valid.

## Contract

- Treat `775bbb82f`, the immutable T10-93 delivery head, as the source for the
  exact T10-93 ledger block.
- Restore only the T10-93 entry in `docs/plans/3y-bet-ledger.yaml` plus this
  recovery BET's own report, retrospective, specification, and waiver.
- Preserve the current mainline T10-92/T10-94 records and all family registry,
  quarantine, runtime, host, submodule, and value-state content.
- Keep T10-93 as `done` with `completion_evidence.overall_state:
  delivery_accepted` and value `NOT_PROVEN`.

## Acceptance

1. Current mainline contains exactly one T10-93 ledger entry with the original
   done state, accepted Spec binding, dependency, and completion matrix.
2. T10-93 ledger content matches the immutable delivery head byte-for-byte for
   the restored block.
3. Ledger lint, T10-95 verification, doc-ssot, migration checker, and required
   governance checks pass without changing unrelated records.
