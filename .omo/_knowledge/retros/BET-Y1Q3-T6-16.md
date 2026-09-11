---
bet_id: BET-Y1Q3-T6-16
title: "多仓本地分支、脏工作树与未合并交付的保护性收敛"
status: completed
date: 2026-09-11
owner: governance-team
---

# Retro: BET-Y1Q3-T6-16

## What happened

主仓曾被遗留在并发 agent 分支 `chore/t10-125-code-rebase` 上 (非 main, 有 1 个
未提交运行时文件)。执行保护性收敛:

1. **主仓恢复**: stash 运行时状态 → checkout main → pull 最新 → 恢复 submodule 指针
2. **已合并分支清理**: 3 个已合并到 main 且无开放 PR 的分支及其 worktree 删除
   - agent/governance-agent/arch-current-state-convergence
   - agent/governance-agent/bet-y1q4-t10-125
   - agent/governance-agent/plugin-fix
3. **并发 agent 工作保护**: 剩余 8 worktree / 11 分支全属并发 agent (有开放 PR
   或活跃交付), 未触碰

## Result

- worktree: 11 → 8 (删 3 个已合并)
- 本地分支: 14 → 11 (删 3 个已合并)
- 主仓: main @ 最新, 干净 (仅运行时状态文件)

## Lesson

主仓应始终停留在 main (基线同步 + gitignore 运行时区)。并发 agent 的
worktree/分支不应在主仓操作中被清理——识别归属 (open PR 检查) 后再决策。
