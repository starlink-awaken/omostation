# Submodule Sync SOP

> Status: active | Lifecycle: contract | Owner: governance-team | Last-reviewed: 2026-09-04

## Overview

Standard operating procedure for synchronizing submodule pointers (gitlinks) in the workspace. This SOP covers drift detection, resolution, and prevention.

## When to Use

- After squash merge that may create dangling SHA (P97 pattern)
- When local submodule HEAD differs from the superproject gitlink
- During pre-push validation to prevent pushing inconsistent state
- After parallel agent operations that may modify submodule state

## Drift Detection

### Quick Check

```bash
# Detect drift between local HEAD and gitlink
python3 bin/ssot/submodule-reachability-gate.py --source index --drift-check

# JSON output for CI integration
python3 bin/ssot/submodule-reachability-gate.py --source index --drift-check --json
```

### Understanding Drift

**Drift** occurs when the local checked-out commit in a submodule differs from the gitlink recorded in the superproject index. Common causes:

1. **P97 squash-SHA dangling**: After squash merge, the original commit SHA is no longer in the submodule's history
2. **Local uncommitted changes**: Developer modified submodule locally without committing
3. **Parallel agent operations**: Multiple agents checking out different submodule states

### Drift Resolution

#### Option 1: Auto Fast-Forward (Recommended)

If the gitlink SHA is a descendant of the local HEAD, fast-forward is safe:

```bash
# Attempt auto fast-forward (circuit_breaker: stops on failure)
python3 bin/ssot/submodule-reachability-gate.py --source index --drift-check --auto-fast-forward
```

**Circuit Breaker**: The fast-forward will refuse to proceed if:
- The submodule has uncommitted changes
- The gitlink SHA is not a descendant of local HEAD (would require force)
- Fetch from origin fails

#### Option 2: Manual Resolution

```bash
cd projects/<submodule>
git fetch origin
git checkout <gitlink-sha>  # or git merge origin/main
cd ../..
git add projects/<submodule>
git commit -m "chore(submodule): sync <submodule> to <sha>"
```

#### Option 3: Reset to Gitlink

When auto fast-forward fails but you need to match the gitlink:

```bash
cd projects/<submodule>
git fetch origin
git reset --hard <gitlink-sha>  # WARNING: discards local changes
cd ../..
git add projects/<submodule>
```

## Prevention

### Pre-push Validation

Add to pre-push hook or CI:

```bash
# Full reachability check
python3 bin/ssot/submodule-reachability-gate.py --source index --fetch

# With drift detection
python3 bin/ssot/submodule-reachability-gate.py --source index --drift-check
```

### Incremental Mode

For faster checks on specific changes:

```bash
# Only check submodules changed since origin/main
python3 bin/ssot/submodule-reachability-gate.py --source index --changed-from origin/main
```

## Integration with Agent Workflow

### Claiming Submodule Changes

When claiming submodule-related paths:

```bash
# Generate affected receipt
python3 bin/gac/affected-graph.py --changed-projects workspace-root --output affected-receipt.json --json

# Claim with receipt
uv run --with pyyaml python bin/agent-workflow.py claim <run-id> --path projects/<submodule> --affected-hash affected-receipt.json
```

### Verify After Changes

```bash
uv run --with pyyaml python bin/agent-workflow.py verify <run-id> --from-diff --execute
```

## Troubleshooting

### "submodule not initialized"

```bash
git submodule update --init projects/<submodule>
```

### "fetch failed"

Check network connectivity and origin remote configuration:

```bash
git -C projects/<submodule> remote -v
git -C projects/<submodule> fetch origin
```

### "gitlink SHA is not a descendant of local HEAD"

This means auto fast-forward is impossible. You need manual resolution:

```bash
cd projects/<submodule>
git log --oneline HEAD..<gitlink-sha>  # See what commits are missing
git merge <gitlink-sha>  # Or cherry-pick specific commits
```

## References

- [Submodule Gitlink Drift Guard Spec](../superpowers/specs/2026-09-04-submodule-gitlink-drift-guard-spec.md)
- [Submodule PR Strategy](./SUBMODULE-PR-STRATEGY.md)
- [Git Worktree Policy](../../AGENTS.md#0-worktree-policy-mandatory)
