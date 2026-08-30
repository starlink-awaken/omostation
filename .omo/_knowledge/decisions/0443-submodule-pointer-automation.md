---
id: ADR-0443
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-08-30
---

# ADR-0443: Submodule Pointer Automation

- **Status**: ACCEPTED
- **Date**: 2026-08-30
- **Authors**: governance-team
- **Supersedes**: (none)
- **Superseded by**: (none)

## Context and Problem Statement

Submodule pointer updates require a three-step dance: commit inside the submodule, push from the submodule, then commit the pointer in the parent repo. Agents frequently skip steps or execute them out of order, producing dangling pointers, failed parent commits (`is in submodule` error), or orphaned submodule commits. ADR-0382 added rewind detection, but the root cause, manual uncoordinated pointer updates, remained.

The problem: how to make submodule pointer updates atomic and foolproof so that an agent cannot produce a half-completed pointer transaction.

## Decision Drivers

* Submodule pointer updates must be all-or-nothing (commit + push + parent commit)
* The workflow must be idempotent (re-running after a partial failure completes the missing steps)
* It must detect and refuse to overwrite a pointer that has advanced beyond the agent's submodule HEAD
* The mechanism must work with the existing git submodule infrastructure, not replace it
* Verification must confirm the parent repo pointer matches the submodule remote HEAD

## Considered Options

1. **Transaction script (submodule-pointer-transaction.sh)** — a single script that performs all three steps with pre/post checks and rollback
2. **Git submodule absorbgitdirs + custom hook** — restructure submodules and use hooks to enforce the dance
3. **Post-commit hook on submodule** — auto-push and auto-update parent on every submodule commit
4. **Make target wrapper** — `make submodule-update SUB=<name>` that wraps the three steps

## Decision Outcome

**Chosen option: "Transaction script (submodule-pointer-transaction.sh)", because it provides explicit pre-conditions, atomic execution, and idempotent recovery in a single auditable artifact.**

### Consequences

* Good: Single entry point eliminates the "forgot to push" and "forgot parent commit" failure modes
* Good: Idempotent design means re-running after a crash completes the remaining steps
* Good: Pre-check detects stale pointer (submodule remote advanced) and refuses to clobber
* Bad: Agents must use the script instead of raw git commands (enforced by AGENTS.md guidance)
* Bad: The script adds one layer of indirection over raw git

### Confirmation

```bash
# Verify the transaction script exists
test -x bin/ssot/submodule-pointer-transaction.sh && echo "script present"

# Dry-run on a clean submodule (should report no-op)
bash bin/ssot/submodule-pointer-transaction.sh --dry-run --submodule projects/ecos

# Full transaction smoke test on a test submodule
bash tests/integration/submodule-pointer-smoke.sh

# Verify parent pointer matches submodule remote HEAD
bash bin/ssot/submodule-pointer-transaction.sh --verify --submodule projects/ecos
```

## Pros and Cons of the Options

### Transaction script

* Good: Explicit pre/post conditions, idempotent, auditable
* Good: Can be called from Make targets and agent workflows
* Bad: One more script to maintain
* Bad: Does not prevent an agent from bypassing it with raw git

### Git submodule absorbgitdirs + custom hook

* Good: Enforced at the git level, cannot be bypassed
* Bad: Restructuring submodule layout is invasive and risky
* Bad: Hooks fire on every commit, including WIP commits that should not update the pointer

### Post-commit hook on submodule

* Good: Fully automatic, no agent action required
* Bad: Auto-pushing on every commit is dangerous (WIP commits, broken states)
* Bad: Hook runs in submodule context, cannot easily commit the parent pointer

### Make target wrapper

* Good: Familiar interface for developers
* Bad: Make is not available in all agent environments
* Bad: Make targets are thin wrappers, still allow raw git bypass

## Rollback

If the transaction script introduces regressions:

1. Disable the script by removing it from the agent workflow `claim` path.
2. Fall back to manual three-step process documented in AGENTS.md §6.
3. The script does not modify git internals, so removing it has no side effects on existing repos.
4. Re-enable after fixing the script and re-running the smoke test.

## References

* ADR-0382: submodule rewind detection (CR-SUBMODULE-REWIND)
* `bin/ssot/submodule-pointer-transaction.sh` — the transaction script
* `tests/integration/submodule-pointer-smoke.sh` — transaction verification
* `AGENTS.md` §6 — submodule commit three-step guidance
