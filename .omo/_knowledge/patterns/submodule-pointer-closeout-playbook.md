---
id: SSP-CLOSEOUT
title: Submodule Pointer Closeout Playbook — deliver, verify, and close pointer-only PRs without governance noise
status: ACTIVE
created_at: '2026-08-17'
---

# SSP-CLOSEOUT — Submodule Pointer Closeout Playbook

> Adoptees: When delivering submodule pointer bumps (or any gitlink-only
> change), the run's verify/closeout must be scoped to the gitlink surface
> and every pointer movement must follow 三段式 (`add` → `commit` → `tag`).
> This pattern crystallized over 2026-08-16/17 pointer-PR delivery sessions.

## Why

Pointer bumps hit three recurring friction points:

1. **Workspace `.omo/**` drift is pre-existing, not yours.** A full-surface
   verify / `ssot-guardian` run flags omo/runtime drift that predates your
   pointer change. Closeout then fails on unrelated surface.
2. **`verify --json` output has a leading `^warning:` adapter line**, which
   breaks naive JSON parsers — the closeout sees `parse error` and may
   double-count or abort.
3. **Submodule worktree removal without `--force` fails** when the worktree
   carries modifications / untracked files (common after a pass across
   submodule worktrees), leaving stale worktree/ branch that later audits flag.

## When to use

- Delivering a submodule gitlink bump (root repo pointer change, clean
  submodule commits already pushed).
- Closing an active run whose diff touches gitlink / `.gitmodules`
  surfaces (`submodule_pointer` lane) alongside concurrent `.omo/**` drift.
- Cleaning up pointer worktrees and branches after squash-merge PR.

## How

1. **CLAIM scoped**: run `bin/gac/affected-graph.py --changed-projects ...`
   (or reuse the existing `artifacts/affected-graph-receipt.json` receipt hash)
   and pass `--affected-hash` to `agent-workflow.py claim` — claim only the
   gitlink paths, never the whole worktree.
2. **DELIVER with 三段式**: per deliverable `git add` → `git commit` →
   `git tag -a <name> -m ...`. Tag refs survive branch rewrites, commits do not.
   In a shared worktree use `git commit --only <paths>` to avoid sweeping
   concurrent submodule pointers.
3. **VERIFY scoped**: `agent-workflow.py verify <run-id> --from-diff --execute`
   with the diff limited to the `submodule_pointer` / gitlink surface
   (`--file` on gitlink paths) so `.omo/**` pre-existing drift never blocks.
4. **PARSE JSON correctly**: when consuming `verify --json`, strip leading
   lines matching `^warning:` (adapter banner) before `json.loads`, or the
   closeout aborts on a spurious parse error.
5. **REMOVE worktree with --force**: `git worktree remove --force <path>` for
   pointer worktrees; clean the `work/<session>` branch only after confirming
   its commits are ancestors of main (`git merge-base --is-ancestor`).
6. **JUDGE squash-merged branches correctly**: a squash-merged branch is not
   an ancestor of main (`git merge-base --is-ancestor` is non-zero), yet its
   content IS on main. Verify content with `git show <sha>:<path>` instead of
   treating "not an ancestor" as "not merged". Only then delete the branch.
7. **CLOSE the run**: `agent-workflow.py close <run-id> --status ok --evidence
   "<note>"` via the broker (never manual `.omo` writes). If the target was
   superseded by a later commit, close `ok` with that evidence; if the plan
   never landed, close `failed` with the superseding doc.

## Recipe (pointer-only PR, 5 min)

```bash
# 1. pointer change in submodules first (each sub own commit+push), then root:
git commit --only 'projects/<sub>' -m "chore(ptr): bump <sub> -> <sha>"
git tag -a pointer-bump-$(date +%Y%m%d) -m "pointer bump <sub>"
# 2. affected-hash for claim
python3 bin/gac/affected-graph.py --changed-projects workspace-root --output artifacts/affected-graph-receipt.json
HASH=$(python3 -c "import json;print(json.load(open('artifacts/affected-graph-receipt.json'))['receipt_hash'])")
# 3. run + claim gitlink paths
uv run --with pyyaml python bin/agent-workflow.py start submodule-pointer-close --profile release-agent --objective "..."
uv run --with pyyaml python bin/agent-workflow.py claim <run-id> --path 'projects/<sub>' --affected-hash "$HASH"
# 4. verify/closeout scoped to gitlink surfaces; strip '^warning:' from JSON
# 5. cleanup: git worktree remove --force <ptr-wt>; delete merged branch (git show <sha>:<path> to confirm content landed)
```

## Pitfalls

| # | Pitfall | Symptom | Remedy |
|---|---------|---------|--------|
| 1 | Unscoped verify on shared tree | `ssot-guardian` blocks on `.omo/**` pre-existing drift | `--file` gitlink surface only; door is for what *you* changed |
| 2 | `verify --json` with `^warning:` banner | closeout parse error, false aborts | strip leading `^warning:` lines before `json.loads` |
| 3 | worktree remove w/o `--force` | "contains modified/untracked files" refuse | `git worktree remove --force -- <path>` |
| 4 | "not ancestor" read as "not merged" after squash | branch cleanup wrongly keeps squash-merged branches | `git show <sha>:<path>` verifies content landed; ancestor check does not |
| 5 | gh in submodule dir | query misses repo | `gh ... --repo starlink-awaken/<sub>.git` |

## Related

- Workflow: `.omo/_truth/registry/agent-workflows/workflows/submodule-pointer-close.yaml`
- Skill: `.agents/skills/workflow:submodule-pointer-close/SKILL.md` (SEMA 结晶)
- ADR: submodule-pointer-close lifecycle (ADR-0203/0204 run + claim contract)