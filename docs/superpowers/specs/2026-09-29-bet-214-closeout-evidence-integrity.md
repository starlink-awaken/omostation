---
schema_version: specification/v1
spec_version: 1.0.0
title: BET-212 closeout evidence integrity repair
bet_id: BET-Y2Q4-T10-214
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-29
---
# BET-Y2Q4-T10-214 — BET-212 Closeout Evidence Integrity Repair

## 1. Problem (measured on `origin/main` after #4544 / #4553)

`BET-Y2Q4-T10-212` is `status: done` on main, and its closeout receipt
`docs/reports/2026-09-29-projection-plane-phase2-pr3-closeout.md` carries three defects that make
the accepted evidence unusable by the next reader:

1. **Six report receipts are stale.** The ledger records `sha256:0fd5034b…` ×5
   (`engineering.tests/diff/rollback`, `operational.live_canary/fresh_receipt`) and
   `sha256:0e3c4bcb…` ×1 (`operational.cleanup`), while the committed report's content digest is
   `sha256:bd2ed573…`. None of the six matches the file it points at.
2. **The recorded `verify` command is not runnable as written.**
   `uv run --with pyyaml python -m pytest tests/unit/test_projection_reader_resolution.py -q`
   fails with `No module named pytest`; after adding `--with pytest` it still needs `projects/omo`
   initialized, because three cases (`test_omo_projection_path_resolves_registry_and_legacy_fallback`,
   `test_omo_projection_path_does_not_fallback_when_registry_omits_name`,
   `test_omo_doctor_does_not_fail_when_health_projection_is_not_generated`) put `projects/omo/src`
   on `sys.path`.
3. **A dead section anchor.** `verify[0].expect` cites "PR-3 closeout report §10"; the report's last
   section is §9. The intended anchor is §9 bullet 8.

No **gate** detects class 1: `bet-ledger.py lint` checks receipt path existence
(`PHANTOM_REPORT_PATH`, warning) and future-dated paths (`FUTURE_DATED_REPORT_PATH`, error) but never
compares a receipt `sha256` against file content, and `.github/workflows/bet-done-gate.yml` hard-fails
only on `BASE_LEDGER_UNREADABLE` / `BET_DONE_*` / `META_TOTAL_BETS_DRIFT`. The detector itself already
ships: `bin/ssot/sync-bet-digests.py` compares exactly those keys against file bytes, fixes them by
`sha256:[0-9a-f]{64}` literal replace only (refuses conflicting replacements; its docstring forbids a
whole-file `yaml.dump` because that "previously corrupted the ledger"), and is pinned by
`tests/test_sync_bet_digests_integrity.py` (3 passed on this checkout). What is missing is wiring: its
registry entry `bin/_registry/scripts/governance/sync-bet-digests.yaml` has `triggers: []` and there is
no call site in `.github/`, `Makefile`, or `.omo/_truth/registry/`. Running it as `--report` on this
checkout measures **1,882 mismatches across 329 bets** (`BET-Y2Q4-T10-212`: 0; `BET-Y2Q4-T10-213`: 0),
which is why the backlog must be registered before the check is turned on — see G1.

## 2. Contract

The repaired state must satisfy, reproducibly:

- C1 — every `receipt://` key in `BET-Y2Q4-T10-212.completion_evidence` equals the SHA-256 of the
  file bytes at `receipt://` path, computed after the last edit of that file. Verification is
  per-key comparison of `shasum -a 256` output (file bytes, **not** `git hash-object`, which hashes
  the `blob <len>\0` header and can never equal a content digest).
- C2 — `BET-Y2Q4-T10-212.verify[0].cmd` is runnable verbatim from a checkout with all submodules
  initialized, and the prerequisite ("`projects/omo` initialized") is stated in the same entry.
- C3 — no textual reference in the ledger points at a report section that does not exist.
- C4 — §9 bullet 6 of the report (the workflow-run chronology corrected by #4544) is preserved
  byte-for-byte; this BET does not rewrite another agent's factual correction.
- C5 — `BET-Y2Q4-T10-212`'s `status`, `done_at`, `accepted_specifications` bytes/digest and
  retrospective are unchanged.
- C6 — the report gains a §9 bullet recording: how the closeout actually landed (#4544), the three
  repaired defects, the measurements taken after repair, and the wiring gap that left class 1 undetected.
- C7 — every command written into a ledger `verify[].cmd` by this bet is executed verbatim, from this
  checkout, before it is written. This clause exists because class 2 recurred while registering this
  repair: the first draft of `BET-Y2Q4-T10-214.verify[0]` was
  `uv run --with pyyaml python -m pytest tests/test_sync_bet_digests_integrity.py -q`, which fails with
  `No module named pytest`; running the drafted commands verbatim caught it, and the recorded command
  now passes (`3 passed`).

## 3. Boundary

Out of scope, and a stop condition rather than a judgement call:

- **`BET-Y2Q4-T10-213`'s completion evidence.** Its five report receipts pin the pre-repair digest
  `sha256:bd2ed573…` and therefore become stale the moment this BET edits the report. They are not
  touched here: T10-212's own `circuit_breaker` lists "backfill of lifecycle evidence for any other
  bet" as a stop condition, and re-pointing a third party's evidence is exactly that. Registered
  below as a follow-up with the exact values needed.
- No new CI check, no change to `bin/plan/bet-ledger.py`, no change to any `.github/workflows/**`.
- No edit to `.omo/state/**` or `BRIEF.md`; generated state does not ride along in a docs PR.

## 4. Registered follow-ups (not fixed by this BET)

- **G1 receipt digests are detected but unwired.** `bin/ssot/sync-bet-digests.py` already performs the
  comparison and its safe repair path; no gate calls it (`triggers: []`, zero call sites), so today a
  report referenced by N BETs costs N×4 digest recomputations per edit, silently. Switching the
  existing detector on repo-wide would red CI on day one against the measured 1,882-mismatch backlog,
  so the wiring BET needs (a) a diff-scoped check over only the receipt keys a PR touches, (b)
  registration of the backlog in `.omo/_truth/registry/gate-known-debt.yaml` with owner and expiry, and
  (c) a decision on whether receipts pin an immutable ref (`git://<commit>:<path>`, already skipped by
  the detector so it creates no new comparison debt) instead of a working-tree content digest.
- **G2 stale receipts already created.** `BET-Y2Q4-T10-213` needs its 5 `receipt://docs/reports/…`
  keys re-pointed from `sha256:bd2ed573…` to this BET's post-repair report digest.
- **G3 `#`-silent truncation.** A `done_when` / `non_goals` scalar containing " #" is parsed as a
  comment and loses the remainder with no error (observed on T10-213's registration; repaired by
  quoting in #4553). New entries must quote such scalars and re-read them parsed.
- **G4 D0 cannot express deletion deliverables.** `bet-ledger.py complete` requires every
  `write_surfaces` literal to resolve in the root index, so a successful untracking BET is failed by
  the gate for the evidence of its own success (see report §9 bullet 3).
