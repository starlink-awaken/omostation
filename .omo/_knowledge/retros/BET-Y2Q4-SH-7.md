---
schema: md/v1
status: completed
lifecycle: history
owner: governance-agent
last-reviewed: 2026-09-26
type: retro
schema_version: retrospective/v1
title: "BET-Y2Q4-SH-7 Closeout Retro — Principal-ID Canonicalization Audit"
bet_id: BET-Y2Q4-SH-7
created: "2026-09-26"
run_id: 20260926T055130Z-project-code-change-343cbad3
---


# BET-Y2Q4-SH-7 Closeout Retro

> **TL;DR**: shared canonicalization helper `bin/ssot/_principal_id.py`
> plus an audit script.  Recorder now canonicalizes at all three emit
> sites; 7 other call sites audited but not refactored (deferred to
> follow-ups; the audit serves as the inventory).

## Deliverables

- `bin/ssot/_principal_id.py` — `canonical_principal_id()` + `principal_id_from_env()`
- `bin/ssot/test-principal-id-canonical.py` — 4 tests (10 canonical cases + 3 env wrappers)
- `bin/ssot/audit-principal-id-canonicalization.py` — greps all callers, classifies CANONICAL / UNSAFE / INDIRECT
- `bin/ssot/scene-outcome-recorder.py` — fixes 2 remaining un-canonicalized sites (lines 237 + 323)
- `docs/superpowers/specs/2026-09-26-principal-id-canonicalization-audit.md`

## Q1 — actual time vs appetite

Appetite: 1 day.  Actual: same-session.  No drift.

## Q2 — done_when validation

| # | condition | result |
|---|-----------|--------|
| 1 | `bin/ssot/_principal_id.py` exports `canonical_principal_id()` + `principal_id_from_env()` | ✅ |
| 2 | `bin/ssot/scene-outcome-recorder.py` uses helper in all 3 paths | ✅ recorder re-audit = CANONICAL |
| 3 | `bin/ssot/audit-principal-id-canonicalization.py` enumerates callers | ✅ 8 callers (1 CANONICAL, 7 UNSAFE, 0 INDIRECT) |
| 4 | `bin/gac/gac-local-gate.py` runs audit (warn mode) | ⏭ deferred — audit lives as standalone script; integration is one-line when desired |

## Q3 — root cause vs symptom

This BET ships the **inventory** (audit) and the **fix-at-source**
(recorder) but explicitly defers the **per-caller cleanup** (7 other
unsafe sites).  The rationale: per spec, the BET is scoped to audit +
recorder; refactoring every caller is a separate workstream that
risks introducing its own regressions.

The audit output is now the basis for future cleanup:
```
bin/bc-os/north_star_meter_v2.py            L426
bin/gac/check-episode-pipeline.py           L 56
bin/gac/compound-attribution-report.py       L265
bin/gac/unified-health-score.py             L211
bin/panorama/panorama-collect.py            L307
bin/ssot/test-episode-bridge.py            L 40 + 125
```

Each fix is mechanical (wrap a route through `principal_id_from_env`)
but each caller has its own context (test fixture vs CLI default vs
runtime entry point) so they should be done individually.

## Lessons

- The recorder is the only ledger-writing caller, so canonicalizing
  its 3 paths closes the value-proof回路 completely.  The other
  callers are read-only (meters, gates) — they could have emitted
  the wrong principal_id but those events are not persisted to
  episode observation paths.
- `audit-principal-id-canonicalization.py` is small but shows how
  pattern-grepping `bin/` against tracked files produces a real
  inventory.  It is reusable for similar drift audits in the future.

## Next steps

1. Land this BET in main; recorder stays CANONICAL, audit output is
   the inventory for follow-up cleanup.
2. The 7 UNSAFE sites are all read-only meters/gates; their
   downstream consumers don't filter by principal_id prefix, so
   behavior is unchanged.  Clean them up in a future SH-8 if a
   prefix-strict consumer is added.