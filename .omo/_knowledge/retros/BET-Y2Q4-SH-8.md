---
schema: md/v1
status: completed
lifecycle: history
owner: governance-agent
last-reviewed: 2026-09-27
type: retro
schema_version: retrospective/v1
title: "BET-Y2Q4-SH-8 Closeout Retro — Ephemeral Cleanup (drift face → 0)"
bet_id: BET-Y2Q4-SH-8
created: "2026-09-27"
run_id: 20260927T063820Z-project-code-change-dac85e73
---


# BET-Y2Q4-SH-8 Closeout Retro

> **TL;DR**: drift face 3 → 0 by archiving 3 stale ephemeral files
> and updating their SSOT/ledger refs to keep pointers valid.

## Deliverables

- `docs/reports/archive/BET-Y1Q3-T10-122-final-report.md`
- `docs/reports/archive/kos-reuse-loop-verification-2026-09-26.md`
- `docs/reports/archive/documents-archive-rollback-receipt.md`
- `.omo/_truth/registry/documents-content-plane-migrations.yaml` — 6 `rollback_ref` lines updated to archive path
- `docs/plans/3y-bet-ledger.yaml` (BET-Y1Q4-T10-123) — receipt ref updated
- `docs/superpowers/specs/2026-09-27-ephemeral-cleanup.md` — accepted spec
- `docs/plans/3y-bet-ledger.yaml` — SH-8 entry

## Q1 — actual time vs appetite

Appetite: 0.25 day.  Actual: same-session.  No drift.

## Q2 — done_when validation

| # | condition | result |
|---|-----------|--------|
| 1 | All 3 files moved to `docs/reports/archive/` | ✅ `git mv` |
| 2 | SSOT registry: 6 rollback_ref lines updated | ✅ verified `grep -c` |
| 3 | Ledger: 1 rollback receipt ref updated | ✅ verified |
| 4 | `make drift-face-clean` produces 0 ephemeral findings | ✅ drift-face-detector: `Total: 0 drift(s)` |
| 5 | `make gac-local-gate` passes 68/68 | ✅ 69/69 green |

## Q3 — root cause vs symptom

The drift face detector had been blocked at 3 ephemeral findings
because the auto-pruner's `prune_ephemeral` skipped any file referenced
by SSOT registry (`receipt://...` pointers in `documents-content-plane-migrations.yaml`
and `3y-bet-ledger.yaml`). The fix is the inverse of SH-5 / SH-7: instead
of writing more code, *update the SSOT pointers to follow the archive*.

This is the right pattern for ephemeral files that have outlived their
owning BET: the SSOT should track the **archive path**, not the
working tree path, so future auto-pruners can sweep freely.

## Final drift face

```
=== drift-face-detector ===
Total: 0 drift(s)
```

The drift face detector's count of 0 confirms all 5 classes are empty
(ephemeral, runs, dashboard, brief, ritual). This is the first time
the system has reached `0 drift` since SH-1 introduced the detector.

## Lessons

- **SSOT path semantics**: when a file's lifecycle ends, the SSOT
  should point at its archive path immediately. Don't wait for
  auto-pruner to coordinate the rename.
- **Deterministic idempotence**: the new path is `archive/<filename>`
  so the same mapping applies to every ephemeral file. No
  hand-curated redirect tables.
- **6 refs vs 5 expected**: my early `grep -c` returned 5 unique
  rollback_ref lines but `replace_all` reported 6 occurrences. The
  discrepancy was because one entry referenced the receipt in two
  places (rollback + evidence). Always re-verify after bulk replace.

## Next steps

1. Land this BET in main; drift face drops to 0.
2. Update `make drift-face-clean` target to verify 0 across all 5
   classes (currently the make target only invokes drift + auto-pruner
   in sequence; an explicit "expect 0" gate could be added).
3. Consider promoting ephemeral-file lifecycle to a more disciplined
   stage: when a BET closes, automatically update SSOT pointers to the
   archive path so the SSOT never lags behind the file move.