---
status: accepted
lifecycle: spec
owner: governance-team
created: 2026-08-24
last_updated: 2026-08-24
schema_version: specification/v1
spec_version: 1.0.0
bet_id: BET-Y1Q3-T10-10
type: ssot
last_updated: 2026-09-03
---

# Maturity Round 2 — G10: 成熟度口径三方对齐 (health/scorecard/台账)

> 日期：2026-08-24
> 状态：accepted
> BET：BET-Y1Q3-T10-10
> 上游设计：docs/operations/90pct-maturity-design.md (Round 2, G10)

## 背景与问题

70→90 (health 报告) vs 6.8→9.0 (maturity-scorecard) vs 验证态 (台账) 三套口径不一致，
导致"系统到底多成熟"无法单一回答。G6 已把 scorecard 升级到 9/10 档 (overall 9.0)，
需要把 scorecard 定为成熟度唯一 SSOT，health/台账验证态映射到它。

## 架构选择

- `GOVERNANCE-EVOLUTION-ROADMAP.md` 新增"成熟度口径对齐"段：声明
  **maturity-scorecard (0-10, 9.0 目标) 为成熟度唯一 SSOT**，health 报告 (0-100) 是
  运行时健康子视图，台账验证态 (status) 是 bet 交付状态——三者映射关系明确。
- `maturity-scorecard.py` 输出加 `calibration` 字段：声明 target 9.0 与 health/台账
  的映射（health_score 复合分 70+ ≈ scorecard 8+，scorecard ≥9.0 ↔ 台账 T10-MATURITY
  bets 全 done）。

## 验收标准

1. **[roadmap 含成熟度口径对齐段]**
   - 验证方式：grep "成熟度口径" docs/GOVERNANCE-EVOLUTION-ROADMAP.md
   - 证据类型：三段映射 (scorecard/health/台账)

2. **[scorecard 输出含 calibration]**
   - 验证方式：`python3 bin/gac/maturity-scorecard.py --json` 含 calibration 字段
   - 证据类型：target 9.0 + health/台账映射

## 反指标

- 不合并 health/scorecard 为一个数字（health 是运行时子视图, scorecard 是成熟度主口径）
- 不重定义台账 status（保持 bet 交付状态语义）

## Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|------|------|------|
| 1 | 合并为一个数 vs 主口径+映射 | scorecard 主口径 + 映射 | 三套各有用途, 关键是声明主从关系 |

## 变更历史

| 日期 | 变更内容 | 变更人 |
|------|----------|--------|
| 2026-08-24 | 初始版本 (grill-me 设计树 G10) | agent |
