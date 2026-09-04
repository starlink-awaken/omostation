---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
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

## Mainline host preflight incident

Mainline implementation `898e5f6ee0878ad218333693a0cc40a73326a1ef`
replayed 21 focused tests, 25 prior tests, migration coverage, and workflow
health before host planning. The first no-write plan halted with
`SQLITE_CORRUPT`; no source or target was mutated.

Read-only enumeration found seven recognizable SQLite recovery files. Six pass
`PRAGMA quick_check`: the three `.codex-optimize-log` backups, `rebuilt2.db`,
`tiny_test.db`, and `tiny_test2.db`. Only the deliberately retained pre-repair
`.cc-switch-recovery2/current.db` is damaged; it is 69353472 bytes with SHA-256
`df0a17b1cb391f3cf78426853269402fbf3be578f86f051bc1e280bb0431c76a`.

Specification 1.0.2 therefore records healthy SQLite files as `ok` and the
known damaged recovery sample as digest-bound `corrupt-preserved`. File hash,
mode, path, aggregate fingerprint, and classification replay remain blocking;
at least one healthy SQLite recovery file is required. Host apply remains
pending until this amendment and regression reach main.

The amended no-write plan succeeds with exactly 21 files, 417772968 bytes,
source fingerprint
`sha256:6050fb3f53e99d7cfc8c85faff5be776aba06fb18fc0ab928ecab29f37898ced`,
six `ok` SQLite checks, and one `corrupt-preserved` check whose result digest is
`sha256:019de329b9bd09bdb76cd7d2bc987e47212a0e300b49f913354109fd9b18727a`.
Permanent deletion is false and the target remains absent.

## Mainline host completion

Specification 1.0.2 merged through PR #2765 as
`e72bf052af1f09d9e87502b979b97fd165777bf5`. A fresh full-profile clone replayed
22 focused tests and generated two byte-identical plans before mutation. Both
plans contained 21 files, 417772968 bytes, source fingerprint
`sha256:6050fb3f53e99d7cfc8c85faff5be776aba06fb18fc0ab928ecab29f37898ced`,
six `ok` SQLite checks, and one digest-bound `corrupt-preserved` check. Both
source roots had zero open handles; target, staging, and rollback-receipt paths
were absent.

The mainline `client-recovery apply` transaction moved all 21 files through a
private staging directory, verified bytes/modes/fingerprint and SQLite status,
fsynced the manifest, atomically published the target, and removed only the two
empty source roots. Postflight proves:

- target: `~/Library/Application Support/CC_Switch Recovery/2026-08-30`;
- manifest SHA-256:
  `sha256:f64b1020645475a9d9e3c6ce77cfea3deefb3027ca7f3186562253c99d6ae89d`;
- manifest mode: `0600`; payload files: 21; payload bytes: 417772968;
- source and target fingerprints equal; both Documents roots absent;
- six SQLite checks remain `ok`; `current.db` remains byte-identical
  `corrupt-preserved` with the preflight result digest;
- fresh verify reports `rollback_available=true`;
- fresh consumer audit reports `status=ok`, `forbidden_executors=0`, and
  `unmatched=0`; permanent deletion is false.

Before and after the move, three protected active/iCloud CC Switch roots were
hashed at file level. Of 805 files, 803 were byte-identical and both iCloud
roots were unchanged. The active `cc-switch` PID 95716 naturally wrote its open
`cc-switch.db` and `logs/cc-switch.log` during the observation window; those
two paths are outside every transaction boundary and were never selected.

The full Documents audit was stable in one attempt but remains non-green from
unrelated historical debt: runtime 4907, cache 36855, invalid archive 31448,
and 73211 total violations. This is explicit evidence that T10-108 is complete
without claiming Documents-wide physical purity.

Engineering is `VERIFIED` and the host relocation is `PROVEN`. Principal-bound
user value remains `NOT_PROVEN`.
