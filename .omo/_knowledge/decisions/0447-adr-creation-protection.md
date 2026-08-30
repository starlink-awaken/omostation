---
id: ADR-0447
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-08-30
---

# ADR-0447: ADR Creation Protection

- **Status**: ACCEPTED
- **Date**: 2026-08-30
- **Authors**: governance-team
- **Supersedes**: (none)
- **Superseded by**: (none)

## Context and Problem Statement

ADR numbering is a globally incrementing sequence defined in `.omo/_knowledge/decisions/README.md`. Concurrent agents creating ADRs simultaneously can collide on the same number, producing duplicate files and INDEX entries. Historical incidents (ADR-0405 renumbered to avoid ADR-0401 collision, ADR-0396 vs ADR-0391 duplication) show this is not theoretical.

The problem: how to guarantee that an agent claiming an ADR number does not race with another agent claiming the same number, while keeping the creation flow lightweight enough for autonomous use.

## Decision Drivers

* ADR numbers must be unique and monotonically incrementing
* Concurrent agents must not produce duplicate ADR numbers
* The claim must be visible to other agents before content is written (reserve-then-write)
* The mechanism must not require a central server or human gatekeeper for every ADR
* Stale claims (agent crashes after reserving) must be reclaimable

## Considered Options

1. **Atomic file creation (O_CREAT|O_EXCL)** — `open(..., O_CREAT|O_EXCL)` on a placeholder file reserves the number atomically
2. **Git-based claim (commit a placeholder)** — commit an empty ADR file to a branch, rely on git's atomic commit
3. **Central ADR allocator script** — a single script that hands out numbers sequentially under a lock
4. **INDEX.md row lock** — lock the INDEX.md file, read max number, write new row, unlock

## Decision Outcome

**Chosen option: "Atomic file creation (O_CREAT|O_EXCL)", because it is a single syscall that either succeeds or fails, making it race-free by kernel guarantee. The placeholder file doubles as the reservation marker.**

### Consequences

* Good: Zero dependencies, kernel-level atomicity, no race window
* Good: The placeholder file itself signals "reserved" to other agents
* Good: Stale placeholders are detectable by checking frontmatter `status: proposed` and age
* Bad: An agent that crashes after creating the placeholder leaves an empty ADR (mitigated by stale sweep)
* Bad: Requires agents to use the helper script, not raw `write`

### Confirmation

```bash
# Verify the ADR claim helper exists
test -x bin/ssot/adr-claim.sh && echo "claim helper present"

# Test concurrent claim (two agents racing for the same number)
bash tests/integration/adr-claim-concurrent-smoke.sh

# Verify exactly one winner
test $(ls .omo/_knowledge/decisions/0NNN-placeholder-*.md 2>/dev/null | wc -l) -eq 1
```

## Pros and Cons of the Options

### Atomic file creation (O_CREAT|O_EXCL)

* Good: Single syscall, kernel guarantees atomicity, no lock window
* Good: Placeholder file is self-documenting (other agents see the reservation)
* Bad: Agent must call the helper, not write directly
* Bad: Stale placeholders need periodic sweep

### Git-based claim

* Good: Leverages existing git infrastructure
* Bad: Commit latency (seconds) vs file creation (microseconds)
* Bad: Branch-based claims require merge coordination, adding complexity

### Central ADR allocator

* Good: Simple sequential logic
* Bad: Single point of failure, bottleneck under concurrent load
* Bad: Requires a long-running process or a lock around the allocator

### INDEX.md row lock

* Good: Co-locates claim with the index
* Bad: INDEX.md is large, locking it blocks all reads during the claim
* Bad: Parsing max number from a markdown table is fragile

## Rollback

If the atomic file creation approach causes issues (e.g., filesystem without O_EXCL support):

1. Fall back to the directory-based mutex pattern from ADR-0441: `mkdir .omo/_knowledge/decisions/.adr-claim-lock` before reading the max number and creating the file.
2. The placeholder file approach stays the same, only the reservation mechanism changes.
3. Re-run the concurrent claim smoke test.

## References

* `.omo/_knowledge/decisions/README.md` — ADR naming rules and status machine
* `bin/ssot/adr-claim.sh` — the atomic claim helper
* `tests/integration/adr-claim-concurrent-smoke.sh` — concurrent claim verification
* ADR-0405: historical renumbering to avoid collision
