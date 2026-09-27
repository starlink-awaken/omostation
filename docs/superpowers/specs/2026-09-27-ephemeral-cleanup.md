---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-27
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: Ephemeral Cleanup — close last 3 drift face findings
bet_id: BET-Y2Q4-SH-8
---


# BET-Y2Q4-SH-8 — Ephemeral Cleanup

## Context

After SH-1..5 + SH-5.1 + SH-6 + SH-7, the drift face detector reports 3
remaining ephemeral drifts:

```
[low] EPHEMERAL-BET-Y1Q3-T10-122-final-report:
      docs/reports/BET-Y1Q3-T10-122-final-report.md
[low] EPHEMERAL-documents-archive-rollback-receipt:
      docs/reports/documents-archive-rollback-receipt.md
[low] EPHEMERAL-kos-reuse-loop-verification-2026-09-26:
      docs/reports/kos-reuse-loop-verification-2026-09-26.md
```

All three are `type: ephemeral` documents that should have been archived
after their owning BET closed. The previous auto-pruner sweep stopped
short because the SSOT registry `documents-content-plane-migrations.yaml`
references `documents-archive-rollback-receipt.md` in 5 places and
`docs/plans/3y-bet-ledger.yaml` references it once (as rollback evidence
for BET-Y1Q4-T10-123).

## Goal

Archive all three ephemeral files to `docs/reports/archive/` and update
their SSOT + ledger references so the pointers remain valid. Drift
face drops 3 → 0 (all ephemeral class).

## Reference map

| file | refs in tracked code |
|------|---------------------|
| `BET-Y1Q3-T10-122-final-report.md` | 0 SSOT refs; 1 generated inventory flag |
| `kos-reuse-loop-verification-2026-09-26.md` | 0 SSOT refs |
| `documents-archive-rollback-receipt.md` | 5 in `documents-content-plane-migrations.yaml` + 1 in `3y-bet-ledger.yaml` |

## Non-goals

- Do not delete the files outright; archive preserves history.
- Do not modify the SSOT semantic intent — only the path suffix.
- Do not run panorama or refresh dashboard.

## Done when

- All 3 files moved to `docs/reports/archive/`.
- `documents-content-plane-migrations.yaml`: 5 `rollback_ref` lines
  updated to `docs/reports/archive/documents-archive-rollback-receipt.md`.
- `docs/plans/3y-bet-ledger.yaml` (BET-Y1Q4-T10-123): rollback receipt ref
  updated to the archive path.
- `make drift-face-clean` produces 0 ephemeral findings.
- `make gac-local-gate` passes 68/68.

## Bootstrap authorization

- workflow: `project-code-change`
- agent: governance-agent
- appetite: 0.25 day
- risk_level: L1 (path-only edits, hermetic)