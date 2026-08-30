---
id: ADR-0444
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-08-30
---

# ADR-0444: High-Frequency File Write Lock

- **Status**: ACCEPTED
- **Date**: 2026-08-30
- **Authors**: governance-team
- **Supersedes**: (none)
- **Superseded by**: (none)

## Context and Problem Statement

Several governance artifacts are written at high frequency by multiple agents: `.omo/_control/governance-data.json`, `.omo/state/system.yaml` projections, and dashboard snapshot files. Concurrent uncoordinated writes produce torn JSON, lost updates, and intermittent parse failures that cascade into gate false-negatives. ADR-0128 addressed state generation concurrency at the architecture level, but the file-level write race remained unresolved for high-frequency producers.

The problem: how to serialize writes to high-frequency shared files without introducing per-file lock overhead that degrades throughput below the production cadence.

## Decision Drivers

* Torn writes must not produce unparseable JSON/YAML that breaks downstream gates
* Last-writer-wins semantics are acceptable for projection files (they are regenerated frequently)
* The lock must be cheap enough that 10+ agents writing every few seconds does not cause visible latency
* The mechanism must degrade gracefully under contention (timeout, not deadlock)
* It must not require a long-running daemon

## Considered Options

1. **Atomic write via temp file + rename** — write to `.tmp`, then `rename(2)` (atomic on POSIX)
2. **Per-file flock with bounded timeout** — `flock` on each target file with a 5-second timeout
3. **Write-through queue (single writer process)** — all writes go through a Unix socket to a single writer
4. **SQLite for projection state** — replace JSON/YAML files with a SQLite database

## Decision Outcome

**Chosen option: "Atomic write via temp file + rename", because it eliminates torn writes at the filesystem level without any lock contention, and last-writer-wins is the correct semantic for frequently regenerated projections.**

### Consequences

* Good: Zero lock contention, no waiting, no deadlocks
* Good: Torn writes are impossible (rename is atomic on POSIX local filesystems)
* Good: Readers always see a complete file (old or new, never partial)
* Bad: Last writer wins, so a slower agent's update can overwrite a faster agent's (acceptable for projections)
* Bad: Does not prevent semantic conflicts (two agents writing different but incompatible states) — requires application-level coordination

### Confirmation

```bash
# Verify the atomic write helper exists
test -x bin/ssot/atomic-write.sh && echo "helper present"

# Concurrent write smoke test (20 agents, 50 writes each, no parse errors)
bash tests/integration/atomic-write-concurrent-smoke.sh

# Verify the output file is valid JSON after concurrent writes
python3 -c "import json; json.load(open('.omo/_control/governance-data.json'))" && echo "valid JSON"
```

## Pros and Cons of the Options

### Atomic write via temp file + rename

* Good: No locks, no waiting, impossible to produce torn files
* Good: Works for any file format (JSON, YAML, text)
* Bad: Last-writer-wins only, no merge semantics
* Bad: Requires writers to use the helper, not raw `>` redirect

### Per-file flock with bounded timeout

* Good: Provides mutual exclusion, prevents lost updates
* Bad: Lock contention under high frequency adds latency
* Bad: Timeout failures require retry logic in the caller
* Bad: Does not prevent torn writes if a writer crashes mid-write (lock releases, partial file remains)

### Write-through queue (single writer process)

* Good: Full serialization, no lost updates, no torn writes
* Bad: Requires a long-running daemon (new failure mode)
* Bad: Single point of failure, throughput bottleneck
* Bad: Adds inter-process communication overhead

### SQLite for projection state

* Good: ACID transactions, queryable, built-in concurrency
* Bad: Replaces file format, breaking existing `jq`/`grep`/`cat` pipelines
* Bad: Overkill for files that are regenerated every few seconds

## Rollback

If the atomic rename approach causes issues (e.g., cross-filesystem rename failure):

1. Detect cross-filesystem cases by checking if the temp file and target are on the same mount point.
2. For cross-filesystem cases, fall back to per-file flock (Option 2) with a bounded timeout.
3. The helper script `bin/ssot/atomic-write.sh` can implement both paths transparently.
4. Re-run the concurrent write smoke test to confirm no parse errors.

## References

* ADR-0128: multi-agent concurrent state generation architecture
* `bin/ssot/atomic-write.sh` — the atomic write helper
* `tests/integration/atomic-write-concurrent-smoke.sh` — concurrent write verification
* `.omo/_control/governance-data.json` — primary high-frequency target
