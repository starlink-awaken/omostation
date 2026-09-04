---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-29
last-reviewed: 2026-08-28
bet_id: BET-Y1Q3-T10-48
type: ssot
last_updated: 2026-09-03
---

# Resident ledger read-status contention repair

## Problem

`make resident-status` repeatedly reports `OperationalError: database is locked`
for `runtime/omo/event-ledger.sqlite3` while the resident daemon is active.
SQLite `quick_check` remains `ok`, so the current evidence indicates connection
or initialization contention rather than a corrupt database.

## Goal

Make the resident status ledger probe a bounded, read-only observation that
survives transient cross-process SQLite contention and reports a truthful
degraded result when the bounded retry budget is exhausted.

## Contract

- Reuse `LedgerBroker` and its existing `BUSY_TIMEOUT_MS` policy; do not add a
  second ledger, writer, lock registry, scheduler, or checkpoint path.
- Retry only `LedgerBroker.connect`/verification on `sqlite3.OperationalError`
  matching a lock/busy condition, with a bounded total budget.
- Always close every successfully opened broker; never issue WAL checkpoints,
  schema mutations, writes, process signals, or launchd changes from status.
- Preserve exit semantics: healthy status exits 0; exhausted contention or
  integrity failure exits non-zero and identifies the observed failure class.
- Add deterministic tests for transient lock recovery, exhausted lock failure,
  broker close, and non-lock errors. No host database is used by tests.

## Non-goals

- No database migration, WAL deletion/checkpoint, force unlock, kill, unload,
  service restart, or host configuration change.
- No claim that resident production topology or personal value is proven.

## Acceptance

1. The status probe returns recovered after a transient bounded lock.
2. A persistent lock returns degraded without mutation and without leaking a
   connection.
3. Existing resident status and ledger regression tests remain green.
4. A read-only host check records before/after database and process evidence;
   host state is not modified by this BET.
