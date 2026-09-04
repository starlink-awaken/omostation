---
bet_id: BET-Y1Q3-T6-07
date: 2026-08-19
lifecycle: history
last_updated: 2026-08-19
status: archived
owner: governance-team
title: BET-Y1Q3-T6-07 Retro — 根目录与项目废弃面清理
type: retro
---

# BET-Y1Q3-T6-07 Retro — 根目录与项目废弃面清理

## Q1 实际耗时 vs appetite

- appetite: 2 days
- 实际耗时: ~1 个会话 (分析 + 独立 clone + workflow + 清理 + 验证)
- 超出原因: 无显著超出；主要时间在独立 clone 初始化与门禁排障。

## Q2 done_when 通过情况

| # | done_when | 状态 | 证据 |
|---|---|---|---|
| 1 | 删除 `archive-1rBrRf/`、`scripts-fix-ci/` 等未跟踪临时面 | ✅ | `rm -rf` 已执行，`git status` 无残留 |
| 2 | 删除根级 9 个一次性脚本与 3 个 scratch patch | ✅ | 已 commit: `cleanup(root): remove one-off gap-clearance scripts...` / `cleanup(root): remove scratch patches...` |
| 3 | 删除 `projects/@驾驶舱/`、`.scratch-archive/`、`Workspace/`、`domain-kems/` | ✅ | 已 commit，含按计划退役 `domain-kems` |
| 4 | `root-directory-governance-scan.py --check` 通过 | ✅ | `[PASS] root-directory-governance` |
| 5 | `gac-local-gate` 通过 | ⚠️ 部分阻塞 | 与本次清理直接相关的检查（`change-lane-check`、`doc-governance`、`root-directory-governance`、`mass-deletion-gate`）均通过；但存在 3 个**预存在**失败阻塞全绿： |

### 预存在阻塞项（非本次清理引入）

1. **`gac-validate` subtraction-quota**: `bin/` 活跃脚本 416 超基线 410。主共享树在清理前已存在此失败。
2. **`bet-retro-due-check`**: 13 个已 done BET 缺 retro（BET-Y2Q1-T3-01 等）。
3. **`adr-coverage`**: 4 个 ADR 文件未入索引。

## Q3 打假 / 与 plan 不符的事实

- `domain-kems` 初看起来最近有 `ruff --fix` 提交，一度误以为仍活跃；深度核查后发现已有明确退役规划（`docs/plans/2026-08-07-workspace-legacy-strategy.md`、`docs/reports/2026-08-11-workspace-kems-convergence-audit.md`），可以安全删除。
- `scripts-fix-ci/` 被扫描器识别为 active-worktree，实则是未注册的完整 workspace 副本，不是合法 linked worktree，直接删除即可。
- 独立 clone 拓扑下，`projects/ecos`、`scripts`、`projects/cockpit-ui` 需手动 init 并 build 才能跑通 `gac-local-gate`。

## Q4 净增减

- 删除 tracked 文件: 38 个
- 删除 tracked 行数: ~2,389 行
- 删除未跟踪目录: `archive-1rBrRf/` (27 MB)、`scripts-fix-ci/` (24 MB)、`projects/Workspace/` (空)
- 新增: BET-Y1Q3-T6-07 台账条目 + 本 retro 文件
- GaC 规则 / ADR: 无增删

## Q5 下一个认领本 track 的 agent 需要知道什么

- 若要让 `gac-local-gate` 全绿，需另开一次 T6-SUBTRACT run 处理 `bin/` 脚本减法配额（至少归档/删除 6 个活跃脚本）以及补 13 个缺 retro 的 BET。
- `adr-coverage` 的 4 个未索引 ADR 也是独立债务。
- 根目录治理策略已生效：新增未跟踪/未忽略根目录会被 `root-directory-governance-scan.py --check` 阻断。
