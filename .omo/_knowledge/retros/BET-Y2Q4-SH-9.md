---
schema: md/v1
status: completed
lifecycle: history
owner: governance-agent
last-reviewed: 2026-09-27
type: retro
schema_version: retrospective/v1
title: "BET-Y2Q4-SH-9 Closeout Retro — Principal-ID Caller Migration"
bet_id: BET-Y2Q4-SH-9
created: "2026-09-27"
run_id: 20260927T083905Z-project-code-change-4f036780
---


# BET-Y2Q4-SH-9 Closeout Retro

> **TL;DR**: SH-7 audit's 7 UNSAFE sites migrated to
> `principal_id_from_env()`. Audit now reports `unsafe_count: 0`.

## Deliverables

- `bin/bc-os/north_star_meter_v2.py` — `--principal-id` default + helper import
- `bin/gac/check-episode-pipeline.py` — `principal_id_from_env()` for recent_episodes query
- `bin/gac/compound-attribution-report.py` — `--principal-id` default
- `bin/gac/unified-health-score.py` — `principal_id_from_env()`
- `bin/panorama/panorama-collect.py` — `principal_id_from_env()` (note: file already has many `from pathlib import Path as _P` aliases; my SH-9 block is the only top-level pathlib ref)
- `bin/ssot/test-episode-bridge.py` — 2 sites (test fixture bootstrap + assertion in hermetic test)
- `bin/ssot/weekly-review.py` — `principal_id_from_env()`

## Q1 — actual time vs appetite

Appetite: 0.25 day.  Actual: same-session.  No drift.

## Q2 — done_when validation

| # | condition | result |
|---|-----------|--------|
| 1 | All 7 UNSAFE sites migrated | ✅ |
| 2 | audit-principal-id-canonicalization reports `unsafe_count: 0` | ✅ |
| 3 | test-principal-id-canonical 4/4 pass | ✅ |
| 4 | test-episode-bridge --count 5 passes | ✅ episodes=5, readiness=collecting |
| 5 | make gac-local-gate 68/68 | ✅ |

## Q3 — root cause vs symptom

SH-5.1 fixed the recorder boundary but left 7 other callers using
`os.environ.get("OMO_PRINCIPAL_ID", ...)`. They didn't matter *today*
because none of them write to the ledger, but they would become a
silent-mismatch source the moment any future code path treats their
output as authoritative (e.g., a dashboard mapping principals to
display names). SH-9 closes that gap.

The 7 sites are all read-only meters/gates/tests — no emit paths — so
the fix is purely preventive. The audit (`audit-principal-id-canonicalization`)
becomes the regression detector going forward: any new UNSAFE call site
will flag immediately.

## Lessons

- **Boundary normalization + caller hygiene** are two halves of the
  same discipline. SH-5.1 was the boundary; SH-9 is the caller audit.
- **Audit scripts are the durable asset**: now that
  `audit-principal-id-canonicalization` exists, the system has a
  guard rail — adding new UNSAFE sites requires explicit justification.
- **Read-only callers still need canonicalization** when their output
  may be promoted to authoritative input by future code.

## Next steps

1. Land this BET in main; audit reports 0/11 unsafe.
2. Promote `audit-principal-id-canonicalization` to a CI gate
   (`make gac-local-gate` warn-level addition) so any new caller is
   flagged at PR time, not via silent drift.
3. After 4 weeks of organic closeout, north-star should drop the
   `no_qualifying_weeks` gate gap; no further action needed for SH-9.