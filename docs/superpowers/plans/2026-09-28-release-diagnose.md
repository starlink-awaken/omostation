# Worktree release-diagnose Implementation Plan

> **For agentic workers:** execute this plan in the isolated release-diagnose worktree.

**Goal:** Add a read-only `release-diagnose <session>` command that explains why a worktree cannot be safely released without changing release behavior.

**Architecture:** Extend `bin/gac/gac-worktree.sh` with a diagnosis-only command that reuses the existing session path, submodule enumeration, and PASW metadata rules. Keep deletion and repair exclusively in `release`; diagnosis emits stable categories and returns a tri-state exit code.

**Tech Stack:** Bash, Git worktree/submodule porcelain, shell regression tests.

## Global Constraints

- Diagnosis must not write, reset, stash, clean, remove worktrees, or delete branches.
- Existing `release` behavior must remain unchanged.
- Do not migrate the implementation to Python.
- Do not change PASW initialization depth or lifecycle policy.
- Use explicit paths and deterministic output suitable for a human operator.

---

### Task 1: Add diagnosis command

**Files:**
- Modify: `bin/gac/gac-worktree.sh`
- Test: `tests/test_gac_worktree_release_diagnose.sh`

**Interfaces:**
- Consumes: session name and `/Users/.../ws-<session>` layout.
- Produces: exit `0` for clean, `1` for diagnosed blockers, `2` for unreadable metadata; output lines with category, path, and recommendation.

- [ ] **Step 1: Write the failing shell test**

Create fixtures using temporary Git repositories and assert the command reports a dirty root without modifying fixture files.

- [ ] **Step 2: Run the test and verify the expected failure**

Run: `bash tests/test_gac_worktree_release_diagnose.sh`
Expected: FAIL because `release-diagnose` is not implemented.

- [ ] **Step 3: Implement the minimal diagnosis path**

Add a `release-diagnose` case before `release`. Validate the session, resolve the worktree, inspect root status, initialized submodules, PASW directories, and untracked files. Emit:

```text
release-diagnose: session=<session>
[dirty-root] path=<path> recommendation=preserve-and-review
[dirty-submodule] path=<path> recommendation=preserve-and-review
[invalid-pasw] path=<path> recommendation=remove-stale-metadata
[generated] path=<path> recommendation=review-generated
[pointer] path=<path> recommendation=review-pointer
```

Return `2` when the worktree or required Git metadata cannot be inspected; return `1` when findings exist; otherwise return `0`.

- [ ] **Step 4: Run the focused test and verify it passes**

Run: `bash tests/test_gac_worktree_release_diagnose.sh`
Expected: all fixture cases pass.

- [ ] **Step 5: Run existing lifecycle tests**

Run: `python3 -m pytest tests/test_gac_worktree_lifecycle.py tests/test_gac_worktree_lifecycle_submodule.py -q`
Expected: existing lifecycle behavior remains green.

- [ ] **Step 6: Commit**

```bash
git add bin/gac/gac-worktree.sh tests/test_gac_worktree_release_diagnose.sh
git commit -m "feat(gac): add read-only worktree release diagnosis"
```

### Task 2: Record verification and closeout

**Files:**
- Create: `.omo/_knowledge/retros/BET-Y2Q4-T10-211.md`
- Create: `docs/reports/2026-09-28-release-diagnose-closeout.md`

- [ ] **Step 1: Record observed workflow/compiler blocker**

State the exact `WORK_PACKET_COMPILER_UNAVAILABLE` result from the pinned OMO submodule and distinguish it from implementation verification.

- [ ] **Step 2: Record command evidence**

Include focused shell test output, lifecycle test output, `make gac-local-gate` result if runnable, and cleanup status.

- [ ] **Step 3: Commit closeout evidence**

```bash
git add .omo/_knowledge/retros/BET-Y2Q4-T10-211.md docs/reports/2026-09-28-release-diagnose-closeout.md
git commit -m "docs: closeout release diagnose evidence"
```
