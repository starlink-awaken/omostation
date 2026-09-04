---
type: ephemeral
created: 2026-09-03
---

# Resident ledger read-status repair report

## Scope

`BET-Y1Q3-T10-48` repairs only the resident status read probe. It does not
modify the SQLite database, WAL files, launchd services, or resident processes.

## Before

The host `make resident-status` probe repeatedly returned degraded health with
`OperationalError: database is locked` while the resident orchestrator held the
ledger open. A direct SQLite read-only `PRAGMA quick_check` returned `ok`, so
the evidence pointed to contention rather than corruption.

## Change

OMO `resident/status.py` now retries only lock/busy `sqlite3.OperationalError`
within a fixed three-attempt budget. Each opened broker is closed in a
`finally` block. Non-lock errors are not retried; exhausted lock contention
remains degraded and reports `retry budget exhausted`.

## Verification

- OMO resident/status + event-ledger regression: `122 passed`.
- Child PR #110 merged at
  `b170d95ae509499f2b3cfa762c944d7609a7a284`.
- Root PR #2501 merged at
  `69370b508e8e27758c1663104446a09182e3ae89`.
- Host probe with the repaired code: degraded with
  `database is locked; retry budget exhausted` after three bounded attempts.
- Ledger before/after: size `151552`, mtime and SHA-256
  `121e211ea159baef0f018675b8fe5a7c43efe81823863344eab3e532e5bc26b9`;
  unchanged.

The host remains degraded because another resident writer keeps the database
contended. The repair makes that state observable and bounded; it does not
claim to have removed the writer or prove production topology.
