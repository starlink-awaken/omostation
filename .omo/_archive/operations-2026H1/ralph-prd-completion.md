---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-18
title: Ralph PRD 完成定义 (G6)
type: doc
---
# Ralph PRD 完成定义 (G6)

> **来源**: P79 pattern · #907 35+ iteration ralph 催促实证 · 2026-08-04
> **场景**: ralph loop 的"完成"判定, 避免无限死磕 user/deferred 任务

## 0. 问题

ralph stop hook 持续催"work is NOT done", 直到所有 PRD stories `passes: true`.
但 PRD 常含两类**非 agent 能单方面完成**的 story:
- **user 任务** (如 US-A1 "用户 merge"): 需用户决策/操作, agent 只能准备就绪
- **deferred 任务** (如 D1/D2 P1): 明确留下轮, ralph scaffold 没 refine

agent 为满足 hook 死磕这些任务 → 高危操作绕权 / 原地打转 (#907 35+ iteration).

## 1. 完成定义 (三层)

| Story 类型 | 判定 | ralph 行为 |
|-----------|------|-----------|
| **agent 任务** (实现/测试/PR) | `passes: true` 当 agent 完成且验证 | 正常推进 |
| **user 任务** (merge/决策) | `passes: true` 当**用户完成** + agent 标记 | 准备就绪后等用户, ralph 核心交付完成即合理 cancel |
| **deferred 任务** (P1/下轮) | `passes: true` 当明确标 `deferred: true` + 下轮 | 不算 ralph 本轮失败 |

## 2. 合理 cancel (非放弃)

ralph **核心交付完成** (所有 agent 任务 passes) 后, 剩 user/deferred 任务:
- **cancel ralph** = 合理收尾 (清 loop state, 方案交底用户)
- **不是放弃** — 核心 hard 交付已落袋, rest 是 user 决策/下轮

## 3. 高危操作红线 (不因 hook 催促而破)

ralph hook 催"continue" **不等于** 用户授权绕权:
- `git reset --hard` / `force push` / `--no-verify` 仍需**明确用户确认**
- 权限系统拦高危操作 = 正确, 不绕
- hook 是系统行为, 非用户指令

## 4. PRD scaffold 建议

ralph 启动 refine PRD 时:
- 区分 story 类型 (agent/user/deferred) 在 story 加 `type` 字段
- deferred story 标 `deferred: true` + `defer_reason`
- user story 标 `needs_user: true`
- ralph 完成判定: 所有 agent 任务 passes + user/deferred 已标记 = 可 cancel

## 5. 关联

- [P79](../../.omo/_knowledge/patterns/p79-partial-worktree-reachability-false-positive.md) §陷阱5 (ralph loop 催促)
- #907 (US-A1 user merge, ralph 死磕 35 iteration 教训)
- ralph skill (`oh-my-claudecode:ralph`) — 本文档是操作补充, 非改 skill 本身
