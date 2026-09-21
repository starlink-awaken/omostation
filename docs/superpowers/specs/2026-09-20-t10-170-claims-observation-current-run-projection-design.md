---
schema_version: specification/v1
spec_version: 1.0.0
title: Canonical Claims observation current-run projection repair
bet_id: BET-Y1Q4-T10-170
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

# Canonical Claims observation current-run projection repair

## Problem

`samples.jsonl` is append-only across observer attempts. After a launchd
restart starts a fresh attempt, the canonical Panorama collector reads every
historical record and can calculate a maximum gap from a prior invalid attempt.
This makes the active, healthy Claims shadow window appear invalid even when the
current attempt has no gap above 120 seconds.

The repository-side collector must use `summary.started_at_utc` as the active
attempt boundary while preserving every historical record on disk.

## Base and artifacts

- Base: `45168df6dfac9465cf37a315c04b04e6cdab726c`
- Canonical collector base SHA-256: `2855f76eb26e3e97f4408aa965d714d1ce8b014affd93cdbdeb49218662e5c30`
- Canonical collector patched SHA-256: `01a2615077eea01afdc704ca6bb656a7de0e89e89a3f0cc93eeaa5d93fce6228`
- Collector patch SHA-256: `64275d2c499f821c1a6d6fdbb04be3d64725871c0ced588ce281262c1f69e743`
- Test patch SHA-256: `5987e5315960c6fc1281928b719a22473885d05f40754cf70eeea67ac80b15e9`
- Temporary focused test result: `4 passed`

## Contract

- Records older than `summary.started_at_utc` are excluded from projection and
  graduation computation.
- Historical records remain append-only and are never deleted or rewritten.
- Current-attempt malformed records still increment errors and fail the window
  closed.
- Descriptor, activation state, receipt digest, and sequence checks remain
  bounded by the active attempt.
- `bin/panorama/panorama-collect.py` and
  `bin/panorama/assets/host/panorama-collect-main.py.asset` remain byte-equal.
- Claims Authority v1 remains the only effective authority; v2 remains shadow.
- The active sampler is not restarted and the authority store is not mutated.

## RED/GREEN matrix

| Case | Required result |
| --- | --- |
| Prior-attempt gap greater than 120 seconds | Excluded; active max gap remains 60 seconds |
| Two current healthy samples | `IN_PROGRESS`, `sample_count=2`, `errors=0` |
| Current malformed JSON/non-object record | `INVALID`, current healthy count remains 2, `errors=1` |
| Current descriptor/state/receipt change | Existing fail-closed behavior remains |

## Implementation surface

Apply `collector.patch` to both canonical collector paths. Apply `test.patch`
only to `tests/unit/test_panorama_claims_authority.py`. Add the candidate
Ledger entry from `candidate-ledger-entry.yaml` only through
`bin/gac/ledger-safe-insert.py`. Do not alter any other path.

## Acceptance

Run focused tests, byte-equality check, host-sync check, ledger lint, and the
default local governance gate. After merge, sync the host collector, allow a
scheduled refresh, and verify Panorama reports the active attempt as
`IN_PROGRESS` with increasing samples, zero errors, and observed gap below 120
seconds.

## Rollback

Revert the single canonical collector patch, identical asset patch, and focused
test patch. No authority, observation, runtime, or value state requires rollback.

## Non-goals

This Spec does not authorize Claims lifecycle execution, graduation, business
value synthesis, admission expansion, a second control plane, or automatic
retry after an unknown outcome.
