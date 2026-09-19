---
schema_version: specification/v1
spec_version: 1.0.0
title: Historical completion receipt digest re-attestation
bet_id: BET-Y1Q3-T10-55
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-29
last-reviewed: 2026-08-29
type: ssot
last_updated: 2026-09-03
---

# Historical completion receipt digest re-attestation

## Intent

Recompute stale file receipt digests in the historical completion matrices for
the twelve non-T1-12 BETs identified by the current ledger lint, so each digest
matches the file currently resolved by the canonical ledger validator.

## Constraints

- Update only receipt digests and the derived overall state they unblock.
- Do not alter historical BET scope, verdicts, implementation, runtime state,
  human attestations, or T1-12.
- Preserve every receipt reference and document the exact before/after audit.

## Acceptance

- No stale digest or derived `OVERALL_STATE_MISMATCH` remains for the twelve
  listed historical BETs.
- T1-12 remains unchanged and is reported separately.
- Root SSOT and governance checks pass.
