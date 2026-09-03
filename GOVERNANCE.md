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
| Pre-push | `gac-worktree-guard.sh --check` blocks pushes from main with uncommitted changes |
| Pre-commit | `pre-commit hook` warns if committing to main |
| CI | `gitlink-ancestry` + `pointer-drift` detect main divergence |
| Audit | Periodic review of `git worktree list` vs PR activity |

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
