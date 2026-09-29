---
schema: md/v1
status: active
lifecycle: plan
owner: governance-agent
last-reviewed: 2026-09-29
type: plan
---

# Worktree release-diagnose 精确分类实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** 将 `release-diagnose` 的 root/PASW 残留分类从路径猜测升级为基于 Git 元数据的精确诊断，同时保持只读接口兼容。

**Architecture:** 保留 `bin/gac/gac-worktree.sh` 的单脚本生命周期边界，只重写 `release_diagnose()` 内的分类与状态解析。根仓库先通过 Git index mode 判断真实 gitlink，再按生成物路径和普通路径分类；普通子模块和 PASW 目录继续复用现有枚举规则。测试继续使用临时 Git 仓库，不引入 Python 实现或额外依赖。

**Tech Stack:** Bash, Git porcelain/index metadata, pytest, shell regression tests.

## Global Constraints

- Diagnosis must not write, reset, stash, clean, remove worktrees, or delete branches.
- Existing `release` behavior must remain unchanged.
- Do not migrate the implementation to Python.
- Do not change PASW initialization depth or lifecycle policy.
- Default text output and exit codes `0/1/2` remain compatible.
- Gitlink classification must use index mode `160000`, never `projects/*` path guessing.

---

### Task 1: Expand regression fixtures for precise categories

**Files:**
- Modify: `tests/test_gac_worktree_release_diagnose.sh`

**Interfaces:**
- Consumes: temporary root repositories, temporary submodules, `WS_ROOT` and `WS_PARENT` overrides.
- Produces: failing fixtures that specify exact category tokens and prove diagnosis is read-only.

- [ ] **Step 1: Add a reusable assertion helper**

Add shell helpers immediately after `make_repo()`:

```bash
assert_contains() {
  local haystack="$1" needle="$2"
  printf '%s\n' "$haystack" | grep -Fq "$needle" || {
    printf 'missing expected output: %s\n%s\n' "$needle" "$haystack" >&2
    exit 1
  }
}

snapshot_tree() {
  local root="$1"
  (cd "$root" && find . -type f -o -type l | sort | shasum -a 256)
}
```

`assert_contains` must fail with the complete command output. `snapshot_tree` is only a before/after comparison helper; it must not modify the fixture.

- [ ] **Step 2: Add the ordinary `projects/*` false-positive fixture**

Create a clean temporary repository, add and commit `projects/ordinary/tracked.txt`, then modify that file. Run `release-diagnose ordinary-project` and assert:

```text
[dirty-root] path=projects/ordinary/tracked.txt recommendation=preserve-and-review
```

Also assert the output does not contain `[pointer]`. This pins the removal of path-based pointer inference.

- [ ] **Step 3: Add a real gitlink fixture**

Create a child repository and add it as `modules/child` with `git -c protocol.file.allow=always submodule add`. Change the root gitlink to a different child commit without changing the child worktree. Run diagnosis and assert:

```text
[gitlink] path=modules/child recommendation=review-pointer
```

The fixture must not classify the path as `[dirty-root]`.

- [ ] **Step 4: Add generated, invalid-PASW, orphan-PASW, and special-path fixtures**

Extend the existing temporary fixture setup to cover:

- `.omo/generated-state.yaml` → `[generated]` and `review-generated`;
- an invalid configured PASW directory under `.subtrees/` → `[invalid-pasw]`;
- an unconfigured Git-invalid directory under `.subtrees/orphan` → `[orphan-pasw]`;
- `notes/file with spaces.txt` and a rename state, asserting no duplicated old/new finding.

Use the actual PASW variable names loaded from `lib/pasw-core.sh`; do not introduce a test-only configuration format.

- [ ] **Step 5: Add the read-only invariant assertion**

For every multi-finding fixture, capture:

```bash
before_status=$(git -C "$fixture" status --porcelain --untracked-files=all)
before_tree=$(snapshot_tree "$fixture")
```

Run diagnosis, then assert `git status` and `snapshot_tree` are byte-identical. This verifies no file, index, branch, or worktree mutation.

- [ ] **Step 6: Run the focused test and verify it fails for the old implementation**

Run:

```bash
bash tests/test_gac_worktree_release_diagnose.sh
```

Expected: FAIL on the new `[gitlink]`/`[orphan-pasw]` assertions while the existing clean/root/submodule/missing cases remain green.

### Task 2: Implement metadata-backed classification

**Files:**
- Modify: `bin/gac/gac-worktree.sh:367-444` (`release_diagnose` and its local classifier)

**Interfaces:**
- Consumes: `diagnose_wt`, `PASW_ISOLATED_SUBS_ARRAY`, `PASW_SUBTREE_DIR`, Git status/index metadata.
- Produces: existing `release-diagnose <session>` command with categories `[dirty-root]`, `[gitlink]`, `[dirty-submodule]`, `[generated]`, `[invalid-pasw]`, `[orphan-pasw]` and exit codes `0/1/2`.

