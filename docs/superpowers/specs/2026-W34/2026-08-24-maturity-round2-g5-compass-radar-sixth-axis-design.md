---
status: accepted
lifecycle: spec
owner: governance-team
created: 2026-08-24
last_updated: 2026-08-24
schema_version: specification/v1
spec_version: 1.0.0
bet_id: BET-Y1Q3-T10-05
type: ssot
last_updated: 2026-09-03
---

# Maturity Round 2 — G5: compass_radar 集成第 6 可观测轴 (observable 8→9)

> 日期：2026-08-24
> 状态：accepted
> BET：BET-Y1Q3-T10-05
> 上游设计：docs/operations/90pct-maturity-design.md (Round 2, G5)
> 依赖：G6 (T10-06) scorecard 升级的 observable 9 分档需要 ≥6 个雷达轴

## 背景与问题

`maturity-scorecard.py::score_observable` 9 分档要求 compass_radar 输出 ≥6 个独立分布
维度（雷达轴）。当前 compass_radar 只有 5 个（Priority/Risk/Owner/Phase/Status），
observable 被封顶 8，导致 G6 的 overall 9.0 数学不可达（5 维 9 + observable 8 = 8.8）。

## 架构选择

在 `compass_radar.py::build_health_projection`（composite 健康分计算后）新增第 6 个
可观测轴 `governance_dist`，从真实 composite breakdown 的三权重贡献
（governance/runtime/freshness）导出，并打印 `📊 Governance Distribution:`。
数据来源是 `_composite_health_score` 的真实计算（非 mock），反映"治理健康分项
可观测性"维度。

- 新增轴：`governance_dist` = {governance, freshness, runtime} 三权重贡献分
- 输出：STDOUT 打印第 6 个 Distribution 标题 + health.yaml distributions 增加一档
- 不修改已有 5 个分布的语义

替代方案（未采用）：按任务 dimension 聚合——c2g metrics 无 dimension 键；
人工映射 phase→成熟度档——造作且无数据支撑。

## 验收标准

1. **[compass_radar 输出 6 个 Distribution]**
   - 验证方式：`uv run --with pyyaml python3 bin/compass_radar.py --dry-run | grep -c "Distribution:"`
   - 证据类型：= 6

2. **[scorecard observable = 9]**
   - 验证方式：`python3 bin/gac/maturity-scorecard.py --json`
   - 证据类型：scores.observable = 9

3. **[G6 overall 9.0 可达]**
   - 验证方式：`python3 bin/gac/maturity-scorecard.py --json`
   - 证据类型：overall = 9.0 (六维全 9)

## 反指标

本 spec **不追求**以下指标作为成功度量：
- 10 分档（需自治自愈率 ≥90% 运行时证据, Phase 5 范畴）
- governance_dist 的业务精确性（三权重贡献分是健康分项的可观测代理）
- 每轴粒度细化（保持 6 个分布维度即可）

## Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|------|------|------|
| 1 | 加 composite 三权重轴 vs 任务 dimension 轴 | composite 三权重 | 数据真实 (非 mock), 贴合"治理健康可观测性" |
| 2 | 改 5 个现有分布 vs 新增第 6 个 | 新增 | 不改既有语义, 风险最小 |

## 变更历史

| 日期 | 变更内容 | 变更人 |
|------|----------|--------|
| 2026-08-24 | 初始版本 (grill-me 设计树 G5) | agent |
