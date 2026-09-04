---
schema_version: specification/v1
spec_version: 1.0.0
title: Canonical ledger duplicate-key hygiene
bet_id: BET-Y1Q3-T10-56
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
type: ssot
last_updated: 2026-09-03
---

# Canonical ledger duplicate-key hygiene

## Intent

Remove the duplicate `done_at` key accidentally retained in the T10-55 ledger
entry while preserving the parsed value and all completion evidence.

## Constraints

- Only normalize the duplicate YAML key and record the before/after audit.
- Do not change BET status, completion evidence, receipt hashes, or T1-12.
- Do not modify implementation, runtime, host state, or registries.

## Acceptance

- T10-55 has exactly one `done_at` key.
- Ledger lint remains limited to the pre-existing T1-12 schema errors.
