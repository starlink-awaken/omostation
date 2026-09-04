---
lifecycle: entry
owner: auto-fix-loop
last_updated: 2026-08-24
title: Directory Convergence Decisions
type: doc
---

# Directory Convergence Decisions

> 2026-08-22 决策：5 个未注册目录收敛方案

| 路径 | 当前状态 | 决策 | 执行动作 | 负责人 |
|------|----------|------|----------|--------|
| `projects/bus-foundation` | `?` untracked | archive | 移动到 `.omo/_attic/bus-foundation-archive/` | governance-team |
| `projects/model-driven` | `?` untracked | register | `git submodule add` + 注册 | governance-team |
| `projects/observability` | `?` untracked | register | `git submodule add` + 注册 | governance-team |
| `projects/omo` | `+` modified submodule | sync | 提交 submodule 内改动 + 更新指针 | governance-team |
| `docs/operations/human-attestations/` | `??` untracked | register | `git add` + 提交 | governance-team |

## 背景

`git status --short` 显示 5 个未注册目录/文件：
- `projects/bus-foundation`、`projects/model-driven`、`projects/observability` 为 untracked（`?`）
- `projects/omo` 为 modified submodule（`+`）
- `docs/operations/human-attestations/` 为 untracked 目录（`??`）

## 决策原则

1. **有业务价值 → register**：保留为正式项目，纳入 `.gitmodules` 和 `project-registry.yaml`
2. **无业务价值 → archive**：移动到 `.omo/_attic/` 作为历史快照
3. **已有 submodule → sync**：提交内部改动并更新指针
4. **普通目录 → register**：`git add` 并纳入项目注册表

## 执行顺序

1. 先执行 `bin/gac/fix-submodule-drift.py --check` 确认漂移状态
2. 对 `projects/omo` 先提交内部改动，再更新根仓指针
3. 对 `projects/model-driven` 和 `projects/observability` 执行 `git submodule add`
4. 对 `projects/bus-foundation` 移动到 `.omo/_attic/`
5. 对 `docs/operations/human-attestations/` 执行 `git add`
