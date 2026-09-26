---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-26
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: Principal-ID Canonicalization Audit — single source of truth for OMO_PRINCIPAL_ID
bet_id: BET-Y2Q4-SH-7
---


# BET-Y2Q4-SH-7 — Principal-ID Canonicalization Audit

## Context

SH-5.1 fixed `bin/ssot/scene-outcome-recorder.py:_write_event_ledger_outcome`
to canonicalize `OMO_PRINCIPAL_ID` to the `principal:<id>` form before
emitting to the ledger. But the same `OMO_PRINCIPAL_ID` env var is read
in 10+ other call sites across `bin/`:

```
bin/bc-os/north_star_meter_v2.py:426    --principal-id default OMO_PRINCIPAL_ID
bin/gac/check-episode-pipeline.py:56     bare OMO_PRINCIPAL_ID
bin/gac/unified-health-score.py:211      bare OMO_PRINCIPAL_ID
bin/gac/compound-attribution-report.py:265  bare OMO_PRINCIPAL_ID
bin/panorama/panorama-collect.py:307    bare OMO_PRINCIPAL_ID
bin/ssot/weekly-review.py:74             bare OMO_PRINCIPAL_ID
bin/ssot/scene-outcome-recorder.py:127   canonicalize ✅
bin/ssot/scene-outcome-recorder.py:214   not canonicalized ⚠ (personal-episode path)
bin/ssot/scene-outcome-recorder.py:300   not canonicalized ⚠ (mos-decision-outcome path)
bin/ssot/test-episode-bridge.py:123      canonicalize via local helper
```

Three failure modes emerge from this fragmentation:

1. **Inconsistency**: each caller duplicates the prefix logic, or omits
   it (rows 2-6 + 214 + 300 above). The recorder's helper is private;
   callers cannot share it without importing `bin/`.
2. **Drift**: the personal-episode path (line 214) still uses bare form;
   if any scene triggers that path, episodes become invisible.
3. **Audit gap**: there is no single grep that answers "where do we
   read `OMO_PRINCIPAL_ID`?" — drift face detector's audit gate cannot
   check it.

## Goal

Promote `_canonical_principal_id` to a shared utility and route every
OMO_PRINCIPAL_ID read through it. Add an audit script that enumerates
all call sites and reports which bypass canonicalization.

## Non-goals

- Do not change sovereignty prefix constants.
- Do not refactor every caller (deferred; this BET only fixes the
  recorder and adds the audit).
- Do not extend ledger schema.

## Done when

- A shared helper module (e.g., `bin/ssot/_principal_id.py`) exports
  `canonical_principal_id(raw: str | None) -> str` and a
  `principal_id_from_env() -> str` convenience wrapper.
- `bin/ssot/scene-outcome-recorder.py` uses the shared helper in all
  three emit paths (lines 127, 214, 300).
- `bin/ssot/audit-principal-id-canonicalization.py` greps all
  `OMO_PRINCIPAL_ID` callers and reports the canonicalization gap.
- `bin/ssot/test-principal-id-canonical.py` covers boundary cases
  (empty, prefixed, with-colon, with-mixed-case).
- `bin/gac/gac-local-gate.py` runs the audit (warn-only initially).

## Bootstrap authorization

- workflow: `project-code-change`
- agent: governance-agent
- appetite: 1 day
- risk_level: L1 (refactor + audit, no schema change)