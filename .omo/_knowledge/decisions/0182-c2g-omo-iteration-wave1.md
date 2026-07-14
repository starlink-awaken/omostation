---
status: ACTIVE
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-14
---

# ADR-0182: C2G + OMO Wave 1 — 闭环迭代

## Context

C2G（战略需求引擎）和 OMO（治理内核）之间存在 4 个关键瓶颈：
1. **反馈闭环不完整**：C2G 发出的 pitch/bet 缺乏效果追踪，无法闭环回 C2G 优化
2. **缺乏预测性治理**：OMO 被动扫描，无前瞻性风险预警
3. **C2G 测试覆盖不足**：核心模块缺少单元测试
4. **OMO 性能瓶颈**：大 workspace 下扫描性能差

## Decision

采用 **Wave 1 迭代**，分 4 个 Epic 逐一解决：

### Epic 1: 反馈闭环增强
- OutcomeTracker: Pitch 全生命周期追踪（created → evaluated → in_progress → completed → archived）
- 成功评分函数（timely, effective, efficient, aligned）
- 排行榜 + 经验教训提炼
- CLI 集成：`c2g outcome list|track|analyze`

### Epic 2: 预测性治理
- PredictiveGovernanceEngine: 基于历史债务趋势预测风险
- RiskForecast: 时间序列预测 + 趋势分析
- ProactiveAction: 预防性建议生成
- 早期预警机制
- CLI 集成：`omo predict risks|debt|actions|alerts`

### Epic 3: 测试覆盖
- C2G: OutcomeTracker 5 测试, PitchAnalyzer 3 测试, Reliability 2 测试
- OMO: PredictiveGovernance 3 测试, StateCache 3 测试, ParallelScanner 2 测试

### Epic 4: 性能优化
- ParallelScanner: 多线程并发扫描
- GovernanceStateCache: TTL 缓存 + 失效策略
- 聚合结果合并

## Consequences

### Positive
- C2G → OMO 闭环：outcome 反馈可驱动 C2G 策略优化
- 预测性治理：提前发现债务风险
- 测试覆盖显著提升
- 大 workspace 扫描性能提升

### Negative
- 新增 4 个 M2 schema 需要维护
- 预测模型依赖历史数据质量
- 缓存机制增加状态管理复杂度

## Implementation

- 项目: `projects/c2g/`, `projects/omo/`
- 文件: outcome_tracker.py, pitch_analyzer.py, reliability.py, predictive_governance.py, state_cache.py, parallel_scanner.py
- 测试: 各模块配套测试文件
- MOF 集成: ADR-0183
