---
schema_version: specification/v1
spec_version: 1.0.0
title: Live value readiness v2-only projection repair
bet_id: BET-Y1Q4-T10-171
status: accepted
lifecycle: spec
owner: governance-team
created: '2026-09-20'
last-reviewed: '2026-09-20'
implementation_authorized: true
value_indicator_policy: false
risk_level: L1
human_gate: false
type: ssot
---

# Live value readiness v2-only projection repair

## Problem

The 43191 `/api/v1/agent/value-proof-readiness` route builds its top-level
`samples.qualifying` from `panel_value.samples.qualifying`. That panel includes
legacy evidence, so one legacy qualifying record appears as business-value
progress even though `value-evidence-validation/v2` correctly reports
`qualifying=0`, `v2_records=0`, and `remaining_to_target=30`.

## Base and artifacts

- Base: `45168df6dfac9465cf37a315c04b04e6cdab726c`
- Patched live server SHA-256: `fa0f9b66054f598867ecf74f01047729e05e015e40f1fea265dd49b0575dc95f`
- Live server patch SHA-256: `c3a33ed2e21a6a80eb6ecc9a7dde221753e3e41e82014788c127fc4daaa730dc`
- Test file SHA-256: `b99d91f4e14fa3114175beca42feab7efcd2b74ef7e48b101e75eb64e81ff36c`
- Temporary focused test result: `3 passed`

## Contract

- Qualifying business-value readiness is `value-evidence-validation/v2.qualifying`.
- Target is `value-evidence-validation/v2.target`, defaulting to 30.
- If validation is unavailable, has the wrong schema, or is not ok, qualifying
  fails closed to zero.
- Legacy records and legacy qualifying records remain explicit history fields,
  never part of qualifying readiness.
- The response schema becomes `agent-value-proof-readiness/v2`.
- The samples threshold is corrected to the same v2 qualifying count.
- No evidence is created, edited, replayed, or backfilled.

## RED/GREEN matrix

| Case | Required result |
| --- | --- |
| Legacy qualifying=1, v2 qualifying=0 | API qualifying=0, remaining=30, legacy_qualifying=1 |
| V2 qualifying=2 | API qualifying=2, remaining=28 |
| Validation unavailable or invalid | Qualifying fails closed to 0 |
| Samples threshold current=1 from legacy panel | Threshold corrected to v2 qualifying count |

## Deployment and restart boundary

After required checks and merge, run host-sync restore so the deployed
`live_server.py` matches the merged asset. Restarting the 43191 live server is
outside implementation authorization and requires a separate explicit operator
approval. Until that restart, the running process may continue to expose the
old v1 response; this must be reported honestly.

## Acceptance

Focused tests must pass. Host asset and deployed file must match after restore.
Ledger lint and default governance gate must pass. After an authorized restart,
the API must return `agent-value-proof-readiness/v2`, `qualifying=0`, and
`remaining=30` for the current evidence set.

## Rollback

Revert the live-server asset and focused test. Restore the prior deployed live
server, restart only with fresh operator authorization, and verify the prior
API contract. No value or authority state requires rollback.

## Non-goals

This Spec does not prove business value, alter the 30-sample target, admit a
new runtime, mutate Claims Authority, or authorize automatic retries.
