---
id: ADR-0399
lifecycle: spec
owner: '@Builder'
last_updated: '2026-08-09'
---

# ADR-0399: 治本 E — 子模块 stale 自动 pull + PASW 漂移检测增强

> **背景**: 编号 0399。本 ADR 固化"治本 E"方案：
> 1. `sync-submodules-push.sh` 新增 `--pull` 模式，pre-push 时自动 pull stale 子模块
> 2. `check-submodule-pointer-drift.py` 增强 PASW 感知，同时检查 `.subtrees/` 状态
> 3. `sync-submodules.sh` 新增 `--pull` 模式，`submit` 时自动同步子模块

## Context and Problem Statement

### 问题 1: stale 子模块不自动 pull
当前 `sync-submodules-push.sh` 只 push 未推 commit，不 pull 过期子模块。
场景：agent A 在子模块 commit + push，agent B 的共享 worktree 中该子模块落后于 origin/main。
→ agent B push 根仓时，CI 拉到的子模块版本旧于 gitlink 指向的 commit → "not our ref"。

### 问题 2: PASW 漂移检测盲区
当前 `check-submodule-pointer-drift.py` 只检查 `projects/<sub>` gitlink vs origin/main，
不检查 `.subtrees/<sub>` PASW worktree 状态。
→ PASW worktree 有未推 commit 或指针不一致时，drift check 漏报。

### 问题 3: submit 未集成 auto-sync
`gac-worktree.sh submit` 调用 `sync-submodules.sh` 但不带 `--pull`，
stale 子模块在 push 根仓后才被发现 → CI 失败 → 返工。

## Decision

### 1. Enhanced sync: `--pull` 模式

修改 `bin/ssot/sync-submodules-push.sh` 和 `bin/sync-submodules.sh`：

- 新增 `--pull` flag
- 检测子模块 `HEAD..origin/main` 的落后 commit 数
- 非 PASW 子模块：自动 `git checkout main && git pull`
- PASW 子模块：跳过 pull（由 `bump-pointer` 显式管理）
- 同时 push 未推 commit（原有行为）

### 2. PASW-aware drift detection

修改 `bin/gac/check-submodule-pointer-drift.py`：

- 新增 `PASW_ISOLATED_SUBS` 常量
- 新增 `check_pasw_drift()` 函数，检查 `.subtrees/<sub>` 状态
- 检测：
  - `.subtrees/<sub>` HEAD vs `projects/<sub>` gitlink（指针一致性）
  - `.subtrees/<sub>` 未推 commit（需 push 到 remote）
- JSON 输出新增 `pasw_checked` 字段
- 非 JSON 输出区分 `.subtrees/` 和 `projects/` 前缀

### 3. Agent workflow integration

修改 `bin/gac/gac-worktree.sh submit`：

- `sync-submodules.sh` 调用增加 `--pull` flag
- submit 时自动 pull stale + push unpushed，确保 gitlink 可达

## Implementation

### Files Changed

| File | Change |
|------|--------|
| `bin/ssot/sync-submodules-push.sh` | 新增 `--pull` 模式，PASW 子模块跳过 pull |
| `bin/sync-submodules.sh` | 新增 `--pull` 模式 |
| `bin/gac/check-submodule-pointer-drift.py` | 新增 `check_pasw_drift()`，JSON 输出增强 |
| `bin/gac/gac-worktree.sh` | `submit` 调用 `sync-submodules.sh --pull` |
| `.githooks/pre-push` | 调用 `sync-submodules-push.sh --pull` |

### PASW Boundary

- **PASW 子模块** (gbrain/cockpit/agora): 不自动 pull，由 `bump-pointer` 显式管理
- **非 PASW 子模块**: 自动 pull + push
- **`.subtrees/` 漂移检测**: 只报告，不自动修复（需人工 bump-pointer）

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| auto-pull 覆盖本地改动 | 仅 pull 无本地改动的子模块（检查 `git diff --quiet`） |
| PASW 子模块误 pull | PASW 子模块跳过 pull，由 bump-pointer 显式管理 |
| CI 时间增加 | auto-sync 仅在有 drift 时执行，平时 skip |
| 并发冲突 | PASW 已隔离高冲突子模块，auto-sync 只操作非 PASW |

## Verification

- [x] `sync-submodules-push.sh --pull` 通过 `make ci-local-fast`
- [x] `check-submodule-pointer-drift.py --json` 输出包含 PASW 状态
- [x] `check-submodule-pointer-drift.py` 非 JSON 输出区分 `.subtrees/` 和 `projects/`
- [ ] `make submodule-sync-auto` 修复 stale 子模块（待 Phase 3 实现）
- [ ] `gac-worktree.sh submit` 自动同步子模块（待 Phase 4 实现）

## Status

PROPOSED — 待 review 后 ACCEPTED
