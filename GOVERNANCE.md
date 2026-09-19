---
type: ssot
owner: governance-team
last_updated: 2026-09-03
---

# Workspace Governance

This document is a navigation pointer, not a second governance source of truth.
The executable contracts and ownership registries remain authoritative.

## Authoritative Sources

- Operating rules: [`AGENTS.md`](AGENTS.md)
- AI session startup: [`CLAUDE.md`](CLAUDE.md)
- Governance checks and owners:
  [`.omo/_truth/registry/governance-checks.yaml`](.omo/_truth/registry/governance-checks.yaml)
- Document ownership and lifecycle:
  [`.omo/_truth/registry/document-governance.yaml`](.omo/_truth/registry/document-governance.yaml)
- Document contract:
  [`.omo/standards/doc-ssot-contract.md`](.omo/standards/doc-ssot-contract.md)
- Agent workflow contract:
  [`.omo/standards/agent-workflow-contract.md`](.omo/standards/agent-workflow-contract.md)
- Project metadata:
  [`docs/project-registry.yaml`](docs/project-registry.yaml)

## Worktree Isolation Policy

**Effective**: 2026-09-02
**Owner**: governance-team
**Scope**: All workspace changes (human + AI agent)

### Rule

> **Main workspace checkout is read-only. Every new change MUST start from an isolated worktree.**

| Action | Required |
|--------|----------|
| New feature / fix / cleanup | `gac-worktree.sh claim <session>` |
| Submodule work | Child worktree via PASW |
| Emergency hotfix on main | Admin approval + post-hoc review |
| Direct commit to main | ❌ Prohibited |

### Workflow

```bash
# 1. Create isolated worktree
bash bin/gac/gac-worktree.sh claim <session-name>

# 2. Work in the new worktree
cd /Users/xiamingxing/ws-<session-name>

# 3. Commit, push, create PR
git add . && git commit -m "..."
git push -u origin <branch>
gh pr create ...

# 4. After PR merged, retire the worktree
bash bin/gac/gac-worktree.sh retire <session-name>
```

### Rationale

- **Prevents dirty state accumulation**: Main workspace stays clean, `git status` always empty
- **Enables parallel work**: Multiple agents/humans work in isolation without conflict
- **Atomic PR review**: Each worktree = one PR, clean diff, no cross-contamination
- **Safe experimentation**: Failed experiments retired without polluting main

### Enforcement

| Check | Mechanism |
|-------|-----------|
| Pre-commit | `bin/gac/check-main-workspace-commit.py`（hook-manifest `main-workspace-commit`）**blocking**: 主工作区**任意分支**上提交即拦截 |
| Pre-push | `gac-worktree-guard.sh --check` blocks pushes from main with uncommitted changes |
| CI | `gitlink-ancestry` + `pointer-drift` detect main divergence |
| Audit | Periodic review of `git worktree list` vs PR activity |

**判据为何按"位置"而非"分支"**（2026-09-19 修正，含两次实证）：

| 位置 | 故障模式 | 实证 |
|---|---|---|
| 主工作区 + **非 main** 分支 | HEAD 停在该分支 → 随时被并发会话切走 → 提交孤立 | 2026-09-18 `e4787d290`（同日 #3976 "dropped from #3969" 是同一事故） |
| 主工作区 + **main** 分支 | 本地 main 领先 origin/main → 一旦 origin 前进即成**双向分叉** → 所有人的 `merge --ff-only origin/main` **只打印 hint、不报错** → 并发会话都以为同步了，实际停在旧提交上 | 2026-09-19，该状态持续近 1 小时无人察觉 |

初版只拦非 main 分支（误判"main 上提交无孤立风险"）—— 第二次实证证明**两种模式都是"在共享工作区提交"的直接后果**，故判据收敛为按位置。

逃生舱（会记入 `runtime/logs/main-workspace-commit-overrides.jsonl`）：

```bash
GAC_ALLOW_MAIN_WORKSPACE_COMMIT=1 git commit -m "..."
```

已孤立/分叉提交的处置：

```bash
python3 bin/gac/workspace-wip-guard.py list-protected   # 查看钉扎
git log --oneline origin/main..main                     # 查分叉
```

### Stale worktree retirement (N = 14 days idle)

Worktrees idle for more than 14 days (no commits and no linked open-PR
activity) are considered stale. The owner archives the remaining diff to a
durable path (e.g. a patch file kept with the session notes) and then removes
the worktree via the standard release flow. This is a docs convention only —
no new automation or daemons.

### Exceptions

| Exception | Condition |
|-----------|-----------|
| Main README/docs typo fix | Single commit, < 5 lines, admin merge |
| Emergency security patch | Post-hoc worktree recreation for audit trail |
| Automated submodule bumps | `auto/submodule-bump-*` branches (cron only) |

---

## Required Delivery Path

Requirement changes use the registered workflow lifecycle:

```text
bootstrap -> status -> start -> claim -> verify -> closeout
```

Use `bin/agent-workflow.py` and the workflow selected for the affected surface.
Project-specific guidance belongs in each project's `AGENTS.md` and `CLAUDE.md`;
workspace-wide rules must not be duplicated there.

## Governance Entry Points

- Local gate: `make gac-local-gate`
- Documentation SSOT check: `uv run --with pyyaml python bin/ssot/doc-ssot-lint.py --json`
- Document governance check: `python3 bin/ssot/doc-governance-check.py --no-new-warnings`
- Runtime projection refresh: `uv run --project projects/omo omo state sync`

Dynamic facts, generated projections, ports, test counts, and project inventories
must be read from their registered SSOT rather than copied into this pointer.
