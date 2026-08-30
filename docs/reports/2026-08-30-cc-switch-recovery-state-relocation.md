---
schema_version: report/v1
status: active
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-30
last-reviewed: 2026-08-30
bet_id: BET-Y1Q3-T10-108
---

# CC Switch recovery-state relocation implementation evidence

## Current boundary

This report proves the Workspace capability implementation only. Host `apply`,
App Support target publication, source removal, postflight consumer evidence,
and operational completion are still pending. The migration family therefore
remains `in_progress`, and T10-108 remains `candidate`.

## Implemented capability

- `lib/documents_client_recovery_relocation.py` owns exact two-root inventory,
  source/target boundaries, source-handle and free-space gates, deterministic
  SHA-256/mode fingerprints, SQLite quick checks, staged movement, fsynced
  manifest publication, verification, and manifest-driven rollback.
- The existing registered `bin/gac/documents-domain-owner-job.py` exposes the
  `client-recovery` subcommand. No new bin entry or script registration remains.
- `phase-gate-enforce.yml` requires the focused tests and Ruff paths.
- The sole migration registry assigns `.codex-optimize-log/**` and
  `.cc-switch-recovery2/**` to the nonterminal `cc-switch-recovery-state`
  family. `root-oneoff-assets` retains its historical status and evidence gap.

## RED to GREEN evidence

- Baseline before edits: 25 existing Documents quarantine/migration tests
  passed.
- Task 1 RED: collection failed only because the new library did not exist.
  GREEN: 10 preflight tests passed.
- Task 2 RED: 5 tests failed only because apply/verify/rollback APIs were
  absent. GREEN: 16 transaction tests passed.
- Task 3 owner-convergence RED: 3 tests failed because the existing owner job
  did not dispatch `client-recovery`. GREEN: 20 tests passed through the real
  owner entry.
- Task 4 RED: the unique-owner test failed with missing
  `cc-switch-recovery-state`. GREEN: 21 focused tests passed and the migration
  checker reported 17 samples, zero unmatched, zero multiple matches, and zero
  errors.
- Focused Ruff passed. `/usr/bin/python3` compiled the library and owner entry
  and executed `client-recovery --help`.
- Existing baseline remained 25 passed. GaC passed after entry convergence.

## Entry-point correction

The first implementation used a new `bin/gac/documents-client-recovery.py`.
GaC correctly rejected it with `bin-quota-diff` (`new 1 > deleted 0`). The
1.0.1 amendment preserved all transaction semantics but deepened the existing
Documents owner job. The superseded CLI was deleted, final bin growth is zero,
and script-registry validation returns to the existing owner registration.

## Branch evidence

The implementation branch contains test-first commits for inventory,
transaction behavior, owner dispatch, CI wiring, family ownership, and the
1.0.1 owner amendment. These commits are branch evidence only until the
implementation PR is squash-merged and its merge commit is proven reachable
from authoritative main.

## Remaining acceptance

Merge the implementation PR with required checks, replay tests from main, then
use a fresh full-profile mainline clone for the 21-file/417772968-byte host
plan, apply, verify, full-tree audit, completion matrix, closeout PR, and final
workflow closeout. Value remains `NOT_PROVEN`.
