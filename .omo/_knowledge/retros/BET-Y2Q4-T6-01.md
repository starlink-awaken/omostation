---
schema: md/v1
status: active
lifecycle: history
owner: governance-agent
last-reviewed: 2026-09-26
type: retro
schema_version: retrospective/v1
title: "BET-Y2Q4-T6-01 Closeout Retro — 降档 ADR 草案就绪，强制生效留 human gate"
bet_id: BET-Y2Q4-T6-01
created: "2026-09-26"
run_id: 20260926T134308Z-governance-state-mutation-0c0f9680
---

# BET-Y2Q4-T6-01 Closeout Retro

> **TL;DR**: ADR-0456（PROPOSED）完稿：closeout/retro 分级（P0/P1 全量；P2 及以下
> 轻量模板 ≤40 行 + 20% 抽样 retro），目标 docs+chore 45%→≤35%，**三轴证据键集与
> D0–D6 纪律零改动**。Shadow 方案（前 10 单双轨 + 3 判据抽检）随 ADR 附带。
> **强制生效未启动**——human gate 留待 principal 批准（decision_ref 回填位已在 ADR
> 中预留），本 bet 按 done_when 的「如实记录等待批准」分支关账。

## 计划 vs 实际

| 项 | 计划 | 实际 |
|---|---|---|
| ADR-0456 完稿（数字基线/分级判据/风险/回滚） | ✅ | 45%→≤35% 基线、分级表、风险表、回滚 = status 改 SUPERSEDED（零迁移成本） |
| 标准 delta 提案 | ✅ | 并入 ADR「影响面与不做的事」节：明确不改的强制面（比单独 standards 文件更防误读；.omo/standards/ 写面保留，若批准后落地细则再写入） |
| shadow 方案 | ✅ | 10 单双轨 + 3 判据（遗漏信息=0 / 证据三行可复算 / 耗时对比），任一失败即回滚 |
| human gate | ✅ 如实记录 | PROPOSED 状态 + 批准回填位，未自行生效（redline 遵守） |

## 设计取舍

1. **分级不动证据矩阵**：D5 门禁（无 retro 不得 done）对被抽样 P2 单以
   `retro: sampled-out` 登记通过——门禁语义保留，豁免显式化，堵"静默缺失"。
2. **shadow 由 governance-agent 补写而非作者自写**：作者自评会系统性偏向
   "没丢信息"；独立补写 + 事后抽检才可信。
3. **legacy 枚举教训前置**：新轻量模板直接用合规 frontmatter 枚举
   （status: active / lifecycle: history），不再制造 legacy-omo-knowledge-enums 预算压力。

## 失败与反思

- done_when「标准 delta 提案文档就绪」最初设想单独 standards 文件；写的过程中
  意识到**提案期把"不改什么"写在一起比"要改什么"更重要**（防批准前被误读为已生效），
  合并入 ADR——单一事实源，批准后如需细则再拆分。

## 后续（全部等待批准后）

1. principal 批准 → 回填 decision_ref → ADR 转 ACCEPTED → shadow 启动；
2. shadow 10 单收口 → 抽检 3 判据 → 全过转常规；
3. 30 天后复算 docs+chore 占比（同基线命令），目标 ≤35%。
