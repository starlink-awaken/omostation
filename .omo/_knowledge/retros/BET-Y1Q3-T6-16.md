---
bet_id: BET-Y1Q3-T6-16
title: "多仓本地分支、脏工作树与未合并交付的保护性收敛"
status: completed
date: 2026-09-05
---

# Retro: BET-Y1Q3-T6-16

## What happened

Conducted a full inventory and protective convergence of local branches, dirty
worktrees, and unmerged deliveries across the root repository.

### Before
- 38 local branches (non-main)
- 27+ worktrees (including 2 orphan/broken directories)
- 0 stashes
- 3 open PRs

### After
- 5 local branches (main + 4 needing human decision)
- 5 worktrees (main + our worktree + 3 needing human decision)
- 23 gone-tracking local branches deleted
- 29 worktrees removed (27 Category A merged + 2 Category D orphan)
- 12 additional safe local branches deleted

### Actions taken
1. **Inventory**: Scanned all worktrees for dirty status, branch reachability from
   origin/main, and PR merge status via `gh pr list`.
2. **Classification**: Categorized every branch/worktree into:
   - Category A (30): Safe to remove — branch reachable from main or squash-merged PR
   - Category B (2): Open PR — wait for merge then remove
   - Category C (3): Unmerged, no PR — needs human decision
   - Category D (2): Orphan/broken directories
3. **Execution**: Removed Category A worktrees, Category D orphans, pruned gone-tracking
   branches, deleted safe local branches.
4. **Remaining**: 3 worktrees needing human decision:
   - `ws-bet-y1q4-t8-14` (open PR #3192)
   - `ws-remove-more-stale-tests` (PRs #3159, #3141 both CLOSED)
   - `ws-ui-continue` (no PR)

### Key finding
The workspace had accumulated significant branch/worktree debt from Y1Q4 bet
execution. Most branches were from bets that had their PRs merged via squash (so
the branch commit isn't in main's history, but the content IS on main).

## Lessons

1. **Squash merge hides branch history**: After squash merge, `git merge-base
   --is-ancestor` returns false even though content is on main. Always check PR
   merge status via `gh pr list --state merged --head <branch>` as the authoritative
   source.
2. **Orphan directories accumulate silently**: Two broken/orphan directories were
   found without proper .git files. Regular worktree audits should include filesystem
   scanning, not just `git worktree list`.
3. **Submodule pointer drift is common in dirty worktrees**: Many "dirty" worktrees
   only had submodule pointer drift — not actual code changes. This is safe to discard.

## Reminders
- Category B worktrees should be removed after their PRs merge
- Category C branches need human review before deletion
- The `remove-more-stale-tests-v2` branch has no PR — check if content was
  incorporated via other means or if it should be revived
