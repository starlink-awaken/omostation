---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: BET-Y1Q3-T1-06 复盘
type: retro
---
# BET-Y1Q3-T1-06 复盘

> 2026-08-16 · aetherforge 双副本指针同步 + 算力路由双 owner 收敛决策 · PR #1603 MERGED

## Q1 实际耗时 vs appetite？超出比例？

约 2 小时（指针同步 + 决策 + CI 修复），低于 2 days appetite，未超出。主要时间花在 PASW 子模块 worktree 流程（submodule-guard 拦截 → .subtrees + bump-pointer）和 cascading_test 环境性失败排查。

## Q2 done_when 是否全部通过？哪条没过，为什么？

3/3 通过：
1. agora 内嵌 aetherforge 指针已同步到根项目最新（b9a299f→905195b，agora commit aabe4a9e）
2. 双 owner 收敛决策报告产出（`docs/reports/2026-08-16-aetherforge-mesh-router-owner-decision.md`）
3. 决策已落地：project-registry.yaml mesh-router status → deprecated

## Q3 关键发现 / 教训

1. **双 owner 收敛的决策方法**：用"引用面 + 接线面 + 活跃度"三方证据选实际消费方——aetherforge（BOS 已登记 + 9 处引用 + 活跃）vs gac-mesh-router（零引用/未接线）→ 孤立实现标 deprecated 不删
2. **PASW 子模块指针同步的正确路径**：主仓直提交被 submodule-guard 拒 → 必须 `gac-worktree claim` + `.subtrees/<sub>` + `bump-pointer`
3. **cascading_test 环境性失败可根治**：setup-uv cache 恢复 400 → 加 `ignore-nothing-to-cache: true`，比绕过更优
4. **新 FAIL 先判断 pre-existing**：actionlint/capability-registry 是 main 级（其他 PR 同 FAIL），非本 bet 引入

## Q4 对后续 bet 的建议

- 子模块指针类 bet 从一开始就走 worktree + .subtrees，不要在主仓尝试直提交
- 双 owner/职责重叠类决策固定用"引用面+接线面+活跃度"三方证据
- done 后立即补 retro（bet-retro-due-check 会拦 CI），避免 PR 卡住

## 关联

- Bet: BET-Y1Q3-T1-06 · PR #1603 · Debt D-2（算力路由双 owner）
