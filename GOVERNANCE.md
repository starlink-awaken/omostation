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
| Pre-commit | `bin/gac/check-main-workspace-commit.py`（hook-manifest `main-workspace-commit`）**blocking**: 主工作区停在非 `main` 分支时提交即拦截 |
| Pre-push | `gac-worktree-guard.sh --check` blocks pushes from main with uncommitted changes |
| CI | `gitlink-ancestry` + `pointer-drift` detect main divergence |
| Audit | Periodic review of `git worktree list` vs PR activity |

**为什么拦"非 main 分支"而不是"提交到 main"**（2026-09-18 修正）：主工作区被多
agent 共享，HEAD 停在非 `main` 分支意味着**该分支随时可能被并发会话切走**，
其上的提交会因此不可达 —— 实证 `e4787d290`（同日 #3976 "dropped from #3969"
是同一事故的另一次发生，导致重复劳动）。停在 `main` 上提交不产生该模式。

逃生舱（会记入 `runtime/logs/main-workspace-commit-overrides.jsonl`）：

```bash
GAC_ALLOW_MAIN_WORKSPACE_COMMIT=1 git commit -m "..."
```

已孤立提交的恢复入口：`python3 bin/gac/workspace-wip-guard.py list-protected`
（提交钉扎见 `refs/wip/`）。

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
