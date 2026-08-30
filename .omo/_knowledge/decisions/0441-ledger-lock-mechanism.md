---
id: ADR-0441
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-08-30
---

# ADR-0441: Ledger Lock Mechanism

- **Status**: ACCEPTED
- **Date**: 2026-08-30
- **Authors**: governance-team
- **Supersedes**: (none)
- **Superseded by**: (none)

## Context and Problem Statement

The events ledger (`.omo/_data/events.jsonl`) is a shared append-only log that multiple agents write to concurrently. Without coordination, concurrent writers produce interleaved or lost entries. ADR-0209 and ADR-0212 documented history gaps and trim-like symptoms caused by uncoordinated access. The ledger is a governance truth source, so silent data loss directly degrades auditability.

The core problem: how to serialize ledger appends across concurrent agents without introducing a heavyweight external dependency or a single-process bottleneck that defeats the multi-agent architecture.

## Decision Drivers

* Concurrent agents must not lose ledger entries
* The mechanism must work on macOS and Linux without extra services
* Lock contention must be bounded so throughput stays acceptable under normal load
* The lock must auto-release if an agent crashes mid-write (no zombie locks)
* Verification must be cheap and runnable in CI

## Considered Options

1. **File-based advisory lock (flock / fcntl)** — atomic `flock(2)` on a sidecar `.lock` file, released on process exit or fd close
2. **Directory-based mutex (mkdir atomicity)** — `mkdir` is atomic on POSIX, use a lock directory as a mutex
3. **SQLite WAL mode** — replace JSONL with a single-table SQLite database relying on WAL serialization
4. **Redis / external coordinator** — introduce a networked lock service

## Decision Outcome

**Chosen option: "File-based advisory lock (flock)", because it is zero-dependency, auto-releases on crash, and integrates cleanly with the existing append-only JSONL format.**

### Consequences

* Good: No new dependencies, works on macOS and Linux, crash-safe by fd lifecycle
* Good: Existing JSONL readers need no changes
* Bad: NFS or network filesystems may not honor flock semantics (acceptable, ledger is local)
* Bad: A process that forks without closing the lock fd can leak the lock (mitigated by CLOEXEC)

### Confirmation

```bash
# Verify the lock wrapper exists and is executable
test -x bin/ssot/ledger-append.sh && echo "wrapper present"

# Run a concurrent append smoke test (10 parallel writers, 100 entries each)
bash tests/integration/ledger-concurrent-smoke.sh

# Verify no lost entries (expect count == 1000)
wc -l /tmp/ledger-smoke.jsonl
```

## Pros and Cons of the Options

### File-based advisory lock (flock)

* Good: Zero dependencies, kernel-managed lifecycle, auto-release on crash
* Good: Bounded wait via `flock --timeout` prevents indefinite blocking
* Bad: Requires a wrapper script or library call around every append
* Bad: Not portable to Windows (acceptable, workspace is macOS/Linux)

### Directory-based mutex (mkdir)

* Good: Pure POSIX atomicity, no fd lifecycle concerns
* Bad: Stale lock directories on crash require manual cleanup or stale detection logic
* Bad: Slower than flock under high contention (mkdir + rmdir vs single syscall)

### SQLite WAL mode

* Good: Built-in serialization, queryable, schema enforcement
* Bad: Replaces the JSONL format, breaking existing tail/grep/jq pipelines
* Bad: WAL checkpointing adds complexity under concurrent load

### Redis / external coordinator

* Good: Cross-machine coordination, rich semantics
* Bad: Introduces a network dependency and a new failure mode
* Bad: Overkill for single-host multi-agent coordination

## Rollback

If the flock mechanism proves unreliable on a target filesystem:

1. Switch the wrapper to the directory-based mutex (Option 2) by replacing `flock` with `mkdir`/`rmdir` in `bin/ssot/ledger-append.sh`.
2. No JSONL format change required, so readers stay unaffected.
3. Re-run the concurrent smoke test to confirm zero lost entries.

## References

* ADR-0209: ledger events.jsonl trim investigation
* ADR-0212: ledger history gap (not physical trim) clarification
* `bin/ssot/ledger-append.sh` — the lock wrapper implementation
* `tests/integration/ledger-concurrent-smoke.sh` — concurrent append verification
