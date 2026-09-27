---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-27
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: Principal-ID Caller Migration — close SH-7 audit UNSAFE sites
bet_id: BET-Y2Q4-SH-9
---


# BET-Y2Q4-SH-9 — Principal-ID Caller Migration

## Context

`bin/ssot/audit-principal-id-canonicalization.py` (added in SH-7) reports
**7 UNSAFE** sites that read `OMO_PRINCIPAL_ID` directly via `os.environ.get`
without routing through `_principal_id_from_env()`:

```
bin/bc-os/north_star_meter_v2.py            L429  --principal-id CLI default
bin/gac/check-episode-pipeline.py           L84   bare read
bin/gac/compound-attribution-report.py       L269  --principal-id CLI default
bin/gac/unified-health-score.py             L211  bare read
bin/panorama/panorama-collect.py            L307  bare read
bin/ssot/test-episode-bridge.py            L40    bare read (test fixture)
bin/ssot/test-episode-bridge.py            L125   bare read (test fixture)
bin/ssot/weekly-review.py                   L74   bare read
```

All 7 are **read-only meters/gates/tests** — no episode-emit path. So
they can't currently corrupt the ledger with bare names. But any
future caller that treats these outputs as authoritative (e.g., a
metrics dashboard mapping principals to display names) inherits the
silent mismatch that SH-5.1 fixed at the recorder boundary.

## Goal

Migrate all 7 sites to import `principal_id_from_env` from
`bin.ssot._principal_id` and use it instead of bare
`os.environ.get("OMO_PRINCIPAL_ID", ...)`.  After migration:

```
$ bin/ssot/audit-principal-id-canonicalization.py
=== principal-id canonicalization audit (BET-Y2Q4-SH-7) ===
  total_callers: 11
  unsafe_count:  0
```

## Non-goals

- Do not refactor the recorder again (already CANONICAL).
- Do not change the canonicalization helper (already complete).
- Do not introduce a new "principal name" mapping.
- Do not change SH-5/SH-6/SH-7/SH-8 ledger entries.

## Done when

- All 7 UNSAFE sites migrated to `principal_id_from_env()`.
- `bin/ssot/audit-principal-id-canonicalization.py` reports `unsafe_count: 0`.
- `bin/ssot/test-principal-id-canonical.py` 4/4 cases still pass.
- `bin/ssot/test-episode-bridge.py --count 5` episodes=5, readiness=collecting.
- `make gac-local-gate` 68/68 green.

## Bootstrap authorization

- workflow: `project-code-change`
- agent: governance-team
- appetite: 0.25 day
- risk_level: L1 (1-line changes, hermetic)