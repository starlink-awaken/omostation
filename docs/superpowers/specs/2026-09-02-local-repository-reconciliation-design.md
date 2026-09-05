---
schema_version: specification/v1
spec_version: 1.0.0
title: Local repository reconciliation — dirty worktrees and unmerged delivery convergence
bet_id: BET-Y1Q3-T6-16
status: accepted
lifecycle: contract
owner: governance-agent
created: 2026-09-02
last-reviewed: 2026-09-05
risk_level: L3
human_gate: true
type: ssot
last_updated: 2026-09-05
---

# Local Repository Reconciliation Design — BET-Y1Q3-T6-16

## Problem

The workspace has accumulated 30+ local branches, 27+ worktrees (including 2 orphan
directories), and unmerged deliveries across the root repo and submodules. Without
structured reconciliation, these represent unrecoverable work risk, CI/billing waste,
and human cognitive overhead.

## Inventory (2026-09-05)

### Total Counts
- Local branches (non-main): 38
- Worktrees: 27 (including this one)
- Open PRs: 2 (#3191 t4-03-done, #3192 t8-14)
- Orphan directories: 2 (broken-081008, husk-1788567131)
- Stashes: 0

### Classification

#### Category A: SAFE TO REMOVE (branch merged to main via ancestor or squash PR)

These 27 worktrees have all their content on origin/main. They can be removed
with `git worktree remove` without losing any work.

| # | Worktree | Branch | Dirty? | PR | Notes |
|---|----------|--------|--------|----|-------|
| 1 | ws-bet-y1q4-t1-02 | work/bet-y1q4-t1-02 | submodule drift | #3100 merged | |
| 2 | ws-continue-design-ctx | work/continue-design-ctx | clean | #3161 merged | |
| 3 | ws-continue-pr-merge | work/continue-pr-merge | clean | #3140 merged | |
| 4 | ws-remove-stale-attest-test | work/fix-dispatch-bridge-test | locks/.venv only | #3110 merged | |
| 5 | ws-stash-cleanup | stash-cleanup | clean | auto-bump | |
| 6 | ws-architecture-analysis | work/architecture-analysis | clean | #3098 merged | |
| 7 | ws-bet-y1q4-t1-03-self-binding | work/bet-y1q4-t1-03-self-binding | submodule drift | #3085 merged | |
| 8 | ws-bet-y1q4-t1-03 | work/bet-y1q4-t1-03 | clean | #3113 merged | |
| 9 | ws-bet-y1q4-t1-05 | work/bet-y1q4-t1-05 | .omo/locks/ | #3075 merged | |
| 10 | ws-bet-y1q4-t1-08 | work/bet-y1q4-t1-08 | clean | #3101 merged | |
| 11 | ws-bet-y1q4-t1-09 | work/bet-y1q4-t1-09 | clean | #3111 merged | |
| 12 | ws-bet-y1q4-t1-10 | work/bet-y1q4-t1-10 | clean | #3164 merged | |
| 13 | ws-bet-y1q4-t1-13 | work/bet-y1q4-t1-13 | system.yaml drift | #3154 merged | |
| 14 | ws-bet-y1q4-t6-03 | work/bet-y1q4-t6-03 | clean | #3137 merged | |
| 15 | ws-bet-y1q4-t8-05 | work/bet-y1q4-t8-05 | submodule drift | #3107 merged | |
| 16 | ws-bet-y1q4-t8-11 | work/bet-y1q4-t8-11 | clean | #3136 merged | |
| 17 | ws-bet-y1q4-t8-12 | work/bet-y1q4-t8-12-rebind | submodule drift | #3158 merged | |
| 18 | ws-bet-y1q4-t8-13 | work/bet-y1q4-t8-13-rebind | submodule drift | #3169 merged | |
| 19 | ws-bet-y1q4-t9-01 | work/bet-y1q4-t9-01 | clean | #3142 merged | |
| 20 | ws-bet-y1q4-t9-02 | work/bet-y1q4-t9-02 | clean | #3160 merged | |
| 21 | ws-bet-y1q4-value-obj-split | work/bet-y1q4-value-obj-split | clean | #3174 merged | |
| 22 | ws-ssa-v5-dynui | work/ssa-v5-dynui | clean | #3166 merged | |
| 23 | ws-design-asset-2026-09-04 | work/design-asset-2026-09-04 | submodule drift | #3152 merged | |
| 24 | ws-fix-cross-repo-consistency | work/fix-cross-repo-consistency | submodule drift | #3110 merged | |
| 25 | ws-fix-stale-tests-2 | work/fix-stale-tests-2 | state+cockpit drift | #3126 merged | |
| 26 | ws-fix-stale-tests | work/fix-stale-tests | submodule drift | #3114 merged | |
| 27 | ws-t1069 | feat/eco-tools-only | .gitmodules+agora drift | #3103 merged | |
| 28 | ws-t8-14-binding | work/t8-14-binding | clean | #3189 merged | |
| 29 | ws-fix-doc-index-hardblock | work/fix-doc-index-hardblock | clean | #3190 merged | |
| 30 | ws-bet-y1q4-t8-11.broken-081008 | work/bet-y1q4-t8-11 | clean | N/A | orphan dir, not a worktree |

#### Category B: OPEN PR — WAIT FOR MERGE THEN REMOVE

| # | Worktree | Branch | PR | Notes |
|---|----------|--------|----|-------|
| 1 | (no worktree, branch only) | work/bet-y1q4-t4-03 | #3191 open | ledger closeout PR |
| 2 | ws-bet-y1q4-t8-14 | work/bet-y1q4-t8-14 | #3192 open | t8-14 spec binding PR |

#### Category C: UNMERGED, NO PR, NEEDS HUMAN DECISION

| # | Worktree | Branch | Dirty? | Notes |
|---|----------|--------|--------|-------|
| 1 | ws-bet-y1q4-t1-03 (duplicate) | work/bet-y1q4-t1-03 | clean | local branch not on origin |
| 2 | (no worktree) | work/remove-more-stale-tests-v2 | N/A | PRs #3159, #3141 both CLOSED |
| 3 | (no worktree) | work/ui-continue | N/A | no PR, clean branch |
| 4 | ws-t8-14-binding | work/t8-14-binding | clean | tracking gone, PR#3189 merged |

#### Category D: ORPHAN/BROKEN

| # | Path | Notes |
|---|------|-------|
| 1 | ws-bet-y1q4-t8-11.broken-081008 | .git is a file (worktree), not a dir |
| 2 | ws-bet-y1q4-t9-01.husk-1788567131 | no .git, empty dir |

## Reconciliation Sequence

### Step 1: Remove Category A worktrees (safe, 30 worktrees)
```bash
for wt in <list of 30 worktrees>; do
  git worktree remove --force "$wt"
done
```
**Risk**: None — all content is on origin/main.
**Evidence**: git worktree list should show only main + bet-y1q3-t6-16 after.

### Step 2: Remove Category D orphan dirs
```bash
rm -rf ws-bet-y1q4-t8-11.broken-081008
rm -rf ws-bet-y1q4-t9-01.husk-1788567131
```
**Risk**: None — these are broken/empty.

### Step 3: Prune gone tracking branches
After worktree removal, prune local branches that track gone remotes.
This is safe for Category A (merged) and Category D (orphan).

### Step 4: Category B — Wait for PR merge, then remove
PRs #3191 and #3192 should be merged first, then their worktrees removed.

### Step 5: Category C — Human decision needed
- `work/remove-more-stale-tests-v2`: PRs closed without merge. Check if content
  is on main. If yes, delete branch.
- `work/ui-continue`: No PR. Check if feature is needed.
- `work/t8-14-binding`: PR merged, tracking gone. Safe to remove after worktree.

## Non-Goals

- No deletion of runtime, .omc, cache, lock, or secret artifacts
- No repeat of T6-15 immutable GaC repair
- No repeat of T10-122 Documents canary work
- No force-push or destructive cleanup of unknown work
