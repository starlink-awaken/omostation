---
name: omo-audit-baseline
description: "Governance audit baseline workflow for the omostation workspace. Run omo audit, check results, commit governance data. Use when syncing governance state or running audit checks."
---

# OMO Audit Baseline — Governance State Sync

The most repeated governance workflow in this workspace (22+ occurrences across sessions). Run the omo audit baseline, verify results, and commit governance data.

## When To Use

- After governance state changes (task lifecycle, debt updates, phase transitions)
- Before committing `.omo/` or `.omo/_knowledge/` changes
- When CI shows governance drift or audit failures
- As part of the RISE cycle (governance-phase-orchestrator skill)

## The Workflow

### Step 1: Run Audit Baseline

```bash
cd /Users/xiamingxing/Workspace
uv run --no-sync python -m omo.cli logs audit \
  --baseline-init /Users/xiamingxing/Workspace/.omo/_knowledge/_audit_baseline.json \
  2>&1 | tail -3
```

**Note**: The first run may fail if the baseline file doesn't exist. The `--baseline-init` flag creates it on first run.

If the command fails, retry with a different path (common path drift):

```bash
cd /Users/xiamingxing/Workspace/projects/omo
uv run --no-sync python -m omo.cli logs audit \
  --baseline-init /Users/xiamingxing/Workspace/.omo/_knowledge/_audit_baseline.json \
  2>&1 | tail -3
```

### Step 2: Sync OMO State

```bash
cd /Users/xiamingxing/Workspace
python3 scripts/sync_omo_state.py 2>&1
```

Or with check mode:

```bash
python3 scripts/sync_omo_state.py --check 2>&1
```

### Step 3: Run Governance Check

```bash
cd /Users/xiamingxing/Workspace
uv run --no-sync python -m omo.cli governance audit 2>&1 | tail -5
```

### Step 4: Commit Governance Data

Stage only governance-related files:

```bash
cd /Users/xiamingxing/Workspace
git add .omo/_knowledge/management/append-only-log-pattern-*.json \
        .omo/_knowledge/_audit_baseline.json \
        .omo/change-log/mutations.jsonl
git commit -m "chore(governance): audit baseline sync"
```

**Important**: Do not `git add .omo/` broadly — only add specific changed files. The `.omo/` directory contains both governed state and local runtime data.

### Step 5: Verify

```bash
git status --short | wc -l  # Should be ≤ 50 (commit closure rule)
git log --oneline -3        # Verify commit landed
```

## Common Failure Modes

| Failure | Cause | Fix |
|---------|-------|-----|
| `FileNotFoundError: _audit_baseline.json` | First run | Run with `--baseline-init` flag |
| `omo.cli logs audit` exit 1 | Path drift | Try from `projects/omo/` instead of root |
| `sync_omo_state.py` no output | Already in sync | Normal — check with `--check` flag |
| Governance score < 100 | Missing state | Run full `omo governance` to diagnose |

## Integration with RISE Cycle

This workflow maps to the **E (Execute)** step of the governance-phase-orchestrator RISE cycle:

```bash
# R step: check current state
git status --short | wc -l
bin/mof-drift 2>&1 | tail -5

# E step: run this workflow
# ... (audit baseline + sync + commit)

# C step: verify
omo governance 2>&1 | tail -5
git status --short | wc -l
```

## Anti-patterns

- **DON'T** `git add .omo/` — too broad, picks up local runtime data
- **DON'T** skip the sync step — audit baseline without sync creates drift
- **DON'T** commit without verifying governance score first
