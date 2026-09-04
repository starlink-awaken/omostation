# P99 — Pre-commit Hook Install Hygiene

**Pattern observed**: 2026-09-04 in BET-Y1Q4-HITL-01 (PR #3077).

## Problem

`.githooks/pre-commit` is the canonical source. `.git/hooks/pre-commit` is an install-time copy (created by `make install-hooks`). If the source is updated with new features but the install copy is stale, the new features are silently bypassed on local commits.

## Symptom

Pre-commit hook rejects commit with "not a fast-forward" error, **even though** the same fingerprint is correctly recorded in `gate-known-debt.yaml`:

```
[submodule-guard] ❌ projects/cockpit 指针变更被拒绝: 不是 fast-forward
```

But `.githooks/pre-commit` has the new logic to honor known-debt fingerprints.

## Root Cause

`.git/hooks/pre-commit` is **out of sync** with `.githooks/pre-commit`. The `gitlink-ancestry|submodule-ancestry-gate` exemption logic was added to `.githooks/pre-commit` but the active install at `.git/hooks/pre-commit` predates it.

## Fix Pattern

Sync the hooks before relying on new features:

```bash
# Option 1: Make target
make install-hooks

# Option 2: Manual copy
cp .githooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

## When to Apply

- BEFORE relying on new pre-commit features (e.g., `gitlink-ancestry` known-debt exemption)
- After `git pull` that updates `.githooks/`
- When local hook behavior diverges from `.githooks/` source
- **At the start of any new worktree** (hooks may not be auto-installed)

## Verification

```bash
# Compare versions
diff .githooks/pre-commit .git/hooks/pre-commit
# Should be empty (no diff)

# Or check for specific feature
grep "gitlink-ancestry" .git/hooks/pre-commit
# Should find the pattern
```

## Related

- `.githooks/pre-commit` (canonical source)
- `Makefile` `install-hooks` target
- `gate-known-debt.yaml` (consumed by pre-commit)
- `submodule-ancestry-gate` (the check that depends on the new logic)
