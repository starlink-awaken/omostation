---
schema_version: specification/v1
spec_version: 1.0.0
title: B1 calibration JSON export and Agent Brief reading parity
bet_id: BET-Y2Q4-T10-268
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-26
---


# B1 calibration JSON export and Agent Brief reading parity

## Scope

Repair `bet-ledger.py list --json` serialization, add a bounded three-reading
comparison block to the Panorama Agent Brief, and correct stale Panorama
scheduler wording. The readings are ledger output, objective coverage, and
value-proof readiness; they remain meaning-separated and are never compared
numerically.

## Contract

- `cmd_list --json` must serialize every ledger-supported date value without
  losing the command exit contract.
- `agent_visibility.work_state.readings` must expose `ledger`,
  `objective_coverage`, and `value_proof`. Each row carries meaning, source,
  source kind, liveness, observed timestamp, and comparability. The comparison
  verdict declares `comparable_pair_count: 0` because no two rows share the
  same meaning or independent source semantics.
- Producer-derived brief generation adds the block only after portfolio cohort
  binding and before body hashing. Snapshot compatibility preserves the block
  as ordinary brief content.
- `docs/PANORAMA.md` must not describe the retired
  `com.omostation.panorama-dashboard-refresh` job as current. Current writers
  are the projection publisher and republisher under the `zhixing-projection`
  surface.

## Boundaries

No launchd installation, service restart, deployment, cron mutation, or
runtime dashboard writes. No numeric comparison or aggregation across readings.
Objective coverage acceptance rules do not change.

## Acceptance

Focused ledger and Panorama unit tests pass, ledger lint passes, and both
changed Python entrypoints compile.
