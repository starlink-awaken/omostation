---
title: 三年战略 · 全链路 Index
status: draft
type: strategy-index
owner: 夏明星
created: 2026-07-15
note: >
  从战略叙事 → 决策定档 → c2g 拆解 → 对齐审计的全链路一页导航。
  运行时数字以 .omo/state/system.yaml 为准；任务属性为 c2g local 草案态。
---

# 三年战略 · 全链路 Index（2026-07-15）

> **一句话**：图纸 A 级、实物 B- 级；三年战略 = 收敛执行面 → 兑现蜂群 → 跃迁个人大脑。
> 链路已闭环：**战略叙事 → ADR 决策 → c2g 15 Bet/Task → radar 对齐审计**。

## 四份产物

| # | 产物 | 文件 | 角色 | 状态 |
|---|------|------|------|------|
| 1 | 战略规划（叙事 SSOT）| [`docs/STRATEGY-3YEAR-PANORAMA.md`](STRATEGY-3YEAR-PANORAMA.md) | 3 年综合全景，三阶段路线图 | draft |
| 2 | 战略决策（定档）| [`.omo/_knowledge/decisions/0210-three-year-strategy-execution-convergence.md`](../.omo/_knowledge/decisions/0210-three-year-strategy-execution-convergence.md) | ADR-0210 收敛优先方向 | PROPOSED（待拍板）|
| 3 | 战略拆解（可执行）| [`projects/c2g/.c2g_data/bets.json`](../projects/c2g/.c2g_data/bets.json) · [`tasks.json`](../projects/c2g/.c2g_data/tasks.json) | 15 Pitch→Bet→Task | planned（待 BET_APPROVED）|
| 4 | 对齐审计（验证）| [`docs/STRATEGY-ALIGNMENT-AUDIT.md`](STRATEGY-ALIGNMENT-AUDIT.md) | radar 六维对齐 + 依赖 DAG | draft |

## 链路全景

```
愿景 (VISION-ROADMAP)
   │  痛点驱动 (ARCHITECTURE-ANALYSIS 2026-07-14: 图纸A/实物B-)
   ▼
① STRATEGY-3YEAR-PANORAMA  ── 3 主题 · 5 支柱 · 三阶段
   │  方向拍板
   ▼
② ADR-0210  ── 收敛优先(选项B) · M1 门禁 · 只治本不加功能
   │  c2g 桥接 (CR-STRATEGY-01 + M2 Schema)
   ▼
③ 15 Bet/Task  ── 收敛6 · 兑现5 · 跃迁4
   │  radar 审计
   ▼
④ ALIGNMENT-AUDIT  ── 覆盖/北极星/优先级/风险/Owner/门禁 全对齐 · DAG
```

## 15 举措速查

| 阶段 | Bet | 举措 | Pri | Risk | Owner | Appetite |
|------|-----|------|-----|------|-------|----------|
| 收敛 | BET-be85 | Agent Isolation | P0 | L2 | 架构师 | 1 周 |
| 收敛 | BET-0059 | 修复 L1 runtime | P0 | L1 | SRE | 1 周 |
| 收敛 | BET-036b | 重构 health_score | P1 | L1 | 架构师 | 3 天 |
| 收敛 | BET-8d92 | gitlink 巡检 cron | P1 | L0 | SRE | 2 小时 |
| 收敛 | BET-b8c5 | KOS 索引启动 | P1 | L1 | 后端 | 1 周 |
| 收敛 | BET-aa56 | 单写者+门禁免疫 | P2 | L2 | 架构师 | 1 周 |
| 兑现 | BET-7e07 | Agent 注册中心+调度 | P0 | L2 | 后端 | 8 周 |
| 兑现 | BET-664e | 角色框架+协议 | P0 | L2 | 架构师 | 6 周 |
| 兑现 | BET-3e60 | 状态同步+故障转移 | P1 | L2 | 后端 | 6 周 |
| 兑现 | BET-b7da | 角色记忆共享 | P1 | L1 | 后端 | 4 周 |
| 兑现 | BET-8c7c | 涌现+集体决策 ⚠ | P2 | L3 | 架构师 | 6 周 |
| 跃迁 | BET-2522 | 个人知识图谱 | P1 | L2 | 后端 | 8 周 |
| 跃迁 | BET-c17d | 个人 AI 助手 | P1 | L1 | 前端 | 6 周 |
| 跃迁 | BET-ede9 | 数字孪生 ⚠ | P2 | L3 | 架构师 | 8 周 |
| 跃迁 | BET-ef25 | 治理产品化 | P2 | L1 | 架构师 | 6 周 |

⚠ = L3 高风险，启动前需专项评审（涌现不可控 / 隐私）。

## 里程碑门禁

| 门禁 | 时间 | 验收 |
|------|------|------|
| **M1** | 2027Q1 | daemon ≥ 90% + 并发 agent 零主仓冲突 → 方可进兑现期 |
| **M2** | 2027Q4 | 多机协作 ≥ 85% 真实可用 → 方可进跃迁期 |
| **M4** | 2029 | 个人大脑日常可用 + 治理方法论一次对外复用 |

## 待办（落地前）

1. ADR-0210 人工拍板 → PROPOSED 转 ACCEPTED。
2. 任务正式入 `.omo`：切 `--adapter ecos` + ADR-0203 先 `agent-workflow.py start`。
3. 兑现/跃迁期大 Bet（6–8 周）按 sub-pitch 二次拆细。
4. L3 两项（涌现、数字孪生）前置风险评审。

---

*Index · 2026-07-15 · 夏明星 · 全链路四产物导航*
