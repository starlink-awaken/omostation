---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-04
last_updated: 2026-09-04
type: ssot
---

# ADR-0201: 子模块指针暂存纪律 (Submodule Pin Stage Discipline)

## Status

Accepted (CR-GIT-STAGE-SUBMODULE-PIN, governance-rule requirement, 2026-09-04)

## Context

`git add -A` / `git add .` 在多子模块仓库中会意外 stage 子仓的 gitlink 侧分支状态，
导致指向非 origin/main 的 commit。此问题在 cockpit/omlxc/omo 三个子仓各触发过一次
(PITFALL-COO-003)，均被 pre-commit gate 拦截。

根因：开发者习惯用 `git add .` 一次性 stage 所有变更，未区分主仓文件与子模块指针。

## Decision

1. **禁止 `git add -A` / `git add .`**：pre-commit hook 拦截含子模块路径的全量 stage。
2. **变更须 add 具体路径**：`git add path/to/file` 而非通配符。
3. **涉子模块变更前核对 gitlink**：`git diff --cached -- submodules/path` 确认指针指向 origin/main。
4. **子模块指针更新走 `bin/ssot/submodule-pointer-transaction.sh`**（非手动 `git add`）。

## Consequences

- 开发者需改变 `git add .` 习惯，改用 `git add <path>`。
- pre-commit hook 拦截提供即时反馈。
- 子模块指针变更可追溯、可审计。

## References

- Rule: CR-GIT-STAGE-SUBMODULE-PIN
- Pitfall: PITFALL-COO-003
- Target: `.githooks/pre-commit` + `git-discipline` skill §1
