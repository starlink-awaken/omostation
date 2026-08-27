---
id: 42
title: "X3: 价值堆栈策略（早期简版）"
type: ARCHITECTURE_PATTERN
phase: Phase6
layer: X3
status: superseded
superseded_by: pat-42
version: v1.0.0
tags: [phase6, X3, kos, value-stack]
date: 2026-05-27
---

# X3: 价值堆栈策略

> ⚠️ 本文档已由 [phase6-完成化/pat-42-X3价值堆栈策略.md](./phase6-完成化/pat-42-X3价值堆栈策略.md) 替代。保留作历史参考。
>
> 日期: 2026-05-27

## 1. 什么是价值堆栈

所有智力资产按价值层级管理, 每层有不同半衰期和保鲜策略。
价值层级越高, 越接近"元认知", 半衰期越长, 变更越谨慎。

## 2. 7 个价值层级

| 层级 | 示例 | 半衰期 | 保鲜策略 | 执行者 |
|------|------|--------|---------|--------|
| Axiom | 逻辑自洽>功能堆砌 | 终身 | 纯版本, 几乎不检查 | Manual |
| Principle | 架构先行, 红蓝对抗 | 5-10年 | 季度review+变更记录 | X2 Cron |
| Theory | 信息论/控制论 | 10-30年 | 年检(新证据追踪) | X2 Cron |
| Framework | 4+1+3架构 | 3-5年 | 半年检查 | X2 Cron |
| Knowledge | 研究结果/实体 | 1-3年 | 月检(新鲜度标记) | X2 Cron |
| Skill | Hermes技能文件 | 6-12月 | 每次使用纠正 | 交互中 |
| Tool | cron脚本/CLI工具 | 1-6月 | 每次使用前健康检查 | Watchdog |

## 3. 保鲜策略

- Axiom: 仅版本化, 几乎不触发检查
- Principle: 每季度 `freshness_check.sh` 扫描变更
- Theory: 每年 minerva 搜索新证据
- Framework: 每半年 arcnode-evolve 检查熵
- Knowledge: 每月 freshness-watch 标记新鲜度
- Skill: Hermes交互中自动纠正
- Tool: 每次 cron 执行前 health-monitor 探测

## 4. 集成点

### X3↔L1 Schema
consensus schema 的 `expires_at` 字段对接 eidos 的 `deprecation_date`。
共识过期 → 对应schema版本检查 → 决定是否需要升级。

### X3↔X2 Cron
freshness_check.sh 读取共识过期记录 → 触发X2保鲜管道。
X2 cron 按 freshness 策略决定处理(通知/归档/删除)。

### X3↔L4 Self
L4的价值原则(principle)是X3的 Principle 层实例。
用户修改L4 identity时，X3的半衰期重置。

## 5. 当前实现

- Consensus domain: ✅ kos/consensus/ (Phase5)
- Freshness cron: ✅ freshness_check.sh
- 价值层级枚举: ⚠️ KOS有 PRINCIPLE/THEORY 等类型, 未实现半衰期计算
- 保鲜自动执行: ❌ 由 X2-1 arcnode-evolve 接管
