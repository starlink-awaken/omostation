---
name: worktree-ci-isolate
description: "Create isolated git worktrees for CI fixes and parallel development. Init submodules, work in isolation, clean up when done. Use when fixing CI issues or needing conflict-free parallel work."
---

# Worktree CI Isolation — Parallel Development Workflow

The agent isolation pattern for this workspace (10+ occurrences). Create an isolated worktree from `origin/main`, initialize needed submodules, work in isolation, then clean up.

## When To Use

- Fixing CI failures without polluting the main working tree
- Parallel development on multiple features simultaneously
- Testing changes that might conflict with concurrent agent work
- Any work that needs a clean `origin/main` baseline

## The Workflow

### Step 1: Create Worktree

```bash
cd /Users/xiamingxing/Workspace
git fetch origin 2>&1 | tail -1
git worktree add ws-ci-roundN -b work/ci-roundN origin/main 2>&1 | tail -2
```

**Naming convention**: `ws-<purpose>-<round>` (e.g., `ws-ci-round12`, `ws-isolation-pilot-2026`)

### Step 2: Initialize Required Submodules

Only init the submodules you need (not all — saves time):

```bash
cd /Users/xiamingxing/Workspace/ws-ci-roundN

# For ecos/omo work:
git submodule update --init projects/ecos projects/omo scripts 2>&1 | tail -3

# For cockpit work:
git submodule update --init projects/cockpit projects/agora 2>&1 | tail -3

# For l4-kernel work:
git submodule update --init projects/l4-kernel 2>&1 | tail -3
```

### Step 3: Work in Isolation

All edits happen inside the worktree:

```bash
cd /Users/xiamingxing/Workspace/ws-ci-roundN
# ... make changes, run tests, commit ...
```

**Key rules**:
- Never edit files in the main workspace from a worktree session
- Each worktree has its own branch — commits are isolated
- Tests run against the worktree's code, not the main workspace

### Step 4: Verify Before Cleanup

```bash
cd /Users/xiamingxing/Workspace/ws-ci-roundN
git status --short | wc -l  # Should be 0 if committed
git log --oneline -3        # Verify commits landed
```

### Step 5: Clean Up

```bash
cd /Users/xiamingxing/Workspace

# Remove worktree
git worktree remove --force ws-ci-roundN 2>&1

# Delete branch
git branch -D work/ci-roundN 2>&1
```

**Bulk cleanup** (when multiple stale worktrees exist):

```bash
cd /Users/xiamingxing/Workspace
for wt in ws-ci-round12 ws-ci-round13 ws-ci-round14; do
  echo "Removing: $wt"
  git worktree remove --force "$wt" 2>&1 | sed 's/^/  /'
  git branch -D "work/$(basename $wt | sed 's/ws-//')" 2>&1 | sed 's/^/  /'
done
```

### Step 6: Push and Create PR (If Applicable)

```bash
cd /Users/xiamingxing/Workspace
git push origin work/ci-roundN 2>&1 | head -5
gh pr create --base main --head work/ci-roundN \
  --title "fix: <description>" \
  --body "## Summary\n- ..."
```

## Naming Conventions

| Pattern | Purpose |
|---------|---------|
| `ws-ci-roundN` | CI fix iterations |
| `ws-isolation-pilot-*` | Isolation experiments |
| `ws-phaseN-*` | Phase-specific work |
| `work/<name>` | Branch naming |

## Submodule Init Strategy

| Work type | Submodules needed |
|-----------|-------------------|
| ecos/omo changes | `projects/ecos`, `projects/omo`, `scripts` |
| cockpit changes | `projects/cockpit`, `projects/agora` |
| l4-kernel changes | `projects/l4-kernel` |
| governance changes | `projects/omo`, `scripts` |
| root docs only | None |

**Do not** `git submodule update --init` without specifying paths — it initializes everything and wastes time.

## Common Pitfalls

| Pitfall | Consequence | Prevention |
|---------|-------------|------------|
| Forgetting `git fetch origin` | Stale baseline | Always fetch before creating |
| Initing all submodules | Slow setup | Only init what you need |
| Not cleaning up worktrees | Disk space + branch clutter | Remove after merge |
| Editing main workspace from worktree | Cross-contamination | Always `cd` into worktree first |
| Pushing without PR | Direct push to main | Use `gh pr create` |

## Integration with GaC Gate

Before committing in a worktree, run the GaC gate:

```bash
cd /Users/xiamingxing/Workspace/ws-ci-roundN
make gac-local-gate  # or targeted scope
```

This ensures governance compliance before merge.

## Anti-patterns

- **DON'T** create worktrees without naming them clearly — purpose-less worktrees are hard to track
- **DON'T** init all submodules — pick only what you need
- **DON'T** forget to clean up — stale worktrees accumulate and confuse other agents
- **DON'T** `git push` from a worktree without creating a PR first
