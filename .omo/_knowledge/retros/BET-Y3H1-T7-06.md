---
schema: md/v1
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-25
type: ephemeral
bet_id: BET-Y3H1-T7-06
title: "health-medical-workflow 场景冷启动 — draft→routine"
---


# BET-Y3H1-T7-06 Retrospective

## Q1: 目标是否达成？

是。4 个 health 场景 (scene-health-archive, scene-health-intake, scene-health-visit-prep, scene-health-visit) 已从 draft 冷启动推进到 routine，activation 从 preview 升至 allowed。全部 4 项 done_when 验收标准达成：
- 4 场景卡 lifecycle = routine ✓
- activation = allowed ✓
- 36 条 trial records (4 场景 × 9 条) ✓
- bet-ledger lint exit 0 ✓

## Q2: 实际做了什么？

分 3 个 PR 完成：
1. **PR #3939 (立项)**: 创建 BET 条目 (candidate) + spec doc + retro 文件
2. **PR #3941 (Transitions + Trials)**: 16 次 lifecycle transition (draft→shadow→assisted→supervised→routine × 4 scenes) + 36 条 trial records
3. **PR #3942 (Closeout)**: ledger status done + completion_evidence 三轴 + retro 归档

总耗时约 1 小时，3 个 PR 全 MERGED。

## Q3: 遇到了什么问题？

1. **worktree 创建极慢**: `git worktree add` 子模块初始化耗时 5+ 分钟，多次超时。改用主工作区直接操作 + `git checkout -b` 创建分支模式。
2. **worktree --no-checkout 陷阱**: 使用 `--no-checkout` 创建 worktree 后，git status 显示所有文件为删除状态，无法正常提交。
3. **文档治理预算**: 新增 spec doc 须包含 `schema_version: specification/v1` + 完整 required_frontmatter，否则触发 SPEC_FRONTMATTER_SCHEMA_INVALID error。

## Q4: 学到了什么？

1. **主工作区直接操作更高效**: 对于仅修改少量文件的场景，直接在主工作区 `git checkout -b` + `git add` + `git commit` 比 worktree 更快（省去 5 分钟初始化）。
2. **4 场景 batch cold-start**: 4 场景 × 4 transitions = 16 次 transition + 36 条 trial records，约 20 分钟完成。
3. **health-medical-workflow journey 为 draft 不影响场景卡推进**: scene-card-lifecycle.py 不检查 journey 状态，只检查场景卡自身的 readiness 条件。

## Q5: 下一步建议？

- **draft 场景卡清零**: 至此全部 6 张 draft 场景卡已冷启动至 routine (admin-inbox, admin-submit, health-archive, health-intake, health-visit-prep, health-visit)。
- **domain 字段修复**: health-* 场景卡 domain 字段为 work (应为 health)，建议在独立 BET 中统一修复。
- **health-medical-workflow journey 升档**: 当前 journey 状态为 draft，建议在场景卡全部 routine 后推进 journey 升档。
- **circuit_breaker 自动化**: 当前校准检查为手动触发，建议在 supervised→routine 前自动检查 calibration >= 0.6。