- [ ] **Step 1: Parse root status records without path-prefix pointer inference**

Replace the current `classify_diagnose_path` branch that treats `projects/*` as pointer. For each status path, obtain the index mode with:

```bash
git -C "$diagnose_wt" ls-files --stage -- "$diagnose_path"
```

A first field of `160000` emits `[gitlink] ... recommendation=review-pointer`; generated prefixes emit `[generated] ... recommendation=review-generated`; all other paths emit `[dirty-root] ... recommendation=preserve-and-review`.

If `ls-files` returns no record for an untracked path, classify it as generated only by the explicit generated prefixes; otherwise classify it as dirty-root.

- [ ] **Step 2: Handle staged/unstaged rename records deterministically**

Use `git status --porcelain=v1 -z --untracked-files=all` and consume NUL-delimited records. For rename/copy records, use the destination path as the finding path and do not emit the source path separately. Preserve paths containing spaces. If the shell implementation cannot safely consume a rename record without word splitting, fail closed with exit `2` rather than silently misclassifying it.

- [ ] **Step 3: Keep submodule content findings separate**

Retain recursive `git submodule foreach --quiet` enumeration and the existing `git -C "$diagnose_wt/$sub_path" status` check. Emit `[dirty-submodule]` only for content changes inside an initialized submodule. A changed root gitlink remains a separate `[gitlink]` finding.

- [ ] **Step 4: Separate configured-invalid PASW from orphan directories**

Build a set of configured PASW basenames from `PASW_ISOLATED_SUBS_ARRAY`. For configured paths under `$PASW_SUBTREE_DIR`, emit `[invalid-pasw]` only when the directory exists but `git -C <path> rev-parse --is-inside-work-tree` fails. For each direct child of `$PASW_SUBTREE_DIR` not in the configured set and not a valid Git worktree, emit `[orphan-pasw]` with `recommendation=preserve-and-review`. Never delete or repair the directory.

- [ ] **Step 5: Preserve exit and error semantics**

Keep `return 2` for missing/unreadable root, submodule enumeration failure, submodule status failure, or unsafe status parsing. Keep `return 1` when any finding was emitted and `return 0` otherwise. Do not change the `release` case or any other command dispatch.

- [ ] **Step 6: Run focused tests and syntax checks**

Run:

```bash
bash -n bin/gac/gac-worktree.sh
bash tests/test_gac_worktree_release_diagnose.sh
```

Expected: shell syntax passes and all precise-category fixtures pass.

### Task 3: Verify lifecycle compatibility and update evidence

**Files:**
- Modify: `tests/test_gac_worktree_release_diagnose.sh`
- Modify: `.omo/_knowledge/retros/BET-Y2Q4-T10-211.md`
- Modify: `docs/reports/2026-09-28-release-diagnose-closeout.md`

**Interfaces:**
- Consumes: implementation from Task 2 and existing lifecycle suites.
- Produces: reproducible verification evidence and no changes to `release` semantics.

- [ ] **Step 1: Run lifecycle regression tests**

Run:

```bash
python3 -m pytest tests/test_gac_worktree_lifecycle.py tests/test_gac_worktree_lifecycle_submodule.py -q
```

Expected: all existing lifecycle tests pass; no test may be weakened or deleted.

- [ ] **Step 2: Run local governance verification**

Run:

```bash
uv run --with pyyaml python bin/plan/bet-ledger.py lint
uv run --with pyyaml python bin/agent-workflow.py verify 20260929T021821Z-project-code-change-33e17d57 --from-diff --execute
make gac-local-gate
```

Record exact pass/fail output. Environment-only failures must be identified separately from implementation failures.

- [ ] **Step 3: Record closeout evidence**

Update the existing retro and closeout report with:

- precise category cases;
- focused test and lifecycle test results;
- read-only before/after evidence;
- governance verification result;
- any remaining environment blocker.

Do not claim `release` integration or JSON output; both are out of scope.

- [ ] **Step 4: Commit implementation and evidence separately**

Use:

```bash
git add tests/test_gac_worktree_release_diagnose.sh bin/gac/gac-worktree.sh
git commit -m "fix(gac): make release diagnosis classifications exact"

git add .omo/_knowledge/retros/BET-Y2Q4-T10-211.md docs/reports/2026-09-28-release-diagnose-closeout.md
git commit -m "docs: record precise release diagnosis evidence"
```

- [ ] **Step 5: Final verification**

Run `git diff --check`, the focused shell test, the two lifecycle suites, ledger lint, and the repository CI/gate checks. Confirm `git status --short` contains only intentionally staged/committed workflow evidence before submission.
